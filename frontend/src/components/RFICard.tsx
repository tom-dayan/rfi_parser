import type { RFIResultWithFile } from '../types';
import StatusBadge from './StatusBadge';

interface RFICardProps {
  result: RFIResultWithFile;
}

export default function RFICard({ result }: RFICardProps) {
  return (
    <div className="bg-white rounded-lg shadow-md p-6 border border-gray-200 hover:shadow-lg transition-shadow">
      {/* Header */}
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">
            {result.rfi_file?.filename || `RFI #${result.rfi_file_id}`}
          </h3>
          <p className="text-xs text-gray-500">
            {result.rfi_file?.file_type.toUpperCase()} • {formatFileSize(result.rfi_file?.file_size || 0)}
          </p>
        </div>
        <StatusBadge status={result.status} />
      </div>

      {/* Content */}
      <div className="space-y-3">
        {/* Consultant Type (if referred) */}
        {result.consultant_type && (
          <div className="flex items-start">
            <span className="text-sm font-medium text-gray-700 w-32 flex-shrink-0">
              Consultant:
            </span>
            <span className="text-sm text-gray-900 capitalize">
              {result.consultant_type}
            </span>
          </div>
        )}

        {/* Reason (for rejected/comment) */}
        {result.reason && (
          <div className="flex items-start">
            <span className="text-sm font-medium text-gray-700 w-32 flex-shrink-0">
              Reason:
            </span>
            <span className="text-sm text-gray-900">{result.reason}</span>
          </div>
        )}

        {/* Specification References */}
        {result.spec_references && result.spec_references.length > 0 && (
          <div className="mt-3">
            <span className="text-sm font-medium text-gray-700">Spec References:</span>
            {result.spec_references.map((ref, index) => (
              <div key={index} className="mt-2 p-3 bg-gray-50 rounded border-l-4 border-blue-500">
                <p className="text-sm text-blue-600 font-medium">{ref.filename}</p>
                {ref.section && (
                  <p className="text-xs text-gray-500 mt-1">Section: {ref.section}</p>
                )}
                {ref.quote && (
                  <p className="text-sm text-gray-700 italic mt-2">{ref.quote}</p>
                )}
              </div>
            ))}
          </div>
        )}

        {/* Confidence */}
        <div className="flex items-center mt-4 pt-3 border-t border-gray-200">
          <span className="text-xs text-gray-500 mr-2">Confidence:</span>
          <div className="flex-1 bg-gray-200 rounded-full h-2 max-w-xs">
            <div
              className="bg-blue-600 h-2 rounded-full"
              style={{ width: `${result.confidence * 100}%` }}
            />
          </div>
          <span className="text-xs text-gray-600 ml-2">
            {Math.round(result.confidence * 100)}%
          </span>
        </div>

        {/* Metadata */}
        <div className="flex items-center justify-between text-xs text-gray-500 mt-3">
          <span>
            {result.referenced_file_ids?.length || 0} files referenced
          </span>
          <span>Processed: {new Date(result.processed_date).toLocaleDateString()}</span>
        </div>
      </div>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
