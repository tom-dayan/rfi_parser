import type { RFIStatus } from '../types';

interface StatusBadgeProps {
  status: RFIStatus;
}

const statusConfig: Record<RFIStatus, { label: string; className: string }> = {
  accepted: {
    label: 'Accepted',
    className: 'bg-green-100 text-green-800 border-green-200',
  },
  rejected: {
    label: 'Rejected',
    className: 'bg-red-100 text-red-800 border-red-200',
  },
  comment: {
    label: 'Comment',
    className: 'bg-yellow-100 text-yellow-800 border-yellow-200',
  },
  refer_to_consultant: {
    label: 'Refer to Consultant',
    className: 'bg-blue-100 text-blue-800 border-blue-200',
  },
};

export default function StatusBadge({ status }: StatusBadgeProps) {
  const config = statusConfig[status];

  return (
    <span
      className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium border ${config.className}`}
    >
      {config.label}
    </span>
  );
}
