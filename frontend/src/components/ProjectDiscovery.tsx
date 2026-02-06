import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { discoverProjects, createProject, type ProjectCandidate } from '../services/api';
import { Card, CardHeader, CardTitle, Button, Badge, Progress, Modal } from './ui';
import FolderBrowser from './FolderBrowser';

interface ProjectDiscoveryProps {
  onProjectCreated?: (projectId: number) => void;
  onClose?: () => void;
}

export default function ProjectDiscovery({ onProjectCreated, onClose }: ProjectDiscoveryProps) {
  const [rootPath, setRootPath] = useState('');
  const [showBrowser, setShowBrowser] = useState(false);
  const [selectedCandidate, setSelectedCandidate] = useState<ProjectCandidate | null>(null);
  const [editingName, setEditingName] = useState('');
  
  const queryClient = useQueryClient();

  const { 
    data: discoveryResult, 
    isLoading, 
    isError, 
    error,
    refetch 
  } = useQuery({
    queryKey: ['discover-projects', rootPath],
    queryFn: () => discoverProjects(rootPath || undefined, 3, 0.2),
    enabled: false, // Manual trigger only
    retry: false,
  });

  const createMutation = useMutation({
    mutationFn: (candidate: ProjectCandidate) => createProject({
      name: editingName || candidate.name,
      rfi_folder_path: candidate.rfi_folder || candidate.root_path,
      specs_folder_path: candidate.specs_folder || candidate.root_path,
    }),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      setSelectedCandidate(null);
      onProjectCreated?.(data.id);
    },
  });

  const handleDiscover = () => {
    refetch();
  };

  const handleSelectCandidate = (candidate: ProjectCandidate) => {
    setSelectedCandidate(candidate);
    setEditingName(candidate.name);
  };

  const handleCreateFromCandidate = () => {
    if (selectedCandidate) {
      createMutation.mutate(selectedCandidate);
    }
  };

  const getConfidenceColor = (confidence: number) => {
    if (confidence >= 0.7) return 'success';
    if (confidence >= 0.4) return 'warning';
    return 'default';
  };

  const getConfidenceLabel = (confidence: number) => {
    if (confidence >= 0.7) return 'High match';
    if (confidence >= 0.4) return 'Medium match';
    return 'Low match';
  };

  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <svg className="w-5 h-5 text-primary-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            Discover Projects
          </CardTitle>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-stone-400 hover:text-stone-600 hover:bg-stone-100 rounded-lg transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </CardHeader>

        <p className="text-sm text-stone-500 mb-6">
          Scan your shared folders to automatically find project directories with RFIs, submittals, and project knowledge.
        </p>

        {/* Root Path Input */}
        <div className="mb-6">
          <label className="block text-sm font-medium text-stone-700 mb-2">
            Shared Folder Root (optional)
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={rootPath}
              onChange={(e) => setRootPath(e.target.value)}
              placeholder="Leave empty to use configured default"
              className="input flex-1"
            />
            <Button
              type="button"
              variant="secondary"
              size="md"
              onClick={() => setShowBrowser(true)}
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              }
            />
            <Button
              type="button"
              variant="primary"
              onClick={handleDiscover}
              loading={isLoading}
              icon={!isLoading ? (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
              ) : undefined}
            >
              {isLoading ? 'Scanning...' : 'Discover'}
            </Button>
          </div>
          <p className="mt-1.5 text-xs text-stone-400">
            Tip: Point to your office's shared network drive where projects are stored
          </p>
        </div>

        {/* Loading State */}
        {isLoading && (
          <div className="py-8 text-center">
            <div className="inline-flex items-center gap-3 text-stone-500">
              <svg className="w-5 h-5 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              <span>Scanning folders for projects...</span>
            </div>
            <Progress value={50} className="mt-4 max-w-xs mx-auto" indeterminate />
          </div>
        )}

        {/* Error State */}
        {isError && (
          <div className="p-4 bg-red-50 text-red-700 rounded-xl border border-red-200">
            <div className="flex items-start gap-3">
              <svg className="w-5 h-5 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
              <div>
                <p className="font-medium">Failed to discover projects</p>
                <p className="text-sm mt-1">
                  {error instanceof Error ? error.message : 'Please check the folder path and try again.'}
                </p>
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {discoveryResult && !isLoading && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-medium text-stone-700">
                Found {discoveryResult.total} potential project{discoveryResult.total !== 1 ? 's' : ''}
              </h3>
              {discoveryResult.total > 0 && (
                <p className="text-xs text-stone-400">
                  Click a project to create it
                </p>
              )}
            </div>

            {discoveryResult.candidates.length === 0 ? (
              <div className="py-8 text-center text-stone-500">
                <svg className="w-12 h-12 mx-auto mb-3 text-stone-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
                <p>No projects found in this location</p>
                <p className="text-sm mt-1">Try a different folder path</p>
              </div>
            ) : (
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {discoveryResult.candidates.map((candidate, idx) => (
                  <button
                    key={idx}
                    onClick={() => handleSelectCandidate(candidate)}
                    className="w-full text-left p-4 bg-stone-50 hover:bg-stone-100 rounded-xl border border-stone-200 hover:border-primary-300 transition group"
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-stone-900 truncate group-hover:text-primary-600">
                            {candidate.name}
                          </h4>
                          <Badge 
                            variant={getConfidenceColor(candidate.confidence) as 'success' | 'warning' | 'default'} 
                            size="sm"
                          >
                            {getConfidenceLabel(candidate.confidence)}
                          </Badge>
                        </div>
                        <p className="text-xs text-stone-500 truncate mt-1">
                          {candidate.root_path}
                        </p>
                      </div>
                      <svg className="w-5 h-5 text-stone-300 group-hover:text-primary-500 flex-shrink-0 ml-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      {candidate.rfi_folder && (
                        <Badge variant="rfi" size="sm">
                          {candidate.rfi_count} RFIs
                        </Badge>
                      )}
                      {candidate.specs_folder && (
                        <Badge variant="spec" size="sm">
                          {candidate.spec_count} Knowledge
                        </Badge>
                      )}
                      <Badge variant="default" size="sm">
                        {candidate.file_count} total files
                      </Badge>
                    </div>

                    {candidate.reasons.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {candidate.reasons.slice(0, 3).map((reason, i) => (
                          <span key={i} className="text-xs text-stone-400">
                            • {reason}
                          </span>
                        ))}
                      </div>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Empty State - Before First Search */}
        {!discoveryResult && !isLoading && !isError && (
          <div className="py-12 text-center text-stone-400">
            <svg className="w-16 h-16 mx-auto mb-4 text-stone-200" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <p className="text-stone-500 mb-1">Ready to discover projects</p>
            <p className="text-sm">Enter a folder path or click "Discover" to scan the default location</p>
          </div>
        )}

        {/* Folder Browser */}
        <FolderBrowser
          isOpen={showBrowser}
          onClose={() => setShowBrowser(false)}
          onSelect={(path) => {
            setRootPath(path);
            setShowBrowser(false);
          }}
          initialPath={rootPath}
        />
      </Card>

      {/* Create Project Modal */}
      <Modal
        isOpen={selectedCandidate !== null}
        onClose={() => setSelectedCandidate(null)}
        title="Create Project"
        size="md"
      >
        {selectedCandidate && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-stone-700 mb-2">
                Project Name
              </label>
              <input
                type="text"
                value={editingName}
                onChange={(e) => setEditingName(e.target.value)}
                className="input w-full"
                placeholder="Enter project name"
              />
            </div>

            <div className="p-4 bg-stone-50 rounded-xl space-y-3">
              <div>
                <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-1">
                  RFI/Submittal Folder
                </p>
                <p className="text-sm text-stone-700 break-all">
                  {selectedCandidate.rfi_folder || selectedCandidate.root_path}
                </p>
              </div>
              <div>
                <p className="text-xs font-medium text-stone-500 uppercase tracking-wide mb-1">
                  Project Knowledge Folder
                </p>
                <p className="text-sm text-stone-700 break-all">
                  {selectedCandidate.specs_folder || selectedCandidate.root_path}
                </p>
              </div>
            </div>

            {createMutation.isError && (
              <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm border border-red-200">
                Failed to create project. The folders may already be in use.
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Button
                variant="secondary"
                onClick={() => setSelectedCandidate(null)}
                className="flex-1"
              >
                Cancel
              </Button>
              <Button
                variant="primary"
                onClick={handleCreateFromCandidate}
                loading={createMutation.isPending}
                disabled={!editingName.trim()}
                className="flex-1"
              >
                {createMutation.isPending ? 'Creating...' : 'Create Project'}
              </Button>
            </div>
          </div>
        )}
      </Modal>
    </>
  );
}
