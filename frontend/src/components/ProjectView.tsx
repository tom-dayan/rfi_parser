import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getProject } from '../services/api';
import FileExplorer from './FileExplorer';
import Dashboard from './Dashboard';
import SmartAnalysis from './SmartAnalysis';

interface ProjectViewProps {
  projectId: number;
  onBack: () => void;
}

export default function ProjectView({ projectId, onBack }: ProjectViewProps) {
  const [activeTab, setActiveTab] = useState<'files' | 'smart' | 'results'>('files');
  const [showSmartAnalysis, setShowSmartAnalysis] = useState(false);

  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });

  return (
    <div className="space-y-6">
      {/* Project Header */}
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
        <div className="px-6 py-5 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <button
              onClick={onBack}
              className="p-2 rounded-lg hover:bg-slate-100 transition-colors text-slate-500 hover:text-slate-700"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </button>
            <div>
              <h1 className="text-xl font-semibold text-slate-900">
                {project?.name || 'Loading...'}
              </h1>
              {project && (
                <div className="mt-1 flex items-center gap-4 text-sm text-slate-500">
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                    {project.rfi_count} RFIs
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-indigo-500"></span>
                    {project.submittal_count || 0} Submittals
                  </span>
                  <span className="flex items-center gap-1">
                    <span className="w-2 h-2 rounded-full bg-emerald-500"></span>
                    {project.spec_count} Specs
                  </span>
                  {project.result_count > 0 && (
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber-500"></span>
                      {project.result_count} Results
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Internal Tab Navigation */}
        <div className="px-6 border-t border-slate-100 bg-slate-50">
          <nav className="flex gap-1">
            <TabButton
              label="Files"
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
                </svg>
              }
              active={activeTab === 'files'}
              onClick={() => setActiveTab('files')}
            />
            <TabButton
              label="Smart Analysis"
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                </svg>
              }
              active={activeTab === 'smart'}
              onClick={() => setShowSmartAnalysis(true)}
              badge="New"
            />
            <TabButton
              label="Results"
              icon={
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              }
              active={activeTab === 'results'}
              onClick={() => setActiveTab('results')}
            />
          </nav>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'files' && <FileExplorer projectId={projectId} />}
      {activeTab === 'results' && <Dashboard projectId={projectId} projectName={project?.name} />}
      
      {/* Smart Analysis Modal */}
      {showSmartAnalysis && (
        <SmartAnalysis
          projectId={projectId}
          projectName={project?.name}
          onComplete={() => setActiveTab('results')}
          onClose={() => setShowSmartAnalysis(false)}
        />
      )}
    </div>
  );
}

function TabButton({
  label,
  icon,
  active,
  onClick,
  badge,
}: {
  label: string;
  icon: React.ReactNode;
  active: boolean;
  onClick: () => void;
  badge?: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
        active
          ? 'border-blue-600 text-blue-600 bg-white'
          : 'border-transparent text-slate-500 hover:text-slate-700'
      }`}
    >
      {icon}
      {label}
      {badge && (
        <span className="px-1.5 py-0.5 text-[10px] font-semibold bg-primary-500 text-white rounded-full">
          {badge}
        </span>
      )}
    </button>
  );
}
