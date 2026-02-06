import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  browseProjectFolder,
  suggestSpecsFromPaths,
  smartAnalyzeFromPaths,
  type PathBasedSpecSuggestion,
  type PathBasedRfiSuggestions,
} from '../services/api';
import { Card, Button, Badge, Progress, StepProgress } from './ui';

interface SmartAnalysisProps {
  projectId: number;
  projectName?: string;
  onComplete?: () => void;
  onClose?: () => void;
}

type AnalysisStep = 'select' | 'suggest' | 'approve' | 'analyze' | 'complete';

export default function SmartAnalysis({
  projectId,
  projectName,
  onComplete,
  onClose,
}: SmartAnalysisProps) {
  const queryClient = useQueryClient();
  
  // Step tracking
  const [currentStep, setCurrentStep] = useState<AnalysisStep>('select');
  
  // RFI selection state - using file paths instead of IDs
  const [selectedRfiPaths, setSelectedRfiPaths] = useState<Set<string>>(new Set());
  
  // Spec suggestions state
  const [suggestions, setSuggestions] = useState<PathBasedRfiSuggestions[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  
  // Selected specs per RFI (keyed by RFI path)
  const [selectedSpecs, setSelectedSpecs] = useState<Map<string, Set<string>>>(new Map());
  
  // Analysis progress state
  const [analysisProgress, setAnalysisProgress] = useState<{
    message: string;
    currentRfi?: string;
    currentSpec?: string;
    completed: number;
    total: number;
    error?: string;
  }>({ message: '', completed: 0, total: 0 });
  
  const [analyzing, setAnalyzing] = useState(false);
  
  // Browse RFI files directly from filesystem (NO DATABASE REQUIRED!)
  const { data: rfiResponse, isLoading: rfiLoading } = useQuery({
    queryKey: ['browse', projectId, 'rfi'],
    queryFn: () => browseProjectFolder(projectId, 'rfi', true),
  });
  
  // Browse Submittal files directly from filesystem
  const { data: submittalResponse, isLoading: submittalLoading } = useQuery({
    queryKey: ['browse', projectId, 'submittal'],
    queryFn: () => browseProjectFolder(projectId, 'submittal', true),
  });
  
  // Combine RFIs and Submittals from filesystem
  const rfiFiles = rfiResponse?.files || [];
  const submittalFiles = submittalResponse?.files || [];
  
  // Filter to only show RFI and Submittal files based on filename patterns
  const allDocuments = [...rfiFiles, ...submittalFiles].filter(file => {
    const name = file.name.toLowerCase();
    return name.includes('rfi') || name.includes('submittal');
  });
  
  const isLoading = rfiLoading || submittalLoading;
  const folderError = rfiResponse?.error || submittalResponse?.error;
  
  // Toggle RFI selection
  const toggleRfi = (path: string) => {
    setSelectedRfiPaths(prev => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  };
  
  // Select all / none
  const selectAll = () => {
    setSelectedRfiPaths(new Set(allDocuments.map(f => f.path)));
  };
  
  const selectNone = () => {
    setSelectedRfiPaths(new Set());
  };
  
  // Request spec suggestions from AI
  const handleGetSuggestions = async () => {
    if (selectedRfiPaths.size === 0) return;
    
    setLoadingSuggestions(true);
    setCurrentStep('suggest');
    
    try {
      // Convert selected paths to the format the API expects
      const rfiFiles = Array.from(selectedRfiPaths).map(path => {
        const file = allDocuments.find(f => f.path === path);
        return {
          path,
          name: file?.name || path.split('/').pop() || path,
        };
      });
      
      const response = await suggestSpecsFromPaths(projectId, rfiFiles);
      
      if (response.error) {
        console.error('Suggest specs error:', response.error);
      }
      
      setSuggestions(response.suggestions);
      
      // Initialize selected specs with AI suggestions (top 5 for each)
      const initial = new Map<string, Set<string>>();
      response.suggestions.forEach(s => {
        const topSpecs = s.suggested_specs.slice(0, 5).map(sp => sp.path);
        initial.set(s.rfi_path, new Set(topSpecs));
      });
      setSelectedSpecs(initial);
      
      setCurrentStep('approve');
    } catch (err) {
      console.error('Failed to get suggestions:', err);
      setAnalysisProgress(prev => ({ ...prev, error: 'Failed to get spec suggestions' }));
    } finally {
      setLoadingSuggestions(false);
    }
  };
  
  // Toggle spec selection for an RFI
  const toggleSpec = (rfiPath: string, specPath: string) => {
    setSelectedSpecs(prev => {
      const next = new Map(prev);
      const current = next.get(rfiPath) || new Set();
      const updated = new Set(current);
      
      if (updated.has(specPath)) {
        updated.delete(specPath);
      } else {
        updated.add(specPath);
      }
      
      next.set(rfiPath, updated);
      return next;
    });
  };
  
  // Select/deselect all specs for an RFI
  const toggleAllSpecs = (rfiPath: string, specs: PathBasedSpecSuggestion[], select: boolean) => {
    setSelectedSpecs(prev => {
      const next = new Map(prev);
      if (select) {
        next.set(rfiPath, new Set(specs.map(s => s.path)));
      } else {
        next.set(rfiPath, new Set());
      }
      return next;
    });
  };
  
  // Start the smart analysis
  const handleStartAnalysis = async () => {
    setCurrentStep('analyze');
    setAnalyzing(true);
    
    // Build analysis request using file paths
    const analyses = suggestions.map(s => ({
      rfi_path: s.rfi_path,
      rfi_name: s.rfi_filename,
      spec_file_paths: Array.from(selectedSpecs.get(s.rfi_path) || []),
    })).filter(a => a.spec_file_paths.length > 0);
    
    if (analyses.length === 0) {
      setAnalysisProgress({ message: 'No specs selected', completed: 0, total: 0 });
      setAnalyzing(false);
      return;
    }
    
    setAnalysisProgress({
      message: 'Starting analysis...',
      completed: 0,
      total: analyses.length,
    });
    
    try {
      // Process each RFI one by one and update progress
      for (let i = 0; i < analyses.length; i++) {
        const analysis = analyses[i];
        
        setAnalysisProgress(prev => ({
          ...prev,
          message: `Analyzing ${analysis.rfi_name}...`,
          currentRfi: analysis.rfi_name,
          currentSpec: `Parsing ${analysis.spec_file_paths.length} spec files...`,
          completed: i,
        }));
        
        // Make API call for this single RFI
        try {
          await smartAnalyzeFromPaths(projectId, { analyses: [analysis] });
          
          setAnalysisProgress(prev => ({
            ...prev,
            completed: i + 1,
            message: `Completed ${i + 1} of ${analyses.length}`,
          }));
        } catch (err) {
          console.error(`Error analyzing ${analysis.rfi_name}:`, err);
        }
      }
      
      // All done
      setAnalysisProgress(prev => ({
        ...prev,
        message: 'Analysis complete!',
        completed: analyses.length,
        currentRfi: undefined,
        currentSpec: undefined,
      }));
      
      setCurrentStep('complete');
      queryClient.invalidateQueries({ queryKey: ['results', projectId] });
      
    } catch (err) {
      console.error('Analysis failed:', err);
      setAnalysisProgress(prev => ({
        ...prev,
        error: 'Analysis failed. Please try again.',
      }));
    } finally {
      setAnalyzing(false);
    }
  };
  
  // Cancel analysis
  const handleCancel = () => {
    setCurrentStep('approve');
    setAnalyzing(false);
    setAnalysisProgress({ message: '', completed: 0, total: 0 });
  };
  
  // Finish and close
  const handleFinish = () => {
    onComplete?.();
    onClose?.();
  };
  
  // Get step index for StepProgress
  const stepIndex = {
    select: 0,
    suggest: 0,
    approve: 1,
    analyze: 2,
    complete: 3,
  }[currentStep];
  
  // Determine file type from filename
  const getFileType = (filename: string): 'rfi' | 'submittal' => {
    return filename.toLowerCase().includes('submittal') ? 'submittal' : 'rfi';
  };
  
  // Format file size
  const formatSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  
  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-stone-200 bg-gradient-to-r from-primary-50 to-primary-100">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-stone-900 flex items-center gap-2">
                <svg className="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
                Smart Analysis
              </h2>
              <p className="text-sm text-stone-500 mt-1">
                {projectName ? `Project: ${projectName}` : 'AI-powered document analysis'}
              </p>
            </div>
            <button
              onClick={onClose}
              className="p-2 text-stone-400 hover:text-stone-600 hover:bg-stone-100 rounded-lg transition"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          
          {/* Progress Steps */}
          <div className="mt-4">
            <StepProgress
              steps={[
                { id: 'select', label: 'Select Documents' },
                { id: 'approve', label: 'Review Specs' },
                { id: 'analyze', label: 'Analyze' },
                { id: 'complete', label: 'Done' },
              ]}
              currentStep={stepIndex}
            />
          </div>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Step 1: Select RFIs/Submittals */}
          {currentStep === 'select' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="font-medium text-stone-900">Select Documents to Analyze</h3>
                  <p className="text-sm text-stone-500">
                    Choose the RFIs or Submittals you want to generate responses for
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={selectAll}
                    className="text-sm text-primary-600 hover:text-primary-700 font-medium"
                  >
                    Select All
                  </button>
                  <span className="text-stone-300">|</span>
                  <button
                    onClick={selectNone}
                    className="text-sm text-stone-500 hover:text-stone-700 font-medium"
                  >
                    Clear
                  </button>
                </div>
              </div>
              
              {isLoading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-stone-300 border-t-primary-600" />
                  <p className="text-stone-500 mt-2">Loading documents from folder...</p>
                </div>
              ) : folderError ? (
                <div className="text-center py-12 bg-amber-50 rounded-xl border border-amber-200">
                  <svg className="w-12 h-12 mx-auto text-amber-500 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                  <p className="text-amber-800 font-medium">Folder Configuration Needed</p>
                  <p className="text-sm text-amber-600 mt-1">{folderError}</p>
                  <p className="text-xs text-amber-500 mt-2">
                    Please configure your project's RFI folder path in project settings.
                  </p>
                </div>
              ) : allDocuments.length === 0 ? (
                <div className="text-center py-12 bg-stone-50 rounded-xl">
                  <svg className="w-12 h-12 mx-auto text-stone-400 mb-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                  <p className="text-stone-500 font-medium">No RFIs or Submittals found</p>
                  <p className="text-sm text-stone-400 mt-1">
                    Make sure your project folder contains files with "RFI" or "Submittal" in the filename.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2 max-h-[400px] overflow-y-auto">
                  {allDocuments.map(file => (
                    <label
                      key={file.path}
                      className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition ${
                        selectedRfiPaths.has(file.path)
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-stone-200 hover:border-stone-300 bg-white'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedRfiPaths.has(file.path)}
                        onChange={() => toggleRfi(file.path)}
                        className="w-4 h-4 rounded text-primary-600 focus:ring-primary-500"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-stone-900 truncate">{file.name}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge 
                            variant={getFileType(file.name)} 
                            size="sm"
                          >
                            {getFileType(file.name).toUpperCase()}
                          </Badge>
                          <span className="text-xs text-stone-400">
                            {file.extension.toUpperCase().replace('.', '')} • {formatSize(file.size)}
                          </span>
                        </div>
                      </div>
                      {selectedRfiPaths.has(file.path) && (
                        <svg className="w-5 h-5 text-primary-600 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd" />
                        </svg>
                      )}
                    </label>
                  ))}
                </div>
              )}
              
              <div className="pt-4 border-t border-stone-200 flex justify-between items-center">
                <p className="text-sm text-stone-500">
                  {selectedRfiPaths.size} of {allDocuments.length} selected
                </p>
                <Button
                  variant="primary"
                  onClick={handleGetSuggestions}
                  disabled={selectedRfiPaths.size === 0 || loadingSuggestions}
                  loading={loadingSuggestions}
                >
                  {loadingSuggestions ? 'Finding specs...' : 'Find Related Specs'}
                </Button>
              </div>
            </div>
          )}
          
          {/* Step 2: Review and approve spec suggestions */}
          {(currentStep === 'suggest' || currentStep === 'approve') && (
            <div className="space-y-6">
              {loadingSuggestions ? (
                <div className="text-center py-12">
                  <div className="inline-block animate-spin rounded-full h-10 w-10 border-2 border-stone-300 border-t-primary-600" />
                  <p className="text-stone-700 font-medium mt-4">AI is finding relevant specifications...</p>
                  <p className="text-sm text-stone-500 mt-1">Analyzing document keywords and references</p>
                </div>
              ) : (
                <>
                  <div className="flex items-center justify-between">
                    <div>
                      <h3 className="font-medium text-stone-900">Review Suggested Specs</h3>
                      <p className="text-sm text-stone-500">
                        AI found specifications that may be relevant. Adjust selections as needed.
                      </p>
                    </div>
                    <button
                      onClick={() => setCurrentStep('select')}
                      className="text-sm text-stone-500 hover:text-stone-700"
                    >
                      ← Back to selection
                    </button>
                  </div>
                  
                  {suggestions.length === 0 ? (
                    <div className="text-center py-12 bg-amber-50 rounded-xl">
                      <p className="text-amber-800">No specs folder configured or no spec files found.</p>
                      <p className="text-sm text-amber-600 mt-1">
                        Please configure your project's Specs folder path.
                      </p>
                    </div>
                  ) : (
                    suggestions.map(suggestion => (
                      <Card key={suggestion.rfi_path} className="border-l-4 border-l-primary-500">
                        <div className="space-y-4">
                          {/* RFI header */}
                          <div className="flex items-start justify-between">
                            <div>
                              <Badge variant={getFileType(suggestion.rfi_filename)} className="mb-2">
                                {getFileType(suggestion.rfi_filename).toUpperCase()}
                              </Badge>
                              <h4 className="font-medium text-stone-900">{suggestion.rfi_filename}</h4>
                              {suggestion.rfi_title && (
                                <p className="text-sm text-stone-500 mt-1">{suggestion.rfi_title}</p>
                              )}
                            </div>
                            <div className="text-right">
                              <p className="text-sm text-stone-500">
                                {suggestion.suggested_specs.length} specs found
                              </p>
                              <p className="text-xs text-stone-400">
                                {selectedSpecs.get(suggestion.rfi_path)?.size || 0} selected
                              </p>
                            </div>
                          </div>
                          
                          {/* Keywords found */}
                          {suggestion.extracted_keywords.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {suggestion.extracted_keywords.slice(0, 8).map((kw, i) => (
                                <span key={i} className="px-2 py-0.5 bg-stone-100 text-stone-600 text-xs rounded-full">
                                  {kw}
                                </span>
                              ))}
                            </div>
                          )}
                          
                          {/* Spec suggestions */}
                          <div>
                            <div className="flex items-center justify-between mb-2">
                              <span className="text-sm font-medium text-stone-700">Suggested Specifications</span>
                              <div className="flex gap-2">
                                <button
                                  onClick={() => toggleAllSpecs(suggestion.rfi_path, suggestion.suggested_specs, true)}
                                  className="text-xs text-primary-600 hover:text-primary-700"
                                >
                                  Select All
                                </button>
                                <button
                                  onClick={() => toggleAllSpecs(suggestion.rfi_path, suggestion.suggested_specs, false)}
                                  className="text-xs text-stone-500 hover:text-stone-700"
                                >
                                  Clear
                                </button>
                              </div>
                            </div>
                            
                            <div className="grid grid-cols-1 gap-1 max-h-48 overflow-y-auto">
                              {suggestion.suggested_specs.map((spec) => (
                                <label
                                  key={spec.path}
                                  className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition text-sm ${
                                    selectedSpecs.get(suggestion.rfi_path)?.has(spec.path)
                                      ? 'border-spec-500 bg-spec-50'
                                      : 'border-stone-200 hover:border-stone-300'
                                  }`}
                                >
                                  <input
                                    type="checkbox"
                                    checked={selectedSpecs.get(suggestion.rfi_path)?.has(spec.path) || false}
                                    onChange={() => toggleSpec(suggestion.rfi_path, spec.path)}
                                    className="w-3.5 h-3.5 rounded text-spec-600 focus:ring-spec-500"
                                  />
                                  <div className="flex-1 min-w-0">
                                    <p className="font-medium text-stone-800 truncate">{spec.name}</p>
                                    {spec.matched_terms.length > 0 && (
                                      <p className="text-xs text-stone-500 truncate">
                                        Matched: {spec.matched_terms.join(', ')}
                                      </p>
                                    )}
                                  </div>
                                  <Badge variant="spec" size="sm">
                                    {Math.round(spec.relevance_score)}
                                  </Badge>
                                </label>
                              ))}
                            </div>
                            
                            {suggestion.suggested_specs.length === 0 && (
                              <p className="text-sm text-stone-400 text-center py-4">
                                No matching specs found. Make sure your Specs folder is configured.
                              </p>
                            )}
                          </div>
                        </div>
                      </Card>
                    ))
                  )}
                  
                  <div className="pt-4 border-t border-stone-200 flex justify-between items-center">
                    <p className="text-sm text-stone-500">
                      Ready to analyze {suggestions.filter(s => (selectedSpecs.get(s.rfi_path)?.size || 0) > 0).length} documents
                    </p>
                    <Button
                      variant="primary"
                      onClick={handleStartAnalysis}
                      disabled={Array.from(selectedSpecs.values()).every(set => set.size === 0)}
                    >
                      Start Analysis
                    </Button>
                  </div>
                </>
              )}
            </div>
          )}
          
          {/* Step 3: Analysis in progress */}
          {currentStep === 'analyze' && (
            <div className="space-y-6 py-8">
              <div className="text-center">
                <div className="inline-block animate-spin rounded-full h-12 w-12 border-3 border-stone-300 border-t-primary-600 mb-4" />
                <h3 className="text-lg font-medium text-stone-900">Analyzing Documents</h3>
                <p className="text-stone-500 mt-1">{analysisProgress.message}</p>
              </div>
              
              <div className="max-w-md mx-auto">
                <div className="flex justify-between text-xs text-stone-500 mb-2">
                  <span>Progress</span>
                  <span>{analysisProgress.completed} of {analysisProgress.total}</span>
                </div>
                <Progress
                  value={(analysisProgress.completed / Math.max(analysisProgress.total, 1)) * 100}
                  size="lg"
                  variant="default"
                />
              </div>
              
              {analysisProgress.currentRfi && (
                <div className="bg-stone-50 rounded-xl p-4 max-w-md mx-auto text-center">
                  <p className="text-sm text-stone-600">
                    <span className="font-medium">Current:</span> {analysisProgress.currentRfi}
                  </p>
                  {analysisProgress.currentSpec && (
                    <p className="text-xs text-stone-500 mt-1">
                      {analysisProgress.currentSpec}
                    </p>
                  )}
                </div>
              )}
              
              {analysisProgress.error && (
                <div className="bg-red-50 text-red-700 p-4 rounded-xl text-center">
                  {analysisProgress.error}
                </div>
              )}
              
              <div className="text-center">
                <Button variant="ghost" onClick={handleCancel} disabled={!analyzing}>
                  Cancel
                </Button>
              </div>
            </div>
          )}
          
          {/* Step 4: Complete */}
          {currentStep === 'complete' && (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto rounded-full bg-spec-100 flex items-center justify-center mb-4">
                <svg className="w-8 h-8 text-spec-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h3 className="text-xl font-semibold text-stone-900 mb-2">Analysis Complete!</h3>
              <p className="text-stone-500 mb-6">
                Successfully analyzed {analysisProgress.completed} of {analysisProgress.total} documents.
              </p>
              <div className="flex justify-center gap-3">
                <Button variant="secondary" onClick={() => setCurrentStep('select')}>
                  Analyze More
                </Button>
                <Button variant="primary" onClick={handleFinish}>
                  View Results
                </Button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
