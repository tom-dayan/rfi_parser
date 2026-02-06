import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getProjectResults,
  updateResult,
  deleteResult,
} from '../services/api';
import RefineMode from './CoPilotMode';
import { Card, Badge } from './ui';
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
  const [refineResult, setRefineResult] = useState<ProcessingResultWithFile | null>(null);
  const queryClient = useQueryClient();

  // Fetch results
  const { data: results = [], isLoading: resultsLoading } = useQuery({
    queryKey: ['results', projectId],
    queryFn: () => getProjectResults(projectId),
  });

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

  return (
    <div className="space-y-6">
      {/* Results Header */}
      <Card>
        <div className="flex items-center justify-between mb-5">
          <div>
            <h2 className="text-lg font-semibold text-stone-900">Analysis Results</h2>
            <p className="text-sm text-stone-500 mt-1">
              {results.length === 0
                ? 'Run Smart Analysis to generate responses for your RFIs and Submittals.'
                : `${results.length} document${results.length !== 1 ? 's' : ''} analyzed`}
            </p>
          </div>
        </div>

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
            className={`px-4 py-2 rounded-xl text-sm font-medium transition-colors ${
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
            Use Smart Analysis to select RFIs/Submittals and generate AI responses.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredResults.map((result: ProcessingResultWithFile) => (
            <ResultCard 
              key={result.id} 
              result={result}
              projectId={projectId}
              onViewDetails={() => setSelectedResult(result)}
              onRefine={() => setRefineResult(result)}
            />
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedResult && (
        <ResultDetailModal 
          result={selectedResult}
          projectId={projectId}
          onClose={() => setSelectedResult(null)}
          onUpdate={() => {
            queryClient.invalidateQueries({ queryKey: ['results', projectId] });
          }}
          onRefine={() => {
            setRefineResult(selectedResult);
            setSelectedResult(null);
          }}
        />
      )}

      {/* Refine Mode (formerly Co-Pilot) */}
      {refineResult && (
        <RefineMode
          result={refineResult}
          projectId={projectId}
          projectName={projectName}
          onClose={() => setRefineResult(null)}
          onSave={() => {
            setRefineResult(null);
            queryClient.invalidateQueries({ queryKey: ['results', projectId] });
          }}
        />
      )}
    </div>
  );
}

function ResultCard({ 
  result, 
  projectId,
  onViewDetails, 
  onRefine,
}: { 
  result: ProcessingResultWithFile; 
  projectId: number;
  onViewDetails: () => void; 
  onRefine: () => void;
}) {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const queryClient = useQueryClient();
  const isRFI = result.document_type === 'rfi';
  const isTruncated = result.response_text && result.response_text.length > 300;
  const hasMoreRefs = result.spec_references && result.spec_references.length > 2;

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteResult(result.id);
      queryClient.invalidateQueries({ queryKey: ['results', projectId] });
    } catch (err) {
      console.error('Failed to delete result:', err);
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  return (
    <div className="bg-white rounded-lg shadow-md p-6 flex flex-col relative">
      {/* Delete Confirmation Overlay */}
      {showDeleteConfirm && (
        <div className="absolute inset-0 bg-white/95 rounded-lg z-10 flex items-center justify-center p-6">
          <div className="text-center">
            <div className="w-12 h-12 mx-auto rounded-full bg-red-100 flex items-center justify-center mb-3">
              <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
            </div>
            <p className="text-sm font-medium text-slate-900 mb-1">Delete this result?</p>
            <p className="text-xs text-slate-500 mb-4">This cannot be undone.</p>
            <div className="flex justify-center gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                disabled={isDeleting}
                className="px-4 py-2 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition disabled:opacity-50"
              >
                {isDeleting ? 'Deleting...' : 'Delete'}
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="flex items-start justify-between mb-4">
        <div className="flex-1 min-w-0">
          <span className={`inline-block px-2 py-1 rounded text-xs font-medium ${
            isRFI ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
          }`}>
            {isRFI ? 'RFI' : 'Submittal'}
          </span>
          <h3 className="text-lg font-semibold text-gray-900 mt-2 truncate">
            {result.source_file?.filename || result.source_filename || 'Unknown'}
          </h3>
        </div>
        <div className="flex items-center gap-2 ml-2 flex-shrink-0">
          {!isRFI && result.status && (
            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getStatusColor(result.status)}`}>
              {result.status.replace(/_/g, ' ')}
            </span>
          )}
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="p-1.5 text-slate-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition"
            title="Delete result"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
          </button>
        </div>
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
          <span className="mx-2">&middot;</span>
          <span>{new Date(result.processed_date).toLocaleDateString()}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefine}
            className="text-sm text-purple-600 hover:text-purple-800 font-medium flex items-center gap-1"
            title="Refine this response with AI assistance"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
            Refine
          </button>
          <button
            onClick={onViewDetails}
            className="text-sm text-blue-600 hover:text-blue-800 font-medium flex items-center"
          >
            View Full
            <svg className="w-4 h-4 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function ResultDetailModal({ 
  result, 
  projectId,
  onClose,
  onUpdate,
  onRefine,
}: { 
  result: ProcessingResultWithFile;
  projectId: number;
  onClose: () => void;
  onUpdate?: () => void;
  onRefine?: () => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedText, setEditedText] = useState(result.response_text || '');
  const [isSaving, setIsSaving] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const queryClient = useQueryClient();
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

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await deleteResult(result.id);
      queryClient.invalidateQueries({ queryKey: ['results', projectId] });
      onClose();
    } catch (err) {
      console.error('Failed to delete result:', err);
      setIsDeleting(false);
      setShowDeleteConfirm(false);
    }
  };

  // Close on escape key (only if not editing)
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Escape' && !isEditing && !showDeleteConfirm) onClose();
  };

  return (
    <div 
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
      onClick={!isEditing && !showDeleteConfirm ? onClose : undefined}
      onKeyDown={handleKeyDown}
      tabIndex={0}
    >
      <div 
        className="bg-white rounded-xl shadow-2xl max-w-3xl w-full max-h-[90vh] overflow-hidden flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Delete Confirmation */}
        {showDeleteConfirm && (
          <div className="absolute inset-0 bg-white/95 z-20 flex items-center justify-center rounded-xl">
            <div className="text-center p-8">
              <div className="w-14 h-14 mx-auto rounded-full bg-red-100 flex items-center justify-center mb-4">
                <svg className="w-7 h-7 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900 mb-1">Delete this result?</h3>
              <p className="text-sm text-slate-500 mb-6">This action cannot be undone.</p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  disabled={isDeleting}
                  className="px-5 py-2.5 text-sm font-medium text-slate-700 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
                >
                  Cancel
                </button>
                <button
                  onClick={handleDelete}
                  disabled={isDeleting}
                  className="px-5 py-2.5 text-sm font-medium text-white bg-red-600 hover:bg-red-700 rounded-lg transition disabled:opacity-50"
                >
                  {isDeleting ? 'Deleting...' : 'Delete Result'}
                </button>
              </div>
            </div>
          </div>
        )}

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
                    </div>
                    {ref.text && (
                      <p className="text-sm text-gray-600 mt-2 italic">
                        &quot;{ref.text.length > 300 ? ref.text.substring(0, 300) + '...' : ref.text}&quot;
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
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">
              Processed: {new Date(result.processed_date).toLocaleString()}
            </span>
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="text-xs text-red-500 hover:text-red-700 font-medium flex items-center gap-1 transition"
            >
              <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
              </svg>
              Delete
            </button>
          </div>
          <div className="flex items-center gap-2">
            {onRefine && (
              <button
                onClick={onRefine}
                className="px-4 py-2 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors text-sm font-medium flex items-center gap-1.5"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                </svg>
                Refine with AI
              </button>
            )}
            <button
              onClick={onClose}
              className="px-4 py-2 bg-gray-800 text-white rounded-lg hover:bg-gray-900 transition-colors text-sm font-medium"
            >
              Close
            </button>
          </div>
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
