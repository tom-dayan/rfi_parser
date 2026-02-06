import { useState, useCallback, useMemo, useEffect, memo } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import {
  updateResult,
  refineResult,
  getSpecFolderTree,
  type PathBasedSpecSuggestion,
} from '../services/api';
import type { ProcessingResultWithFile } from '../types';

interface RefineModeProps {
  result: ProcessingResultWithFile;
  projectId: number;
  projectName?: string;
  onClose: () => void;
  onSave: () => void;
}

type Step = 'review' | 'specs' | 'refine' | 'finalize';

export default function RefineMode({
  result,
  projectId,
  projectName: _projectName,
  onClose,
  onSave,
}: RefineModeProps) {
  const [currentStep, setCurrentStep] = useState<Step>('review');
  const [draftText, setDraftText] = useState(result.response_text || '');
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [regenerateError, setRegenerateError] = useState<string | null>(null);
  const [userInstructions, setUserInstructions] = useState('');
  const queryClient = useQueryClient();

  // Spec selection state
  const [selectedSpecPaths, setSelectedSpecPaths] = useState<Set<string>>(new Set());
  const [allSpecFiles, setAllSpecFiles] = useState<PathBasedSpecSuggestion[]>([]);
  const [allFolders, setAllFolders] = useState<string[]>([]);
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set());
  const [specSearchQuery, setSpecSearchQuery] = useState('');
  const [isLoadingSpecs, setIsLoadingSpecs] = useState(false);
  const [specsLoaded, setSpecsLoaded] = useState(false);
  const [specsError, setSpecsError] = useState<string | null>(null);
  const [hasSpecChanges, setHasSpecChanges] = useState(false);

  const isRFI = result.document_type === 'rfi';

  const steps: { id: Step; label: string; description: string }[] = [
    { id: 'review', label: 'Review', description: 'Review the current AI response' },
    { id: 'specs', label: 'Specifications', description: 'Edit spec file selections' },
    { id: 'refine', label: 'Refine', description: 'Regenerate or manually edit the response' },
    { id: 'finalize', label: 'Finalize', description: 'Review and save the final response' },
  ];

  const currentStepIndex = steps.findIndex(s => s.id === currentStep);

  // Load spec folder tree when user navigates to specs step
  useEffect(() => {
    if (currentStep === 'specs' && !specsLoaded && !isLoadingSpecs) {
      loadSpecFolderTree();
    }
  }, [currentStep]);

  const loadSpecFolderTree = async () => {
    setIsLoadingSpecs(true);
    setSpecsError(null);
    try {
      const treeData = await getSpecFolderTree(projectId);
      const files = treeData.files || [];
      const folders = treeData.folders || [];
      
      setAllSpecFiles(files);
      setAllFolders(folders);
      
      // Pre-select specs from current result's spec_references
      const existingSpecs = new Set<string>();
      if (result.spec_references) {
        for (const ref of result.spec_references) {
          // Match by filename
          const matching = files.find(f => f.name === ref.source_filename);
          if (matching) {
            existingSpecs.add(matching.path);
          }
        }
      }
      setSelectedSpecPaths(existingSpecs);
      
      // Auto-expand folders that contain selected specs
      const foldersToExpand = new Set<string>();
      for (const file of files) {
        if (existingSpecs.has(file.path) && file.folder) {
          // Expand the folder and all parent folders
          const parts = file.folder.split('/');
          let current = '';
          for (const part of parts) {
            current = current ? `${current}/${part}` : part;
            foldersToExpand.add(current);
          }
        }
      }
      setExpandedFolders(foldersToExpand);
      
      setSpecsLoaded(true);
    } catch (err) {
      console.error('Failed to load spec tree:', err);
      setSpecsError('Failed to load specifications folder. Make sure the project specs folder is accessible.');
    } finally {
      setIsLoadingSpecs(false);
    }
  };

  // Toggle spec file selection
  const handleToggleFile = useCallback((path: string) => {
    setSelectedSpecPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
    setHasSpecChanges(true);
  }, []);

  // Toggle folder expansion
  const handleToggleFolder = useCallback((folder: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev);
      if (next.has(folder)) {
        next.delete(folder);
      } else {
        next.add(folder);
      }
      return next;
    });
  }, []);

  // Filter specs by search query
  const filteredSpecFiles = useMemo(() => {
    if (!specSearchQuery.trim()) return allSpecFiles;
    const q = specSearchQuery.toLowerCase();
    return allSpecFiles.filter(f => f.name.toLowerCase().includes(q) || (f.folder || '').toLowerCase().includes(q));
  }, [allSpecFiles, specSearchQuery]);

  // Get root-level folders (no parent)
  const rootFolders = useMemo(() => {
    return allFolders.filter(f => !f.includes('/'));
  }, [allFolders]);

  // Format file size
  const formatSize = useCallback((bytes: number): string => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }, []);

  // Regenerate response with updated specs
  const handleRegenerate = async () => {
    const specPaths = Array.from(selectedSpecPaths);
    if (specPaths.length === 0) {
      setRegenerateError('Please select at least one specification file first.');
      return;
    }

    setIsRegenerating(true);
    setRegenerateError(null);
    try {
      const response = await refineResult(
        result.id,
        specPaths,
        userInstructions.trim() || undefined
      );
      setDraftText(response.response_text);
      setHasSpecChanges(false);
    } catch (err) {
      console.error('Failed to regenerate:', err);
      setRegenerateError(
        err instanceof Error ? err.message : 'Failed to regenerate response. Please try again.'
      );
    } finally {
      setIsRegenerating(false);
    }
  };

  // Save the final response
  const saveMutation = useMutation({
    mutationFn: () => updateResult(result.id, { response_text: draftText }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['results', projectId] });
      onSave();
    },
  });

  const handleSave = () => {
    saveMutation.mutate();
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-gradient-to-r from-violet-600 to-purple-600">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Refine Response</h2>
              <p className="text-sm text-white/80 truncate max-w-md">{result.source_file?.filename || result.source_filename || 'Unknown'}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-white/80 hover:text-white hover:bg-white/10 rounded-lg transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Step Indicator */}
        <div className="px-6 py-4 bg-slate-50 border-b border-slate-200">
          <div className="flex items-center justify-between">
            {steps.map((step, index) => (
              <div key={step.id} className="flex items-center">
                <button
                  onClick={() => setCurrentStep(step.id)}
                  className={`flex items-center gap-2 ${
                    index <= currentStepIndex ? 'text-violet-600' : 'text-slate-400'
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      index < currentStepIndex
                        ? 'bg-violet-600 text-white'
                        : index === currentStepIndex
                        ? 'bg-violet-100 text-violet-600 ring-2 ring-violet-600'
                        : 'bg-slate-200 text-slate-500'
                    }`}
                  >
                    {index < currentStepIndex ? (
                      <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                      </svg>
                    ) : (
                      index + 1
                    )}
                  </div>
                  <span className="hidden sm:inline text-sm font-medium">{step.label}</span>
                </button>
                {index < steps.length - 1 && (
                  <div
                    className={`w-12 h-0.5 mx-2 ${
                      index < currentStepIndex ? 'bg-violet-600' : 'bg-slate-200'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Step 1: Review */}
          {currentStep === 'review' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Current Response</h3>
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      isRFI ? 'bg-blue-100 text-blue-700' : 'bg-indigo-100 text-indigo-700'
                    }`}>
                      {isRFI ? 'RFI' : 'Submittal'}
                    </span>
                    <span className="text-sm text-slate-600">{result.source_file?.filename || result.source_filename || 'Unknown'}</span>
                    <span className="text-xs text-slate-400 ml-auto">
                      Confidence: {(result.confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              </div>

              {/* Current AI Response */}
              {result.response_text && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">AI Response</h4>
                  <div className="bg-white rounded-lg p-4 border border-slate-200 max-h-64 overflow-y-auto">
                    <p className="text-sm text-slate-800 whitespace-pre-wrap leading-relaxed">{result.response_text}</p>
                  </div>
                </div>
              )}

              {/* Existing spec references */}
              {result.spec_references && result.spec_references.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">
                    Specification References ({result.spec_references.length})
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {result.spec_references.map((ref, idx) => (
                      <span key={idx} className="inline-flex items-center px-3 py-1.5 bg-spec-50 text-spec-700 rounded-lg text-sm border border-spec-200">
                        <svg className="w-3.5 h-3.5 mr-1.5 text-spec-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                        </svg>
                        {ref.source_filename}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {result.consultant_type && (
                <div className="p-3 bg-orange-50 border border-orange-200 rounded-lg">
                  <div className="flex items-center text-sm text-orange-800">
                    <svg className="w-4 h-4 mr-2 text-orange-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                    </svg>
                    Recommend referral to: <strong className="ml-1">{result.consultant_type}</strong> consultant
                  </div>
                </div>
              )}

              <div className="p-4 bg-violet-50 border border-violet-200 rounded-xl">
                <p className="text-sm text-violet-700">
                  <strong>Next:</strong> Edit your specification file selections, then regenerate the AI response with updated context.
                </p>
              </div>
            </div>
          )}

          {/* Step 2: Specifications */}
          {currentStep === 'specs' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 mb-1">Edit Specification Files</h3>
                <p className="text-sm text-slate-600">
                  Add or remove spec files to influence the AI response. Changes here will be used when you regenerate in the next step.
                </p>
              </div>

              {isLoadingSpecs && (
                <div className="flex items-center justify-center py-12">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-slate-300 border-t-violet-600 mr-3" />
                  <span className="text-slate-500">Loading specifications folder...</span>
                </div>
              )}

              {specsError && (
                <div className="p-4 bg-red-50 text-red-700 rounded-xl border border-red-200">
                  <p className="text-sm">{specsError}</p>
                  <button
                    onClick={loadSpecFolderTree}
                    className="mt-2 text-sm font-medium text-red-600 hover:text-red-800 underline"
                  >
                    Retry
                  </button>
                </div>
              )}

              {specsLoaded && (
                <>
                  {/* Selection summary */}
                  <div className="flex items-center justify-between bg-slate-50 rounded-lg px-4 py-3 border border-slate-200">
                    <div className="flex items-center gap-3">
                      <span className="text-sm text-slate-600">
                        <strong className="text-violet-600">{selectedSpecPaths.size}</strong> of {allSpecFiles.length} specs selected
                      </span>
                      {hasSpecChanges && (
                        <span className="inline-flex items-center px-2 py-0.5 bg-amber-100 text-amber-700 rounded text-xs font-medium">
                          Modified
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setSelectedSpecPaths(new Set());
                          setHasSpecChanges(true);
                        }}
                        className="text-xs text-slate-500 hover:text-slate-700 font-medium"
                      >
                        Clear all
                      </button>
                    </div>
                  </div>

                  {/* Search */}
                  <div className="relative">
                    <svg className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                    <input
                      type="text"
                      value={specSearchQuery}
                      onChange={(e) => setSpecSearchQuery(e.target.value)}
                      placeholder="Search spec files..."
                      className="w-full pl-10 pr-4 py-2.5 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 focus:border-violet-500"
                    />
                  </div>

                  {/* Folder tree or search results */}
                  <div className="border border-slate-200 rounded-lg max-h-[45vh] overflow-y-auto bg-white">
                    {specSearchQuery.trim() ? (
                      // Flat search results
                      filteredSpecFiles.length === 0 ? (
                        <div className="p-6 text-center text-sm text-slate-400">No files match your search.</div>
                      ) : (
                        filteredSpecFiles.map(file => (
                          <SpecFileRow
                            key={file.path}
                            file={file}
                            isSelected={selectedSpecPaths.has(file.path)}
                            onToggle={handleToggleFile}
                            formatSize={formatSize}
                            depth={0}
                            showFolder
                          />
                        ))
                      )
                    ) : (
                      // Folder tree view
                      <>
                        {/* Root-level files (not in any subfolder) */}
                        {allSpecFiles
                          .filter(f => !f.folder || f.folder === '')
                          .map(file => (
                            <SpecFileRow
                              key={file.path}
                              file={file}
                              isSelected={selectedSpecPaths.has(file.path)}
                              onToggle={handleToggleFile}
                              formatSize={formatSize}
                              depth={0}
                            />
                          ))}

                        {/* Folder tree */}
                        {rootFolders.map(folder => {
                          const childFolders = allFolders.filter(f => {
                            if (!f.startsWith(folder + '/')) return false;
                            const remainder = f.slice(folder.length + 1);
                            return !remainder.includes('/');
                          });
                          const filesInFolder = allSpecFiles.filter(f => (f.folder || '') === folder);
                          const selectedCount = allSpecFiles.filter(f => 
                            ((f.folder || '').startsWith(folder)) && selectedSpecPaths.has(f.path)
                          ).length;
                          const totalCount = allSpecFiles.filter(f => (f.folder || '').startsWith(folder)).length;
                          
                          return (
                            <SpecFolderTreeNode
                              key={folder}
                              folder={folder}
                              childFolders={childFolders}
                              filesInFolder={filesInFolder}
                              selectedSpecs={selectedSpecPaths}
                              isExpanded={expandedFolders.has(folder)}
                              selectedCount={selectedCount}
                              totalCount={totalCount}
                              onToggleFolder={handleToggleFolder}
                              onToggleFile={handleToggleFile}
                              formatSize={formatSize}
                              depth={0}
                              allFolders={allFolders}
                              allFiles={allSpecFiles}
                              expandedFolders={expandedFolders}
                            />
                          );
                        })}
                      </>
                    )}
                  </div>
                </>
              )}
            </div>
          )}

          {/* Step 3: Refine */}
          {currentStep === 'refine' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">Refine Response</h3>
                  <p className="text-sm text-slate-600">
                    Regenerate with AI using your updated specs, or manually edit the text below.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleRegenerate}
                    disabled={isRegenerating}
                    className="px-4 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
                  >
                    {isRegenerating ? (
                      <>
                        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Regenerating...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                        Regenerate
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Spec summary for context */}
              <div className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-slate-500 uppercase tracking-wide">Spec files used</span>
                  <button
                    onClick={() => setCurrentStep('specs')}
                    className="text-xs text-violet-600 hover:text-violet-800 font-medium"
                  >
                    Edit specs
                  </button>
                </div>
                {selectedSpecPaths.size > 0 ? (
                  <div className="flex flex-wrap gap-1.5 mt-1">
                    {Array.from(selectedSpecPaths).slice(0, 6).map(path => {
                      const name = path.split('/').pop() || path;
                      return (
                        <span key={path} className="px-2 py-0.5 bg-spec-100 text-spec-700 rounded text-xs">
                          {name}
                        </span>
                      );
                    })}
                    {selectedSpecPaths.size > 6 && (
                      <span className="px-2 py-0.5 bg-slate-200 text-slate-600 rounded text-xs">
                        +{selectedSpecPaths.size - 6} more
                      </span>
                    )}
                  </div>
                ) : (
                  <p className="text-xs text-slate-400 mt-1">No specs selected. Go to the Specifications step to add some.</p>
                )}
                {hasSpecChanges && (
                  <p className="text-xs text-amber-600 mt-2">
                    Spec selections have changed. Click "Regenerate" to get an updated AI response.
                  </p>
                )}
              </div>

              {/* Instructions for AI */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1.5">
                  Instructions for AI <span className="font-normal text-slate-400">(optional)</span>
                </label>
                <textarea
                  value={userInstructions}
                  onChange={(e) => setUserInstructions(e.target.value)}
                  placeholder='e.g. "Focus on waterproofing requirements", "Be more concise", "Include specific section numbers"...'
                  className="w-full h-20 px-3 py-2 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-violet-500 focus:border-violet-500 resize-none"
                  disabled={isRegenerating}
                />
                <p className="text-xs text-slate-400 mt-1">
                  Guide the AI on how to approach the response. These instructions are sent alongside the document and specs.
                </p>
              </div>

              {regenerateError && (
                <div className="p-3 bg-red-50 text-red-700 rounded-lg border border-red-200 text-sm">
                  {regenerateError}
                </div>
              )}

              {isRegenerating && (
                <div className="p-4 bg-violet-50 border border-violet-200 rounded-xl">
                  <div className="flex items-center gap-3">
                    <div className="inline-block animate-spin rounded-full h-5 w-5 border-2 border-violet-300 border-t-violet-600" />
                    <div>
                      <p className="text-sm font-medium text-violet-800">Regenerating AI response...</p>
                      <p className="text-xs text-violet-600 mt-0.5">Parsing documents and analyzing with updated specifications</p>
                    </div>
                  </div>
                </div>
              )}

              <textarea
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                placeholder="Response text will appear here after generation, or type manually..."
                className="w-full h-64 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-violet-500 focus:border-violet-500 text-sm resize-none"
                disabled={isRegenerating}
              />
            </div>
          )}

          {/* Step 4: Finalize */}
          {currentStep === 'finalize' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">Final Review</h3>
                <p className="text-sm text-slate-600 mb-4">
                  Review your response before saving.
                </p>
              </div>

              <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                <h4 className="text-sm font-medium text-slate-700 mb-2">Response</h4>
                <p className="text-sm text-slate-900 whitespace-pre-wrap leading-relaxed">{draftText || '(No response drafted)'}</p>
              </div>

              {selectedSpecPaths.size > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Specifications Used ({selectedSpecPaths.size})</h4>
                  <div className="flex flex-wrap gap-2">
                    {Array.from(selectedSpecPaths).map((path, idx) => {
                      const name = path.split('/').pop() || path;
                      return (
                        <span key={idx} className="px-3 py-1 bg-spec-50 text-spec-700 rounded-full text-sm border border-spec-200">
                          {name}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}

              {draftText !== result.response_text && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-lg">
                  <p className="text-sm text-green-700 flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    The response has been modified from the original.
                  </p>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <div>
            {currentStepIndex > 0 && (
              <button
                onClick={() => setCurrentStep(steps[currentStepIndex - 1].id)}
                className="px-4 py-2 text-slate-600 hover:text-slate-800 text-sm font-medium"
              >
                &larr; Previous
              </button>
            )}
          </div>
          <div className="flex gap-3">
            <button
              onClick={onClose}
              className="px-4 py-2 text-slate-600 hover:text-slate-800 text-sm font-medium"
            >
              Cancel
            </button>
            {currentStep === 'finalize' ? (
              <button
                onClick={handleSave}
                disabled={!draftText || saveMutation.isPending}
                className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
              >
                {saveMutation.isPending ? (
                  <>
                    <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Saving...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Save Response
                  </>
                )}
              </button>
            ) : (
              <button
                onClick={() => setCurrentStep(steps[currentStepIndex + 1].id)}
                disabled={isRegenerating}
                className="px-6 py-2 bg-violet-600 text-white rounded-lg hover:bg-violet-700 text-sm font-medium disabled:opacity-50"
              >
                Next &rarr;
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}


// ---- Shared tree components (similar to SmartAnalysis) ----

interface SpecFolderTreeNodeProps {
  folder: string;
  childFolders: string[];
  filesInFolder: PathBasedSpecSuggestion[];
  selectedSpecs: Set<string>;
  isExpanded: boolean;
  selectedCount: number;
  totalCount: number;
  onToggleFolder: (folder: string) => void;
  onToggleFile: (path: string) => void;
  formatSize: (bytes: number) => string;
  depth: number;
  allFolders: string[];
  allFiles: PathBasedSpecSuggestion[];
  expandedFolders: Set<string>;
}

const SpecFolderTreeNode = memo(function SpecFolderTreeNode({
  folder,
  childFolders,
  filesInFolder,
  selectedSpecs,
  isExpanded,
  selectedCount,
  totalCount,
  onToggleFolder,
  onToggleFile,
  formatSize,
  depth,
  allFolders,
  allFiles,
  expandedFolders,
}: SpecFolderTreeNodeProps) {
  const folderName = folder.split('/').pop() || folder;
  
  const handleToggle = useCallback(() => {
    onToggleFolder(folder);
  }, [folder, onToggleFolder]);
  
  return (
    <div className="border-b border-stone-100 last:border-b-0">
      <button
        onClick={handleToggle}
        className="w-full flex items-center gap-2 px-3 py-2 hover:bg-stone-50 transition-colors text-left"
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        <svg
          className={`w-4 h-4 text-stone-400 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
        <svg className="w-4 h-4 text-amber-500" fill="currentColor" viewBox="0 0 24 24">
          <path d="M10 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V8a2 2 0 00-2-2h-8l-2-2z" />
        </svg>
        <span className="flex-1 text-sm font-medium text-stone-700">{folderName}</span>
        {selectedCount > 0 && (
          <span className="px-1.5 py-0.5 bg-violet-100 text-violet-700 text-xs rounded-full">
            {selectedCount}/{totalCount}
          </span>
        )}
        {selectedCount === 0 && totalCount > 0 && (
          <span className="text-xs text-stone-400">{totalCount} files</span>
        )}
      </button>
      
      {isExpanded && (
        <div>
          {filesInFolder.map(file => (
            <SpecFileRow
              key={file.path}
              file={file}
              isSelected={selectedSpecs.has(file.path)}
              onToggle={onToggleFile}
              formatSize={formatSize}
              depth={depth}
            />
          ))}
          
          {childFolders.map(childFolder => {
            const childChildFolders = allFolders.filter(f => {
              if (!f.startsWith(childFolder + '/')) return false;
              const remainder = f.slice(childFolder.length + 1);
              return !remainder.includes('/');
            });
            const childFilesInFolder = allFiles.filter(f => (f.folder || '') === childFolder);
            const childSelectedCount = allFiles.filter(f => 
              ((f.folder || '').startsWith(childFolder)) && selectedSpecs.has(f.path)
            ).length;
            const childTotalCount = allFiles.filter(f => (f.folder || '').startsWith(childFolder)).length;
            
            return (
              <SpecFolderTreeNode
                key={childFolder}
                folder={childFolder}
                childFolders={childChildFolders}
                filesInFolder={childFilesInFolder}
                selectedSpecs={selectedSpecs}
                isExpanded={expandedFolders.has(childFolder)}
                selectedCount={childSelectedCount}
                totalCount={childTotalCount}
                onToggleFolder={onToggleFolder}
                onToggleFile={onToggleFile}
                formatSize={formatSize}
                depth={depth + 1}
                allFolders={allFolders}
                allFiles={allFiles}
                expandedFolders={expandedFolders}
              />
            );
          })}
        </div>
      )}
    </div>
  );
});

const SpecFileRow = memo(function SpecFileRow({
  file,
  isSelected,
  onToggle,
  formatSize,
  depth,
  showFolder,
}: {
  file: PathBasedSpecSuggestion;
  isSelected: boolean;
  onToggle: (path: string) => void;
  formatSize: (bytes: number) => string;
  depth: number;
  showFolder?: boolean;
}) {
  const handleChange = useCallback(() => {
    onToggle(file.path);
  }, [file.path, onToggle]);
  
  return (
    <label
      className={`flex items-center gap-2 py-2 cursor-pointer hover:bg-stone-50 transition-colors text-sm ${
        isSelected ? 'bg-violet-50' : ''
      }`}
      style={{ paddingLeft: `${28 + depth * 16}px`, paddingRight: '12px' }}
    >
      <input
        type="checkbox"
        checked={isSelected}
        onChange={handleChange}
        className="w-3.5 h-3.5 rounded text-violet-600 focus:ring-violet-500"
      />
      <svg className="w-4 h-4 text-stone-400 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <span className="flex-1 truncate">{file.name}</span>
      {showFolder && file.folder && (
        <span className="text-xs text-stone-400 truncate max-w-[150px]">{file.folder}</span>
      )}
      <span className="text-xs text-stone-400 flex-shrink-0">{formatSize(file.size || 0)}</span>
    </label>
  );
});
