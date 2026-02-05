import { useState, useCallback } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getProjectFiles, scanProjectStream, indexKnowledgeBase } from '../services/api';
import type { ProjectFileSummary, ContentType, ScanProgressEvent, ScanResult, IndexResult } from '../types';

interface FileExplorerProps {
  projectId: number;
}

const contentTypeLabels: Record<ContentType, string> = {
  rfi: 'RFIs',
  submittal: 'Submittals',
  specification: 'Specifications',
  drawing: 'Drawings',
  image: 'Images',
  other: 'Other Files',
};

const contentTypeColors: Record<ContentType, string> = {
  rfi: 'bg-blue-50 text-blue-700',
  submittal: 'bg-indigo-50 text-indigo-700',
  specification: 'bg-emerald-50 text-emerald-700',
  drawing: 'bg-purple-50 text-purple-700',
  image: 'bg-amber-50 text-amber-700',
  other: 'bg-slate-100 text-slate-700',
};

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

type SetupPhase = 'idle' | 'scanning' | 'indexing' | 'complete' | 'error';

interface SetupState {
  phase: SetupPhase;
  scanProgress: ScanProgressEvent | null;
  scanResult: ScanResult | null;
  indexResult: IndexResult | null;
  error: string | null;
}

export default function FileExplorer({ projectId }: FileExplorerProps) {
  const [selectedType, setSelectedType] = useState<ContentType | 'all'>('all');
  const [setupState, setSetupState] = useState<SetupState>({
    phase: 'idle',
    scanProgress: null,
    scanResult: null,
    indexResult: null,
    error: null,
  });
  const queryClient = useQueryClient();

  const { data: files = [], isLoading } = useQuery({
    queryKey: ['files', projectId, selectedType],
    queryFn: () => getProjectFiles(projectId, selectedType === 'all' ? undefined : selectedType),
  });

  // Combined scan + index workflow
  const handleScanAndIndex = useCallback(() => {
    setSetupState({
      phase: 'scanning',
      scanProgress: null,
      scanResult: null,
      indexResult: null,
      error: null,
    });

    scanProjectStream(projectId, async (event) => {
      setSetupState((prev) => ({
        ...prev,
        scanProgress: event,
        scanResult: event.result || prev.scanResult,
        error: event.error || null,
      }));

      // When scan completes, automatically start indexing
      if (event.event_type === 'complete') {
        queryClient.invalidateQueries({ queryKey: ['files', projectId] });
        queryClient.invalidateQueries({ queryKey: ['projects'] });

        // Start indexing phase
        setSetupState((prev) => ({
          ...prev,
          phase: 'indexing',
        }));

        try {
          const indexResult = await indexKnowledgeBase(projectId, false);
          setSetupState((prev) => ({
            ...prev,
            phase: 'complete',
            indexResult,
          }));
          queryClient.invalidateQueries({ queryKey: ['kb-stats', projectId] });
          queryClient.invalidateQueries({ queryKey: ['projects'] });
        } catch (err) {
          setSetupState((prev) => ({
            ...prev,
            phase: 'complete', // Still complete, just with index errors
            error: err instanceof Error ? err.message : 'Indexing failed',
          }));
        }
      } else if (event.event_type === 'error') {
        setSetupState((prev) => ({
          ...prev,
          phase: 'error',
        }));
      }
    });
  }, [projectId, queryClient]);

  const isProcessing = setupState.phase === 'scanning' || setupState.phase === 'indexing';

  // Group files by content type
  const groupedFiles = files.reduce((acc, file) => {
    const type = file.content_type;
    if (!acc[type]) acc[type] = [];
    acc[type].push(file);
    return acc;
  }, {} as Record<ContentType, ProjectFileSummary[]>);

  const typeCounts: Record<string, number> = {
    all: files.length,
    rfi: groupedFiles.rfi?.length || 0,
    submittal: groupedFiles.submittal?.length || 0,
    specification: groupedFiles.specification?.length || 0,
    drawing: groupedFiles.drawing?.length || 0,
    image: groupedFiles.image?.length || 0,
    other: groupedFiles.other?.length || 0,
  };

  const scanProgress = setupState.scanProgress;
  const progressPercent = scanProgress?.total_files
    ? Math.round((scanProgress.current_file_index / scanProgress.total_files) * 100)
    : 0;

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-lg font-semibold text-slate-900">Project Files</h2>
        <button
          onClick={handleScanAndIndex}
          disabled={isProcessing}
          className="px-4 py-2.5 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700 disabled:bg-slate-300 transition-colors flex items-center shadow-sm"
        >
          {isProcessing ? (
            <>
              <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              {setupState.phase === 'scanning' ? 'Scanning...' : 'Indexing...'}
            </>
          ) : (
            <>
              <svg className="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              Scan & Index
            </>
          )}
        </button>
      </div>

      {/* Combined Progress Display */}
      {isProcessing && (
        <div className="mb-4 p-4 bg-blue-50 rounded-lg">
          {/* Step indicators */}
          <div className="flex items-center mb-3">
            <div className={`flex items-center ${setupState.phase === 'scanning' ? 'text-blue-700' : 'text-green-600'}`}>
              {setupState.phase === 'scanning' ? (
                <svg className="animate-spin h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <svg className="h-4 w-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
              )}
              <span className="text-sm font-medium">1. Scan</span>
            </div>
            <div className="mx-3 h-px w-8 bg-gray-300" />
            <div className={`flex items-center ${setupState.phase === 'indexing' ? 'text-blue-700' : 'text-gray-400'}`}>
              {setupState.phase === 'indexing' ? (
                <svg className="animate-spin h-4 w-4 mr-1" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                <span className="h-4 w-4 mr-1 rounded-full border-2 border-current" />
              )}
              <span className="text-sm font-medium">2. Index</span>
            </div>
          </div>

          {/* Scanning progress */}
          {setupState.phase === 'scanning' && scanProgress && (
            <>
              <div className="flex justify-between text-sm text-blue-800 mb-2">
                <span>{scanProgress.message}</span>
                <span>{progressPercent}%</span>
              </div>
              <div className="w-full bg-blue-200 rounded-full h-3">
                <div
                  className="bg-blue-600 h-3 rounded-full transition-all duration-300 ease-out"
                  style={{ width: `${progressPercent}%` }}
                />
              </div>
              {scanProgress.current_file && (
                <p className="text-xs text-blue-600 mt-2 truncate">
                  {scanProgress.phase === 'rfi' ? 'RFI' : 'Specs'}: {scanProgress.current_file}
                </p>
              )}
              <p className="text-xs text-blue-500 mt-1">
                {scanProgress.current_file_index} of {scanProgress.total_files} files
              </p>
            </>
          )}

          {/* Indexing progress */}
          {setupState.phase === 'indexing' && (
            <div className="text-sm text-blue-800">
              <p>Building knowledge base from specifications...</p>
              <p className="text-xs text-blue-600 mt-1">This may take a moment for large documents.</p>
            </div>
          )}
        </div>
      )}

      {/* Error Message */}
      {setupState.error && (
        <div className="mb-4 p-3 bg-red-50 text-red-800 rounded-lg text-sm">
          {setupState.error}
        </div>
      )}

      {/* Success Message */}
      {setupState.phase === 'complete' && !setupState.error && (
        <div className="mb-4 p-3 bg-green-50 text-green-800 rounded-lg text-sm">
          <div className="flex items-center mb-1">
            <svg className="h-4 w-4 mr-2 text-green-600" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
            </svg>
            <span className="font-medium">Setup Complete!</span>
          </div>
          {setupState.scanResult && (
            <p>Found {setupState.scanResult.files_found} files (Added: {setupState.scanResult.files_added}, Updated: {setupState.scanResult.files_updated})</p>
          )}
          {setupState.indexResult && (
            <p>Indexed {setupState.indexResult.files_indexed} specs ({setupState.indexResult.chunks_created} chunks)</p>
          )}
          <p className="text-xs mt-2 text-green-600">You can now process RFIs and Submittals from the Results tab.</p>
        </div>
      )}

      {/* Filter tabs */}
      <div className="flex gap-2 mb-6 flex-wrap">
        <FilterButton
          label="All"
          count={typeCounts.all}
          active={selectedType === 'all'}
          onClick={() => setSelectedType('all')}
        />
        <FilterButton
          label="RFIs"
          count={typeCounts.rfi}
          active={selectedType === 'rfi'}
          onClick={() => setSelectedType('rfi')}
          color="blue"
        />
        <FilterButton
          label="Submittals"
          count={typeCounts.submittal}
          active={selectedType === 'submittal'}
          onClick={() => setSelectedType('submittal')}
          color="indigo"
        />
        <FilterButton
          label="Specs"
          count={typeCounts.specification}
          active={selectedType === 'specification'}
          onClick={() => setSelectedType('specification')}
          color="green"
        />
        <FilterButton
          label="Drawings"
          count={typeCounts.drawing}
          active={selectedType === 'drawing'}
          onClick={() => setSelectedType('drawing')}
          color="purple"
        />
        <FilterButton
          label="Images"
          count={typeCounts.image}
          active={selectedType === 'image'}
          onClick={() => setSelectedType('image')}
          color="yellow"
        />
      </div>

      {/* File list */}
      {isLoading ? (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-blue-600" />
          <p className="text-gray-600 mt-2">Loading files...</p>
        </div>
      ) : files.length === 0 ? (
        <div className="text-center py-8 text-gray-500">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 19a2 2 0 01-2-2V7a2 2 0 012-2h4l2 2h4a2 2 0 012 2v1M5 19h14a2 2 0 002-2v-5a2 2 0 00-2-2H9a2 2 0 00-2 2v5a2 2 0 01-2 2z" />
          </svg>
          <p className="mt-2">No files found. Click "Rescan Folders" to index files.</p>
        </div>
      ) : (
        <div className="divide-y divide-gray-200">
          {files.map((file) => (
            <FileRow key={file.id} file={file} />
          ))}
        </div>
      )}
    </div>
  );
}

function FilterButton({
  label,
  count,
  active,
  onClick,
  color = 'gray',
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  color?: string;
}) {
  const colorClasses: Record<string, string> = {
    gray: active ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
    blue: active ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700 hover:bg-blue-100',
    indigo: active ? 'bg-indigo-600 text-white' : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100',
    green: active ? 'bg-green-600 text-white' : 'bg-green-50 text-green-700 hover:bg-green-100',
    purple: active ? 'bg-purple-600 text-white' : 'bg-purple-50 text-purple-700 hover:bg-purple-100',
    yellow: active ? 'bg-yellow-600 text-white' : 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100',
  };

  return (
    <button
      onClick={onClick}
      className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${colorClasses[color]}`}
    >
      {label} ({count})
    </button>
  );
}

function FileRow({ file }: { file: ProjectFileSummary }) {
  return (
    <div className="py-3 flex items-center justify-between hover:bg-gray-50 px-2 -mx-2 rounded">
      <div className="flex items-center min-w-0">
        <FileIcon fileType={file.file_type} />
        <div className="ml-3 min-w-0">
          <p className="text-sm font-medium text-gray-900 truncate">{file.filename}</p>
          <p className="text-xs text-gray-500">
            {formatFileSize(file.file_size)} • {file.file_type.toUpperCase()}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 ml-4">
        <span className={`px-2 py-1 rounded text-xs font-medium ${contentTypeColors[file.content_type]}`}>
          {contentTypeLabels[file.content_type]}
        </span>
        {file.has_content ? (
          <span className="text-green-500" title="Content indexed">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
            </svg>
          </span>
        ) : (
          <span className="text-gray-400" title="No content extracted">
            <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </span>
        )}
      </div>
    </div>
  );
}

function FileIcon({ fileType }: { fileType: string }) {
  const iconClasses = "w-8 h-8 text-gray-400";

  switch (fileType.toLowerCase()) {
    case 'pdf':
      return (
        <svg className={iconClasses} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M4 4a2 2 0 012-2h4.586A2 2 0 0112 2.586L15.414 6A2 2 0 0116 7.414V16a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
        </svg>
      );
    case 'dwg':
    case 'dxf':
      return (
        <svg className={iconClasses} fill="currentColor" viewBox="0 0 20 20">
          <path d="M3 4a1 1 0 011-1h12a1 1 0 011 1v2a1 1 0 01-1 1H4a1 1 0 01-1-1V4zM3 10a1 1 0 011-1h6a1 1 0 011 1v6a1 1 0 01-1 1H4a1 1 0 01-1-1v-6zM14 9a1 1 0 00-1 1v6a1 1 0 001 1h2a1 1 0 001-1v-6a1 1 0 00-1-1h-2z" />
        </svg>
      );
    case 'png':
    case 'jpg':
    case 'jpeg':
      return (
        <svg className={iconClasses} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M4 3a2 2 0 00-2 2v10a2 2 0 002 2h12a2 2 0 002-2V5a2 2 0 00-2-2H4zm12 12H4l4-8 3 6 2-4 3 6z" clipRule="evenodd" />
        </svg>
      );
    default:
      return (
        <svg className={iconClasses} fill="currentColor" viewBox="0 0 20 20">
          <path fillRule="evenodd" d="M4 4a2 2 0 012-2h8a2 2 0 012 2v12a2 2 0 01-2 2H6a2 2 0 01-2-2V4z" clipRule="evenodd" />
        </svg>
      );
  }
}
