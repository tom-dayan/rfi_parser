import { useState } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import FolderConfig from './components/FolderConfig';
import FileExplorer from './components/FileExplorer';
import Dashboard from './components/Dashboard';
import { getProjects } from './services/api';
import type { ProjectWithStats } from './types';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppContent() {
  const [activeTab, setActiveTab] = useState<'projects' | 'files' | 'results'>('projects');
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);

  const { data: projects = [], isLoading: projectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  const handleProjectCreated = (projectId: number) => {
    setSelectedProjectId(projectId);
    setActiveTab('files');
  };

  const handleSelectProject = (project: ProjectWithStats) => {
    setSelectedProjectId(project.id);
    setActiveTab('files');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <h1 className="text-3xl font-bold text-gray-900">
            RFI Processing Tool
          </h1>
          <p className="mt-2 text-sm text-gray-600">
            Configure project folders, scan files, and analyze RFIs against specifications
          </p>
        </div>
      </header>

      {/* Navigation */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <nav className="flex space-x-8">
            <NavButton
              label="Projects"
              active={activeTab === 'projects'}
              onClick={() => setActiveTab('projects')}
            />
            <NavButton
              label="Files"
              active={activeTab === 'files'}
              onClick={() => setActiveTab('files')}
              disabled={!selectedProjectId}
            />
            <NavButton
              label="Results"
              active={activeTab === 'results'}
              onClick={() => setActiveTab('results')}
              disabled={!selectedProjectId}
            />
          </nav>
        </div>
      </div>

      {/* Selected Project Indicator */}
      {selectedProject && (
        <div className="bg-blue-50 border-b border-blue-200">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center">
                <span className="text-sm text-blue-700">Active Project:</span>
                <span className="ml-2 text-sm font-medium text-blue-900">{selectedProject.name}</span>
                <span className="ml-4 text-xs text-blue-600">
                  {selectedProject.rfi_count} RFIs • {selectedProject.spec_count} Specs • {selectedProject.drawing_count} Drawings
                </span>
              </div>
              <button
                onClick={() => setSelectedProjectId(null)}
                className="text-sm text-blue-700 hover:text-blue-900"
              >
                Change Project
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {activeTab === 'projects' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <FolderConfig onProjectCreated={handleProjectCreated} />
            <ProjectList
              projects={projects}
              loading={projectsLoading}
              selectedId={selectedProjectId}
              onSelect={handleSelectProject}
            />
          </div>
        )}

        {activeTab === 'files' && selectedProjectId && (
          <FileExplorer projectId={selectedProjectId} />
        )}

        {activeTab === 'results' && selectedProjectId && (
          <Dashboard projectId={selectedProjectId} />
        )}

        {(activeTab === 'files' || activeTab === 'results') && !selectedProjectId && (
          <div className="text-center py-12 bg-white rounded-lg shadow-md">
            <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
            <h3 className="mt-4 text-lg font-medium text-gray-900">No Project Selected</h3>
            <p className="mt-2 text-sm text-gray-600">
              Please select or create a project first.
            </p>
            <button
              onClick={() => setActiveTab('projects')}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Go to Projects
            </button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="bg-white border-t border-gray-200 mt-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-gray-500">
            Powered by Ollama AI • Ready to switch to Claude API anytime
          </p>
        </div>
      </footer>
    </div>
  );
}

function NavButton({
  label,
  active,
  onClick,
  disabled = false,
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`py-4 px-1 border-b-2 font-medium text-sm transition-colors ${
        active
          ? 'border-blue-600 text-blue-600'
          : disabled
          ? 'border-transparent text-gray-300 cursor-not-allowed'
          : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
      }`}
    >
      {label}
    </button>
  );
}

function ProjectList({
  projects,
  loading,
  selectedId,
  onSelect,
}: {
  projects: ProjectWithStats[];
  loading: boolean;
  selectedId: number | null;
  onSelect: (project: ProjectWithStats) => void;
}) {
  if (loading) {
    return (
      <div className="bg-white rounded-lg shadow-md p-6">
        <h2 className="text-xl font-semibold text-gray-900 mb-4">Existing Projects</h2>
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-300 border-t-blue-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-lg shadow-md p-6">
      <h2 className="text-xl font-semibold text-gray-900 mb-4">Existing Projects</h2>
      {projects.length === 0 ? (
        <p className="text-gray-500 text-center py-8">
          No projects yet. Create your first project using the form on the left.
        </p>
      ) : (
        <div className="space-y-3">
          {projects.map((project) => (
            <div
              key={project.id}
              onClick={() => onSelect(project)}
              className={`p-4 rounded-lg border-2 cursor-pointer transition-colors ${
                selectedId === project.id
                  ? 'border-blue-500 bg-blue-50'
                  : 'border-gray-200 hover:border-gray-300 hover:bg-gray-50'
              }`}
            >
              <div className="flex items-center justify-between">
                <h3 className="font-medium text-gray-900">{project.name}</h3>
                {project.result_count > 0 && (
                  <span className="px-2 py-1 bg-green-100 text-green-800 text-xs rounded">
                    {project.result_count} results
                  </span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-3 text-sm text-gray-600">
                <span>{project.rfi_count} RFIs</span>
                <span>{project.spec_count} Specs</span>
                <span>{project.drawing_count} Drawings</span>
              </div>
              {project.last_scanned && (
                <p className="mt-2 text-xs text-gray-400">
                  Last scanned: {new Date(project.last_scanned).toLocaleDateString()}
                </p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}

export default App;
