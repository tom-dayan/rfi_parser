import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { sendChatMessage, updateResult } from '../services/api';
import type { ProcessingResultWithFile, ProjectFileSummary } from '../types';

interface CoPilotModeProps {
  result: ProcessingResultWithFile;
  specFiles: ProjectFileSummary[];
  projectId: number;
  projectName?: string;
  onClose: () => void;
  onSave: () => void;
}

type Step = 'review' | 'specs' | 'draft' | 'finalize';

export default function CoPilotMode({
  result,
  specFiles,
  projectId,
  projectName: _projectName,
  onClose,
  onSave,
}: CoPilotModeProps) {
  const [currentStep, setCurrentStep] = useState<Step>('review');
  const [draftText, setDraftText] = useState(result.response_text || '');
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedSpecs, setSelectedSpecs] = useState<string[]>(
    result.spec_references?.map(r => r.source_filename) || []
  );
  const queryClient = useQueryClient();

  const isRFI = result.document_type === 'rfi';

  const steps: { id: Step; label: string; description: string }[] = [
    { id: 'review', label: 'Review', description: 'Review the document and extracted questions' },
    { id: 'specs', label: 'Specifications', description: 'Select relevant specifications' },
    { id: 'draft', label: 'Draft', description: 'Generate and refine the response' },
    { id: 'finalize', label: 'Finalize', description: 'Review and save the final response' },
  ];

  const currentStepIndex = steps.findIndex(s => s.id === currentStep);

  // Generate or improve draft using AI
  const generateDraft = async (instruction: string) => {
    setIsGenerating(true);
    try {
      const response = await sendChatMessage({
        content: instruction,
        project_id: projectId,
      });
      
      // Extract the draft from the response
      setDraftText(response.content);
      
      // Generate suggestions for improvement
      const suggestionResponse = await sendChatMessage({
        content: `Based on this draft response, suggest 3 brief ways to improve it (one line each):\n\n${response.content}`,
        project_id: projectId,
      });
      
      // Parse suggestions (simple split by newlines)
      const suggestionLines = suggestionResponse.content
        .split('\n')
        .filter(line => line.trim().length > 0)
        .slice(0, 3);
      setSuggestions(suggestionLines);
      
    } catch (error) {
      console.error('Failed to generate draft:', error);
    } finally {
      setIsGenerating(false);
    }
  };

  // Apply a suggestion
  const applySuggestion = async (suggestion: string) => {
    setIsGenerating(true);
    try {
      const response = await sendChatMessage({
        content: `Improve this draft by applying this suggestion: "${suggestion}"\n\nCurrent draft:\n${draftText}`,
        project_id: projectId,
      });
      setDraftText(response.content);
      setSuggestions([]);
    } catch (error) {
      console.error('Failed to apply suggestion:', error);
    } finally {
      setIsGenerating(false);
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

  const handleGenerateInitialDraft = () => {
    const prompt = isRFI
      ? `Generate a professional response to this RFI. The document is titled "${result.source_file?.filename || result.source_filename || 'Unknown'}". Consider these specification references: ${selectedSpecs.join(', ')}. Be concise and reference specific sections.`
      : `Generate professional review comments for this submittal titled "${result.source_file?.filename || result.source_filename || 'Unknown'}". Consider these specification references: ${selectedSpecs.join(', ')}. Provide clear comments on compliance.`;
    
    generateDraft(prompt);
  };

  const handleRegenerateDraft = () => {
    const prompt = `Regenerate this ${isRFI ? 'RFI response' : 'submittal review'} with a different approach. Keep it professional and concise. Document: "${result.source_file?.filename || result.source_filename || 'Unknown'}".`;
    generateDraft(prompt);
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl max-w-4xl w-full max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-gradient-to-r from-purple-600 to-indigo-600">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-white/20 rounded-lg flex items-center justify-center">
              <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <div>
              <h2 className="text-lg font-semibold text-white">Co-Pilot Mode</h2>
              <p className="text-sm text-white/80">{result.source_file?.filename || result.source_filename || 'Unknown'}</p>
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
                    index <= currentStepIndex ? 'text-purple-600' : 'text-slate-400'
                  }`}
                >
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                      index < currentStepIndex
                        ? 'bg-purple-600 text-white'
                        : index === currentStepIndex
                        ? 'bg-purple-100 text-purple-600 ring-2 ring-purple-600'
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
                      index < currentStepIndex ? 'bg-purple-600' : 'bg-slate-200'
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
                <h3 className="text-lg font-semibold text-slate-900 mb-4">Document Review</h3>
                <div className="bg-slate-50 rounded-lg p-4 border border-slate-200">
                  <div className="flex items-center gap-2 mb-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      isRFI ? 'bg-blue-100 text-blue-700' : 'bg-indigo-100 text-indigo-700'
                    }`}>
                      {isRFI ? 'RFI' : 'Submittal'}
                    </span>
                    <span className="text-sm text-slate-600">{result.source_file?.filename || result.source_filename || 'Unknown'}</span>
                  </div>
                  <p className="text-sm text-slate-600">
                    Review the document details before proceeding to select relevant specifications.
                  </p>
                </div>
              </div>

              {/* Show existing AI analysis if available */}
              {result.response_text && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Previous AI Analysis</h4>
                  <div className="bg-amber-50 rounded-lg p-4 border border-amber-200">
                    <p className="text-sm text-amber-800">{result.response_text}</p>
                  </div>
                </div>
              )}

              {/* Existing spec references */}
              {result.spec_references && result.spec_references.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">
                    Found Specification References ({result.spec_references.length})
                  </h4>
                  <div className="space-y-2">
                    {result.spec_references.map((ref, idx) => (
                      <div key={idx} className="bg-slate-50 rounded-lg p-3 border border-slate-200">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium text-slate-900">{ref.source_filename}</span>
                          <span className="text-xs bg-blue-100 text-blue-700 px-2 py-0.5 rounded">
                            {(ref.score * 100).toFixed(0)}% match
                          </span>
                        </div>
                        {ref.section && (
                          <p className="text-xs text-slate-500 mt-1">Section: {ref.section}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Step 2: Specifications */}
          {currentStep === 'specs' && (
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-semibold text-slate-900 mb-2">Select Relevant Specifications</h3>
                <p className="text-sm text-slate-600 mb-4">
                  Choose which specification files should be referenced in the response.
                </p>
              </div>

              <div className="space-y-2 max-h-64 overflow-y-auto">
                {specFiles.map((file) => (
                  <label
                    key={file.id}
                    className="flex items-center gap-3 p-3 rounded-lg border border-slate-200 hover:bg-slate-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedSpecs.includes(file.filename)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedSpecs([...selectedSpecs, file.filename]);
                        } else {
                          setSelectedSpecs(selectedSpecs.filter(s => s !== file.filename));
                        }
                      }}
                      className="w-4 h-4 text-purple-600 rounded focus:ring-purple-500"
                    />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-slate-900">{file.filename}</p>
                      <p className="text-xs text-slate-500">{file.content_type}</p>
                    </div>
                    {result.spec_references?.some(r => r.source_filename === file.filename) && (
                      <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">
                        AI suggested
                      </span>
                    )}
                  </label>
                ))}
              </div>

              {specFiles.length === 0 && (
                <div className="text-center py-8 text-slate-500">
                  No specification files indexed. Index your specs first.
                </div>
              )}
            </div>
          )}

          {/* Step 3: Draft */}
          {currentStep === 'draft' && (
            <div className="space-y-6">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-slate-900 mb-1">Draft Response</h3>
                  <p className="text-sm text-slate-600">
                    Generate and refine your {isRFI ? 'RFI response' : 'submittal review'}.
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleGenerateInitialDraft}
                    disabled={isGenerating}
                    className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50 text-sm font-medium flex items-center gap-2"
                  >
                    {isGenerating ? (
                      <>
                        <svg className="animate-spin w-4 h-4" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Generating...
                      </>
                    ) : (
                      <>
                        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                        </svg>
                        Generate
                      </>
                    )}
                  </button>
                  {draftText && (
                    <button
                      onClick={handleRegenerateDraft}
                      disabled={isGenerating}
                      className="px-4 py-2 bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200 disabled:opacity-50 text-sm font-medium"
                    >
                      Regenerate
                    </button>
                  )}
                </div>
              </div>

              <textarea
                value={draftText}
                onChange={(e) => setDraftText(e.target.value)}
                placeholder="Click 'Generate' to create an initial draft, or type your response here..."
                className="w-full h-64 px-4 py-3 border border-slate-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500 text-sm"
              />

              {/* AI Suggestions */}
              {suggestions.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">AI Suggestions for Improvement</h4>
                  <div className="space-y-2">
                    {suggestions.map((suggestion, idx) => (
                      <button
                        key={idx}
                        onClick={() => applySuggestion(suggestion)}
                        disabled={isGenerating}
                        className="w-full text-left p-3 bg-purple-50 hover:bg-purple-100 rounded-lg border border-purple-200 text-sm text-purple-800 transition disabled:opacity-50"
                      >
                        <span className="font-medium">Apply:</span> {suggestion}
                      </button>
                    ))}
                  </div>
                </div>
              )}
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
                <p className="text-sm text-slate-900 whitespace-pre-wrap">{draftText || '(No response drafted)'}</p>
              </div>

              {selectedSpecs.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-slate-700 mb-2">Referenced Specifications</h4>
                  <div className="flex flex-wrap gap-2">
                    {selectedSpecs.map((spec, idx) => (
                      <span key={idx} className="px-3 py-1 bg-blue-50 text-blue-700 rounded-full text-sm">
                        {spec}
                      </span>
                    ))}
                  </div>
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
                ← Previous
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
                className="px-6 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium"
              >
                Next →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
