import { useState, useRef } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import {
  getProjectFiles,
  suggestSpecs,
  smartAnalyzeStream,
  type SpecSuggestion,
  type RfiSpecSuggestions,
  type SmartAnalysisProgressEvent,
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
  
  // RFI selection state
  const [selectedRfiIds, setSelectedRfiIds] = useState<Set<number>>(new Set());
  
  // Spec suggestions state
  const [suggestions, setSuggestions] = useState<RfiSpecSuggestions[]>([]);
  const [loadingSuggestions, setLoadingSuggestions] = useState(false);
  
  // Selected specs per RFI
  const [selectedSpecs, setSelectedSpecs] = useState<Map<number, Set<string>>>(new Map());
  
  // Analysis progress state
  const [analysisProgress, setAnalysisProgress] = useState<{
    message: string;
    currentRfi?: string;
    currentSpec?: string;
    completed: number;
    total: number;
  }>({ message: '', completed: 0, total: 0 });
  
  const streamRef = useRef<{ cancel: () => void } | null>(null);
  
  // Fetch RFI files
  const { data: rfiFiles = [], isLoading: rfiLoading } = useQuery({
    queryKey: ['files', projectId, 'rfi'],
    queryFn: () => getProjectFiles(projectId, 'rfi'),
  });
  
  const { data: submittalFiles = [] } = useQuery({
    queryKey: ['files', projectId, 'submittal'],
    queryFn: () => getProjectFiles(projectId, 'submittal'),
  });
  
  // Combine RFIs and Submittals for selection
  const allDocuments = [...rfiFiles, ...submittalFiles];
  
  // Toggle RFI selection
  const toggleRfi = (id: number) => {
    setSelectedRfiIds(prev => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };
  
  // Select all / none
  const selectAll = () => {
    setSelectedRfiIds(new Set(allDocuments.map(f => f.id)));
  };
  
  const selectNone = () => {
    setSelectedRfiIds(new Set());
  };
  
  // Request spec suggestions from AI
  const handleGetSuggestions = async () => {
    if (selectedRfiIds.size === 0) return;
    
    setLoadingSuggestions(true);
    setCurrentStep('suggest');
    
    try {
      const response = await suggestSpecs(projectId, Array.from(selectedRfiIds));
      setSuggestions(response.suggestions);
      
      // Initialize selected specs with AI suggestions (top 5 for each)
      const initial = new Map<number, Set<string>>();
      response.suggestions.forEach(s => {
        const topSpecs = s.suggested_specs.slice(0, 5).map(sp => sp.path);
        initial.set(s.rfi_id, new Set(topSpecs));
      });
      setSelectedSpecs(initial);
      
      setCurrentStep('approve');
    } catch (err) {
      console.error('Failed to get suggestions:', err);
    } finally {
      setLoadingSuggestions(false);
    }
  };
  
  // Toggle spec selection for an RFI
  const toggleSpec = (rfiId: number, specPath: string) => {
    setSelectedSpecs(prev => {
      const next = new Map(prev);
      const current = next.get(rfiId) || new Set();
      const updated = new Set(current);
      
      if (updated.has(specPath)) {
        updated.delete(specPath);
      } else {
        updated.add(specPath);
      }
      
      next.set(rfiId, updated);
      return next;
    });
  };
  
  // Select/deselect all specs for an RFI
  const toggleAllSpecs = (rfiId: number, specs: SpecSuggestion[], select: boolean) => {
    setSelectedSpecs(prev => {
      const next = new Map(prev);
      if (select) {
        next.set(rfiId, new Set(specs.map(s => s.path)));
      } else {
        next.set(rfiId, new Set());
      }
      return next;
    });
  };
  
  // Start the smart analysis
  const handleStartAnalysis = () => {
    setCurrentStep('analyze');
    
    // Build analysis request
    const analyses = suggestions.map(s => ({
      rfi_file_id: s.rfi_id,
      spec_file_paths: Array.from(selectedSpecs.get(s.rfi_id) || []),
    })).filter(a => a.spec_file_paths.length > 0);
    
    if (analyses.length === 0) {
      setAnalysisProgress({ message: 'No specs selected', completed: 0, total: 0 });
      return;
    }
    
    setAnalysisProgress({
      message: 'Starting analysis...',
      completed: 0,
      total: analyses.length,
    });
    
    streamRef.current = smartAnalyzeStream(
      projectId,
      { analyses },
      (event: SmartAnalysisProgressEvent) => {
        switch (event.event_type) {
          case 'start':
            setAnalysisProgress(prev => ({
              ...prev,
              message: event.message,
              total: event.total || prev.total,
            }));
            break;
            
          case 'parsing':
            setAnalysisProgress(prev => ({
              ...prev,
              message: event.message,
              currentRfi: event.rfi_filename,
            }));
            break;
            
          case 'parsing_spec':
            setAnalysisProgress(prev => ({
              ...prev,
              message: event.message,
              currentSpec: event.spec_name,
            }));
            break;
            
          case 'generating':
            setAnalysisProgress(prev => ({
              ...prev,
              message: event.message,
              currentRfi: event.rfi_filename,
              currentSpec: undefined,
            }));
            break;
            
          case 'completed':
            setAnalysisProgress(prev => ({
              ...prev,
              message: event.message,
              completed: (event.current_index || 0),
            }));
            break;
            
          case 'done':
            setAnalysisProgress(prev => ({
              ...prev,
              message: event.message,
              completed: event.completed || prev.total,
            }));
            setCurrentStep('complete');
            queryClient.invalidateQueries({ queryKey: ['results', projectId] });
            break;
            
          case 'error':
          case 'fatal_error':
            setAnalysisProgress(prev => ({
              ...prev,
              message: `Error: ${event.error || event.message}`,
            }));
            break;
        }
      }
    );
  };
  
  // Cancel analysis
  const handleCancel = () => {
    if (streamRef.current) {
      streamRef.current.cancel();
      streamRef.current = null;
    }
    setCurrentStep('approve');
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
              
              {rfiLoading ? (
                <div className="text-center py-8">
                  <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-stone-300 border-t-primary-600" />
                  <p className="text-stone-500 mt-2">Loading documents...</p>
                </div>
              ) : allDocuments.length === 0 ? (
                <div className="text-center py-12 bg-stone-50 rounded-xl">
                  <p className="text-stone-500">No RFIs or Submittals found</p>
                  <p className="text-sm text-stone-400 mt-1">Scan your project folders first</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-2 max-h-[400px] overflow-y-auto">
                  {allDocuments.map(file => (
                    <label
                      key={file.id}
                      className={`flex items-center gap-3 p-3 rounded-xl border-2 cursor-pointer transition ${
                        selectedRfiIds.has(file.id)
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-stone-200 hover:border-stone-300 bg-white'
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={selectedRfiIds.has(file.id)}
                        onChange={() => toggleRfi(file.id)}
                        className="w-4 h-4 rounded text-primary-600 focus:ring-primary-500"
                      />
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-stone-900 truncate">{file.filename}</p>
                        <div className="flex items-center gap-2 mt-1">
                          <Badge 
                            variant={file.content_type === 'rfi' ? 'rfi' : 'submittal'} 
                            size="sm"
                          >
                            {file.content_type?.toUpperCase()}
                          </Badge>
                          <span className="text-xs text-stone-400">
                            {file.file_type.toUpperCase()}
                          </span>
                          {!file.has_content && (
                            <span className="text-xs text-amber-600">Not parsed</span>
                          )}
                        </div>
                      </div>
                      {selectedRfiIds.has(file.id) && (
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
                  {selectedRfiIds.size} of {allDocuments.length} selected
                </p>
                <Button
                  variant="primary"
                  onClick={handleGetSuggestions}
                  disabled={selectedRfiIds.size === 0 || loadingSuggestions}
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
                  
                  {suggestions.map(suggestion => (
                    <Card key={suggestion.rfi_id} className="border-l-4 border-l-primary-500">
                      <div className="space-y-4">
                        {/* RFI header */}
                        <div className="flex items-start justify-between">
                          <div>
                            <Badge variant="rfi" className="mb-2">
                              {suggestion.rfi_filename.includes('Submittal') ? 'SUBMITTAL' : 'RFI'}
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
                              {selectedSpecs.get(suggestion.rfi_id)?.size || 0} selected
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
                                onClick={() => toggleAllSpecs(suggestion.rfi_id, suggestion.suggested_specs, true)}
                                className="text-xs text-primary-600 hover:text-primary-700"
                              >
                                Select All
                              </button>
                              <button
                                onClick={() => toggleAllSpecs(suggestion.rfi_id, suggestion.suggested_specs, false)}
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
                                  selectedSpecs.get(suggestion.rfi_id)?.has(spec.path)
                                    ? 'border-spec-500 bg-spec-50'
                                    : 'border-stone-200 hover:border-stone-300'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  checked={selectedSpecs.get(suggestion.rfi_id)?.has(spec.path) || false}
                                  onChange={() => toggleSpec(suggestion.rfi_id, spec.path)}
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
                                  {Math.round(spec.relevance_score * 10)}
                                </Badge>
                              </label>
                            ))}
                          </div>
                          
                          {suggestion.suggested_specs.length === 0 && (
                            <p className="text-sm text-stone-400 text-center py-4">
                              No matching specs found. Try adjusting keywords or manually selecting files.
                            </p>
                          )}
                        </div>
                      </div>
                    </Card>
                  ))}
                  
                  <div className="pt-4 border-t border-stone-200 flex justify-between items-center">
                    <p className="text-sm text-stone-500">
                      Ready to analyze {suggestions.filter(s => (selectedSpecs.get(s.rfi_id)?.size || 0) > 0).length} documents
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
                      Parsing: {analysisProgress.currentSpec}
                    </p>
                  )}
                </div>
              )}
              
              <div className="text-center">
                <Button variant="ghost" onClick={handleCancel}>
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
