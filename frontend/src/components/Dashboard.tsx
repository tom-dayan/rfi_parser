import { useState, useRef } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getProjectResults,
  getProjectFiles,
  processDocumentsStream,
  indexKnowledgeBase,
  getKnowledgeBaseStats,
  updateResult,
  type ProcessProgressEvent,
} from '../services/api';
import CoPilotMode from './CoPilotMode';
import { Card, Button, Badge, Progress, StepProgress } from './ui';
import type {
  ProcessingResultWithFile,
  DocumentType,
  SubmittalStatus,
} from '../types';

interface DashboardProps {
  projectId: number;
  projectName?: string;
}

export default function Dashboard({ projectId, projectName }: DashboardProps) {
  const [documentTypeFilter, setDocumentTypeFilter] = useState<DocumentType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<SubmittalStatus | 'all'>('all');
  const [selectedResult, setSelectedResult] = useState<ProcessingResultWithFile | null>(null);
  const [coPilotResult, setCoPilotResult] = useState<ProcessingResultWithFile | null>(null);
  const queryClient = useQueryClient();

  // Fetch knowledge base stats
  const { data: kbStats } = useQuery({
    queryKey: ['kb-stats', projectId],
    queryFn: () => getKnowledgeBaseStats(projectId),
  });

  // Fetch results
  const { data: results = [], isLoading: resultsLoading } = useQuery({
    queryKey: ['results', projectId],
    queryFn: () => getProjectResults(projectId),
  });

  // Fetch files by type
  const { data: rfiFiles = [] } = useQuery({
    queryKey: ['files', projectId, 'rfi'],
    queryFn: () => getProjectFiles(projectId, 'rfi'),
  });

  const { data: submittalFiles = [] } = useQuery({
    queryKey: ['files', projectId, 'submittal'],
    queryFn: () => getProjectFiles(projectId, 'submittal'),
  });

  const { data: specFiles = [] } = useQuery({
    queryKey: ['files', projectId, 'specification'],
    queryFn: () => getProjectFiles(projectId, 'specification'),
  });

  // Analyze state - tracks the combined index + process workflow
  const [analyzeState, setAnalyzeState] = useState<{
    phase: 'idle' | 'indexing' | 'processing' | 'complete' | 'error';
    message: string;
    currentFile?: string;
    currentIndex?: number;
    totalFiles?: number;
    processedCount?: number;
  }>({ phase: 'idle', message: '' });
  
  const processStreamRef = useRef<{ cancel: () => void } | null>(null);

  // Index knowledge base mutation
  const indexMutation = useMutation({
    mutationFn: () => indexKnowledgeBase(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['kb-stats', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const handleIndex = () => {
    indexMutation.mutate();
  };

  // Combined analyze workflow: index (if needed) + process with streaming
  const handleAnalyze = async () => {
    setAnalyzeState({ phase: 'indexing', message: 'Indexing specifications...' });
    
    try {
      // Index only new/changed files (not force), skip if already indexed
      await indexKnowledgeBase(projectId, false);
      queryClient.invalidateQueries({ queryKey: ['kb-stats', projectId] });
      
      setAnalyzeState({ 
        phase: 'processing', 
        message: 'Starting document analysis...',
        currentIndex: 0,
        totalFiles: rfiFiles.length + submittalFiles.length,
        processedCount: 0
      });
      
      // Use streaming endpoint for real-time progress
      processStreamRef.current = processDocumentsStream(
        projectId,
        (event: ProcessProgressEvent) => {
          if (event.event_type === 'processing' || event.event_type === 'file_complete') {
            setAnalyzeState(prev => ({
              ...prev,
              phase: 'processing',
              message: event.message,
              currentFile: event.current_file,
              currentIndex: event.current_file_index,
              totalFiles: event.total_files || prev.totalFiles,
              processedCount: event.event_type === 'file_complete' && event.success 
                ? (prev.processedCount || 0) + 1 
                : prev.processedCount
            }));
          } else if (event.event_type === 'complete') {
            queryClient.invalidateQueries({ queryKey: ['results', projectId] });
            queryClient.invalidateQueries({ queryKey: ['projects'] });
            
            setAnalyzeState({ 
              phase: 'complete', 
              message: `Analyzed ${event.processed} documents successfully!`,
              processedCount: event.processed,
              totalFiles: event.total_files
            });
            
            // Reset after 5 seconds
            setTimeout(() => {
              setAnalyzeState({ phase: 'idle', message: '' });
            }, 5000);
          } else if (event.event_type === 'error') {
            setAnalyzeState({ 
              phase: 'error', 
              message: event.message || 'Analysis failed. Please try again.'
            });
          }
        }
      );
      
    } catch (err) {
      setAnalyzeState({ 
        phase: 'error', 
        message: err instanceof Error ? err.message : 'Analysis failed. Please try again.' 
      });
    }
  };
  
  // Cancel processing on unmount
  const handleCancelProcessing = () => {
    if (processStreamRef.current) {
      processStreamRef.current.cancel();
      processStreamRef.current = null;
    }
    setAnalyzeState({ phase: 'idle', message: '' });
  };

  const isAnalyzing = analyzeState.phase === 'indexing' || analyzeState.phase === 'processing';

  // Filter results
  let filteredResults = results;
  if (documentTypeFilter !== 'all') {
    filteredResults = filteredResults.filter(
      (r: ProcessingResultWithFile) => r.document_type === documentTypeFilter
    );
  }
  if (statusFilter !== 'all') {
    filteredResults = filteredResults.filter(
      (r: ProcessingResultWithFile) => r.status === statusFilter
    );
  }

  // Count by document type
  const rfiResults = results.filter((r: ProcessingResultWithFile) => r.document_type === 'rfi');
  const submittalResults = results.filter((r: ProcessingResultWithFile) => r.document_type === 'submittal');

  const totalDocs = rfiFiles.length + submittalFiles.length;
  const isKbIndexed = kbStats?.indexed ?? false;

  return (
    <div className="space-y-6">
      {/* Knowledge Base Status Card */}
      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center ${isKbIndexed ? 'bg-spec-100' : 'bg-amber-100'}`}>
              <svg className={`w-5 h-5 ${isKbIndexed ? 'text-spec-600' : 'text-amber-600'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <div>
              <h3 className="font-semibold text-stone-900">Knowledge Base</h3>
              <div className="flex items-center gap-2 mt-1">
                {isKbIndexed ? (
                  <>
                    <Badge variant="success" size="sm" dot>Ready</Badge>
                    <span className="text-sm text-stone-500">
                      {kbStats?.document_count ?? 0} chunks from {specFiles.length} specs
                    </span>
                  </>
                ) : (
                  <Badge variant="warning" size="sm" dot>Not indexed</Badge>
                )}
              </div>
            </div>
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleIndex}
            disabled={indexMutation.isPending || specFiles.length === 0}
            loading={indexMutation.isPending}
          >
            {isKbIndexed ? 'Re-index' : 'Index Specs'}
          </Button>
        </div>
        {indexMutation.isSuccess && (
          <div className="mt-4 p-3 bg-spec-50 text-spec-700 rounded-xl text-sm border border-spec-200 flex items-center gap-2">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Indexed {indexMutation.data.files_indexed} files ({indexMutation.data.chunks_created} chunks)
          </div>
        )}
        {indexMutation.isError && (
          <div className="mt-4 p-3 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
            Indexing failed. Please try again.
          </div>
        )}
      </Card>

      {/* Results Header */}
      <Card>
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Document Analysis</h2>
            <div className="flex items-center gap-3 mt-2">
              <Badge variant="rfi">{rfiFiles.length} RFIs</Badge>
              <Badge variant="submittal">{submittalFiles.length} Submittals</Badge>
              {results.length > 0 && (
                <Badge variant="success">{results.length} analyzed</Badge>
              )}
            </div>
          </div>
          <Button
            variant="primary"
            onClick={handleAnalyze}
            disabled={isAnalyzing || totalDocs === 0 || specFiles.length === 0}
            loading={isAnalyzing}
          >
            {isAnalyzing ? analyzeState.message : 'Analyze Documents'}
          </Button>
        </div>

        {/* Progress indicator during analysis */}
        {isAnalyzing && (
          <div className="mb-6 p-4 bg-primary-50 rounded-xl border border-primary-200">
            <StepProgress
              steps={[
                { id: 'index', label: 'Indexing' },
                { id: 'analyze', label: 'Analyzing' },
                { id: 'complete', label: 'Complete' },
              ]}
              currentStep={analyzeState.phase === 'indexing' ? 0 : analyzeState.phase === 'processing' ? 1 : 2}
            />
            
            {/* Detailed progress for processing phase */}
            {analyzeState.phase === 'processing' && analyzeState.totalFiles && (
              <div className="mt-4">
                <div className="flex justify-between text-xs text-primary-600 mb-2">
                  <span>Processing documents</span>
                  <span>{analyzeState.currentIndex || 0} of {analyzeState.totalFiles}</span>
                </div>
                <Progress 
                  value={((analyzeState.currentIndex || 0) / analyzeState.totalFiles) * 100} 
                  size="md"
                />
                {analyzeState.currentFile && (
                  <p className="text-xs text-primary-500 mt-2 truncate">
                    Current: {analyzeState.currentFile}
                  </p>
                )}
              </div>
            )}
            
            <div className="flex items-center justify-between mt-4">
              <p className="text-sm text-primary-700">{analyzeState.message}</p>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCancelProcessing}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Status Messages */}
        {analyzeState.phase === 'error' && (
          <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm mb-4 border border-red-200 flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            {analyzeState.message}
          </div>
        )}

        {analyzeState.phase === 'complete' && (
          <div className="p-3 bg-spec-50 text-spec-700 rounded-xl text-sm mb-4 border border-spec-200 flex items-center gap-2">
            <svg className="w-4 h-4 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            {analyzeState.message}
          </div>
        )}

        {totalDocs === 0 && (
          <div className="p-4 bg-stone-50 text-stone-600 rounded-xl text-sm mb-4 border border-stone-200 text-center">
            <p className="font-medium mb-1">No documents to analyze</p>
            <p className="text-stone-500">Scan your folders first from the Files tab</p>
          </div>
        )}

        {totalDocs > 0 && specFiles.length === 0 && (
          <div className="p-4 bg-amber-50 text-amber-700 rounded-xl text-sm mb-4 border border-amber-200 text-center">
            <p className="font-medium mb-1">Specifications required</p>
            <p className="text-amber-600">Add spec files to enable AI analysis</p>
          </div>
        )}

        {/* Document Type Filter */}
        <div className="flex gap-2 flex-wrap mb-4">
          <button
            onClick={() => setDocumentTypeFilter('all')}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
              documentTypeFilter === 'all'
                ? 'bg-stone-800 text-white'
                : 'bg-stone-100 text-stone-700 hover:bg-stone-200'
            }`}
          >
            All ({results.length})
          </button>
          <button
            onClick={() => setDocumentTypeFilter('rfi')}
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
              documentTypeFilter === 'rfi'
                ? 'bg-rfi-600 text-white'
                : 'bg-rfi-50 text-rfi-700 hover:bg-rfi-100'
            }`}
          >
            RFIs ({rfiResults.length})
          </button>
          <button
            onClick={() => setDocumentTypeFilter('submittal')}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              documentTypeFilter === 'submittal'
                ? 'bg-indigo-600 text-white'
                : 'bg-indigo-50 text-indigo-700 hover:bg-indigo-100'
            }`}
          >
            Submittals ({submittalResults.length})
          </button>
        </div>

        {/* Status Filter (for submittals) */}
        {documentTypeFilter === 'submittal' && (
          <div className="flex gap-2 flex-wrap">
            <button
              onClick={() => setStatusFilter('all')}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
                statusFilter === 'all' ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-600'
              }`}
            >
              All
            </button>
            {(['no_exceptions', 'approved_as_noted', 'revise_and_resubmit', 'rejected', 'see_comments'] as SubmittalStatus[]).map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors capitalize ${
                  statusFilter === status ? 'bg-slate-700 text-white' : 'bg-slate-100 text-slate-600'
                }`}
              >
                {status.replace(/_/g, ' ')}
              </button>
            ))}
          </div>
        )}
      </Card>

      {/* Results Grid */}
      {resultsLoading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-slate-300 border-t-blue-600" />
          <p className="text-slate-500 mt-4">Loading results...</p>
        </div>
      ) : filteredResults.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-xl shadow-sm border border-slate-200">
          <div className="w-16 h-16 mx-auto rounded-full bg-slate-100 flex items-center justify-center mb-4">
            <svg
              className="w-8 h-8 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
              />
            </svg>
          </div>
          <h3 className="text-lg font-medium text-slate-900">No results yet</h3>
          <p className="mt-2 text-sm text-slate-500">
            {totalDocs === 0
              ? 'Scan your project folders first to index files.'
              : !isKbIndexed
              ? 'Index specifications, then process documents.'
              : 'Click "Process All Documents" to analyze your RFIs and Submittals.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredResults.map((result: ProcessingResultWithFile) => (
            <ResultCard 
              key={result.id} 
              result={result} 
              onViewDetails={() => setSelectedResult(result)}
              onCoPilot={() => setCoPilotResult(result)}
            />
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedResult && (
        <ResultDetailModal 
          result={selectedResult} 
          onClose={() => setSelectedResult(null)}
          onUpdate={() => {
            queryClient.invalidateQueries({ queryKey: ['results', projectId] });
          }}
        />
      )}

      {/* Co-Pilot Mode */}
      {coPilotResult && (
        <CoPilotMode
          result={coPilotResult}
          specFiles={specFiles}
          projectId={projectId}
          projectName={projectName}
          onClose={() => setCoPilotResult(null)}
          onSave={() => {
            setCoPilotResult(null);
            queryClient.invalidateQueries({ queryKey: ['results', projectId] });
          }}
        />
      )}
    </div>
  );
}

function ResultCard({ result, onViewDetails, onCoPilot }: { result: ProcessingResultWithFile; onViewDetails: () => void; onCoPilot: () => void }) {
  const isRFI = result.document_type === 'rfi';
  const isTruncated = result.response_text && result.response_text.length > 300;
  const hasMoreRefs = result.spec_references && result.spec_references.length > 2;

  return (
    <div className="bg-white rounded-lg shadow-md p-6 flex flex-col">
      <div className="flex items-start justify-between mb-4">
        <div>
          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
            isRFI ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
          }`}>
            {isRFI ? 'RFI' : 'Submittal'}
          </span>
          <h3 className="text-lg font-semibold text-gray-900 mt-2">
            {result.source_file?.filename || result.source_filename || 'Unknown'}
          </h3>
        </div>
        {!isRFI && result.status && (
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(result.status)}`}>
            {result.status.replace(/_/g, ' ')}
          </span>
        )}
      </div>

      {result.response_text && (
        <div className="mb-4 flex-1">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            {isRFI ? 'Response' : 'Review Comments'}
          </h4>
          <p className="text-sm text-gray-600 whitespace-pre-wrap">
            {isTruncated
              ? result.response_text.substring(0, 300) + '...'
              : result.response_text}
          </p>
        </div>
      )}

      {result.spec_references && result.spec_references.length > 0 && (
        <div className="mb-4">
          <h4 className="text-sm font-medium text-gray-700 mb-2">
            Specification References {hasMoreRefs && <span className="text-gray-400">({result.spec_references.length})</span>}
          </h4>
          <div className="space-y-2">
            {result.spec_references.slice(0, 2).map((ref, idx) => (
              <div key={idx} className="text-xs bg-gray-50 p-2 rounded">
                <span className="font-medium">{ref.source_filename}</span>
                {ref.section && <span className="text-gray-500"> - {ref.section}</span>}
              </div>
            ))}
            {hasMoreRefs && (
              <p className="text-xs text-gray-400">+{result.spec_references.length - 2} more references</p>
            )}
          </div>
        </div>
      )}

      {result.consultant_type && (
        <div className="text-sm text-orange-600 mb-4">
          Refer to: {result.consultant_type} consultant
        </div>
      )}

      <div className="mt-auto pt-4 border-t border-gray-100 flex justify-between items-center">
        <div className="text-xs text-gray-500">
          <span>AI Confidence: {(result.confidence * 100).toFixed(0)}%</span>
          <span className="mx-2">•</span>
          <span>{new Date(result.processed_date).toLocaleDateString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onCoPilot}
            className="text-sm text-purple-600 hover:text-purple-800 font-medium flex items-center gap-1"
            title="Open Co-Pilot mode for step-by-step drafting"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            Co-Pilot
          </button>
          {(isTruncated || hasMoreRefs) && (
            <button
              onClick={onViewDetails}
              className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
            >
              View Full
              <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function ResultDetailModal({ 
  result, 
  onClose,
  onUpdate
}: { 
  result: ProcessingResultWithFile; 
  onClose: () => void;
  onUpdate?: () => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(result.response_text || '');
  const [isSaving, setIsSaving] = useState(false);
  const isRFI = result.document_type === 'rfi';

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateResult(result.id, { response_text: editedText });
      setIsEditing(false);
      onUpdate?.();
    } catch (err) {
      console.error('Failed to save:', err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleCancel = () => {
    setEditedText(result.response_text || '');
    setIsEditing(false);
  };

  // Close on escape key (only if not editing)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && !isEditing) onClose();
  };

  return (
    <div 
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={!isEditing ? onClose : undefined}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-start justify-between">
          <div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
                isRFI ? 'bg-blue-50 text-blue-700' : 'bg-indigo-50 text-indigo-700'
              }`}>
                {isRFI ? 'RFI' : 'Submittal'}
              </span>
              {!isRFI && result.status && (
                <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(result.status)}`}>
                  {result.status.replace(/_/g, ' ')}
                </span>
              )}
              <span className="text-xs text-slate-500">
                AI Confidence: {(result.confidence * 100).toFixed(0)}%
              </span>
            </div>
            <h2 className="text-lg font-semibold text-slate-900">
              {result.source_file?.filename || result.source_filename || 'Unknown'}
            </h2>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 p-1 rounded-lg hover:bg-slate-100 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Response Text */}
          <div className="mb-6">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-slate-900 uppercase tracking-wide">
                {isRFI ? 'AI Response' : 'Review Comments'}
              </h3>
              {!isEditing && (
                <button
                  onClick={() => setIsEditing(true)}
                  className="flex items-center gap-1.5 text-sm text-blue-600 hover:text-blue-700 font-medium"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                  Edit
                </button>
              )}
            </div>
            
            {isEditing ? (
              <div className="space-y-3">
                <textarea
                  value={editedText}
                  onChange={(e) => setEditedText(e.target.value)}
                  className="w-full h-64 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm text-slate-700 resize-none"
                  placeholder="Enter response text..."
                />
                <div className="flex justify-end gap-2">
                  <button
                    onClick={handleCancel}
                    disabled={isSaving}
                    className="px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleSave}
                    disabled={isSaving}
                    className="px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-lg transition-colors disabled:opacity-50"
                  >
                    {isSaving ? 'Saving...' : 'Save Changes'}
                  </button>
                </div>
              </div>
            ) : (
              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                <p className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed">
                  {result.response_text || 'No response text available.'}
                </p>
              </div>
            )}
          </div>

          {/* Consultant Referral */}
          {result.consultant_type && (
            <div className="mb-6 p-4 bg-orange-50 border border-orange-200 rounded-lg">
              <div className="flex items-center">
                <svg className="w-5 h-5 text-orange-600 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
                <span className="text-orange-800 font-medium">
                  Recommend referral to: {result.consultant_type} consultant
                </span>
              </div>
            </div>
          )}

          {/* Specification References */}
          {result.spec_references && result.spec_references.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide">
                  Specification References ({result.spec_references.length})
                </h3>
                <span className="text-xs text-gray-500">
                  Avg Relevance: {(result.spec_references.reduce((sum, ref) => sum + ref.score, 0) / result.spec_references.length * 100).toFixed(0)}%
                </span>
              </div>
              <div className="space-y-3">
                {result.spec_references.map((ref, idx) => (
                  <div key={idx} className="bg-gray-50 rounded-lg p-4 border border-gray-200">
                    <div className="flex items-start justify-between mb-2">
                      <div>
                        <span className="font-medium text-gray-900">{ref.source_filename}</span>
                        {ref.section && (
                          <span className="ml-2 text-sm text-gray-500">Section: {ref.section}</span>
                        )}
                      </div>
                      <span className="text-xs bg-blue-100 text-blue-800 px-2 py-1 rounded">
                        {(ref.score * 100).toFixed(0)}% relevance
                      </span>
                    </div>
                    {ref.text && (
                      <p className="text-sm text-gray-600 mt-2 italic">
                        "{ref.text.length > 300 ? ref.text.substring(0, 300) + '...' : ref.text}"
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50 flex justify-between items-center">
          <span className="text-xs text-gray-500">
            Processed: {new Date(result.processed_date).toLocaleString()}
          </span>
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors text-sm font-medium"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

function getStatusColor(status: SubmittalStatus): string {
  const colors: Record<SubmittalStatus, string> = {
    no_exceptions: 'bg-green-100 text-green-800',
    approved_as_noted: 'bg-blue-100 text-blue-800',
    revise_and_resubmit: 'bg-yellow-100 text-yellow-800',
    rejected: 'bg-red-100 text-red-800',
    see_comments: 'bg-gray-100 text-gray-800',
  };
  return colors[status] || 'bg-gray-100 text-gray-800';
}
