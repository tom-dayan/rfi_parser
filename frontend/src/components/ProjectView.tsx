import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { getProject, updateProject, deleteProject } from '../services/api';
import FileExplorer from './FileExplorer';
import Dashboard from './Dashboard';
import SmartAnalysis from './SmartAnalysis';

interface ProjectViewProps {
  projectId: number;
  onBack: () => void;
}

export default function ProjectView({ projectId, onBack }: ProjectViewProps) {
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<'files' | 'smart' | 'results'>('files');
  const [showSmartAnalysis, setShowSmartAnalysis] = useState(false);
  const [showSettings, setShowSettings] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const { data: project, refetch: refetchProject } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => getProject(projectId),
  });
  
  const deleteMutation = useMutation({
    mutationFn: () => deleteProject(projectId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      onBack();
    },
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
          
          {/* Settings Button */}
          <button
            onClick={() => setShowSettings(true)}
            className="p-2 rounded-lg hover:bg-slate-100 transition-colors text-slate-500 hover:text-slate-700"
            title="Project Settings"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
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
      
      {/* Project Settings Modal */}
      {showSettings && project && (
        <ProjectSettingsModal
          project={project}
          onClose={() => setShowSettings(false)}
          onSave={() => {
            refetchProject();
            setShowSettings(false);
          }}
          onDelete={() => setShowDeleteConfirm(true)}
        />
      )}
      
      {/* Delete Confirmation Dialog */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="p-2 bg-red-100 rounded-full">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h3 className="text-lg font-semibold text-slate-900">Delete Project?</h3>
            </div>
            <p className="text-slate-600 mb-6">
              Are you sure you want to delete <strong>{project?.name}</strong>? This will remove all indexed files and analysis results. This action cannot be undone.
            </p>
            <div className="flex gap-3 justify-end">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="px-4 py-2 text-slate-700 hover:bg-slate-100 rounded-lg transition"
              >
                Cancel
              </button>
              <button
                onClick={() => deleteMutation.mutate()}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition disabled:opacity-50"
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete Project'}
              </button>
            </div>
          </div>
        </div>
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

// Project Settings Modal Component
function ProjectSettingsModal({
  project,
  onClose,
  onSave,
  onDelete,
}: {
  project: import('../types').ProjectWithStats;
  onClose: () => void;
  onSave: () => void;
  onDelete: () => void;
}) {
  const [name, setName] = useState(project.name);
  const [rfiFolder, setRfiFolder] = useState(project.rfi_folder_path);
  const [specsFolder, setSpecsFolder] = useState(project.specs_folder_path);
  const [excludeFolders, setExcludeFolders] = useState(
    (project.exclude_folders || []).join('\n')
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    try {
      const excludeList = excludeFolders
        .split('\n')
        .map(f => f.trim())
        .filter(f => f.length > 0);
      
      await updateProject(project.id, {
        name,
        rfi_folder_path: rfiFolder,
        specs_folder_path: specsFolder,
        exclude_folders: excludeList,
      });
      onSave();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save changes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-xl shadow-2xl max-w-lg w-full max-h-[90vh] flex flex-col overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-900">Project Settings</h2>
          <button
            onClick={onClose}
            className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-100 rounded-lg transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        
        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-lg text-sm">
              {error}
            </div>
          )}
          
          {/* Project Name */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Project Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
            />
          </div>
          
          {/* RFI Folder */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              RFI / Submittal Folder Path
            </label>
            <input
              type="text"
              value={rfiFolder}
              onChange={(e) => setRfiFolder(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
            />
          </div>
          
          {/* Specs Folder */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Specifications Folder Path
            </label>
            <input
              type="text"
              value={specsFolder}
              onChange={(e) => setSpecsFolder(e.target.value)}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
            />
          </div>
          
          {/* Exclude Folders */}
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">
              Exclude Folders from Spec Suggestions
            </label>
            <p className="text-xs text-slate-500 mb-2">
              Enter folder names to exclude (one per line). These folders will be skipped when suggesting specs.
              Useful for excluding RFI/Submittal folders that may be inside the specs folder.
            </p>
            <textarea
              value={excludeFolders}
              onChange={(e) => setExcludeFolders(e.target.value)}
              placeholder="RFIs&#10;Submittals&#10;Archive"
              rows={4}
              className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 font-mono text-sm"
            />
          </div>
          
          {/* Danger Zone */}
          <div className="pt-4 border-t border-slate-200">
            <h3 className="text-sm font-medium text-red-600 mb-2">Danger Zone</h3>
            <button
              onClick={onDelete}
              className="px-4 py-2 text-red-600 border border-red-300 rounded-lg hover:bg-red-50 transition text-sm"
            >
              Delete Project
            </button>
          </div>
        </div>
        
        {/* Footer */}
        <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 text-slate-700 hover:bg-slate-100 rounded-lg transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
