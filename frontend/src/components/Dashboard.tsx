import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProjectResults, getProjectFiles, processProjectRFIs } from '../services/api';
import RFICard from './RFICard';
import type { RFIStatus, RFIResultWithFile } from '../types';

interface DashboardProps {
  projectId: number;
}

export default function Dashboard({ projectId }: DashboardProps) {
  const [statusFilter, setStatusFilter] = useState<RFIStatus | 'all'>('all');
  const queryClient = useQueryClient();

  const { data: results = [], isLoading: resultsLoading } = useQuery({
    queryKey: ['results', projectId],
    queryFn: () => getProjectResults(projectId),
  });

  const { data: rfiFiles = [] } = useQuery({
    queryKey: ['files', projectId, 'rfi'],
    queryFn: () => getProjectFiles(projectId, 'rfi'),
  });

  const { data: specFiles = [] } = useQuery({
    queryKey: ['files', projectId, 'specification'],
    queryFn: () => getProjectFiles(projectId, 'specification'),
  });

  const processMutation = useMutation({
    mutationFn: () => processProjectRFIs(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['results', projectId] });
      queryClient.invalidateQueries({ queryKey: ['projects'] });
    },
  });

  const handleProcess = () => {
    processMutation.mutate();
  };

  const filteredResults = statusFilter === 'all'
    ? results
    : results.filter((r: RFIResultWithFile) => r.status === statusFilter);

  const statusCounts = {
    all: results.length,
    accepted: results.filter((r: RFIResultWithFile) => r.status === 'accepted').length,
    rejected: results.filter((r: RFIResultWithFile) => r.status === 'rejected').length,
    comment: results.filter((r: RFIResultWithFile) => r.status === 'comment').length,
    refer_to_consultant: results.filter((r: RFIResultWithFile) => r.status === 'refer_to_consultant').length,
  };

  return (
    <div className="w-full max-w-7xl mx-auto">
      {/* Header */}
      <div className="bg-white rounded-lg shadow-md p-6 mb-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">RFI Results</h2>
            <p className="text-sm text-gray-600 mt-1">
              {rfiFiles.length} RFIs • {specFiles.length} Specifications • {results.length} Results
            </p>
          </div>
          <button
            onClick={handleProcess}
            disabled={processMutation.isPending || rfiFiles.length === 0 || specFiles.length === 0}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium flex items-center"
          >
            {processMutation.isPending ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4 text-white" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Processing...
              </>
            ) : (
              'Process All RFIs'
            )}
          </button>
        </div>

        {processMutation.isError && (
          <div className="p-3 bg-red-50 text-red-800 rounded-lg text-sm mb-4">
            Processing failed. Please ensure Ollama is running and try again.
          </div>
        )}

        {processMutation.isSuccess && (
          <div className="p-3 bg-green-50 text-green-800 rounded-lg text-sm mb-4">
            Processed {processMutation.data.results_count} RFIs successfully!
          </div>
        )}

        {/* Status Filter */}
        <div className="flex gap-2 flex-wrap">
          <StatusFilterButton
            label="All"
            count={statusCounts.all}
            active={statusFilter === 'all'}
            onClick={() => setStatusFilter('all')}
            color="gray"
          />
          <StatusFilterButton
            label="Accepted"
            count={statusCounts.accepted}
            active={statusFilter === 'accepted'}
            onClick={() => setStatusFilter('accepted')}
            color="green"
          />
          <StatusFilterButton
            label="Rejected"
            count={statusCounts.rejected}
            active={statusFilter === 'rejected'}
            onClick={() => setStatusFilter('rejected')}
            color="red"
          />
          <StatusFilterButton
            label="Comment"
            count={statusCounts.comment}
            active={statusFilter === 'comment'}
            onClick={() => setStatusFilter('comment')}
            color="yellow"
          />
          <StatusFilterButton
            label="Referred"
            count={statusCounts.refer_to_consultant}
            active={statusFilter === 'refer_to_consultant'}
            onClick={() => setStatusFilter('refer_to_consultant')}
            color="blue"
          />
        </div>
      </div>

      {/* Results Grid */}
      {resultsLoading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-12 w-12 border-4 border-gray-300 border-t-blue-600" />
          <p className="text-gray-600 mt-4">Loading results...</p>
        </div>
      ) : filteredResults.length === 0 ? (
        <div className="text-center py-12 bg-white rounded-lg shadow-md">
          <svg
            className="mx-auto h-12 w-12 text-gray-400"
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
          <h3 className="mt-4 text-lg font-medium text-gray-900">No results yet</h3>
          <p className="mt-2 text-sm text-gray-600">
            {rfiFiles.length === 0 || specFiles.length === 0
              ? 'Scan your project folders first to index files, then process RFIs.'
              : 'Click "Process All RFIs" to analyze your RFIs against specifications.'}
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {filteredResults.map((result: RFIResultWithFile) => (
            <RFICard key={result.id} result={result} />
          ))}
        </div>
      )}
    </div>
  );
}

function StatusFilterButton({
  label,
  count,
  active,
  onClick,
  color,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  color: 'gray' | 'green' | 'red' | 'yellow' | 'blue';
}) {
  const colorClasses = {
    gray: active ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-700 hover:bg-gray-200',
    green: active ? 'bg-green-600 text-white' : 'bg-green-50 text-green-700 hover:bg-green-100',
    red: active ? 'bg-red-600 text-white' : 'bg-red-50 text-red-700 hover:bg-red-100',
    yellow: active ? 'bg-yellow-600 text-white' : 'bg-yellow-50 text-yellow-700 hover:bg-yellow-100',
    blue: active ? 'bg-blue-600 text-white' : 'bg-blue-50 text-blue-700 hover:bg-blue-100',
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
