import { useState, useEffect, useCallback } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import FolderConfig from './components/FolderConfig';
import ProjectView from './components/ProjectView';
import GlobalSearch from './components/GlobalSearch';
import ChatInterface from './components/ChatInterface';
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
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);

  const { data: projects = [], isLoading: projectsLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const handleProjectCreated = (projectId: number) => {
    setSelectedProjectId(projectId);
  };

  const handleSelectProject = (project: ProjectWithStats) => {
    setSelectedProjectId(project.id);
  };

  // Keyboard shortcut for search (Cmd/Ctrl + K)
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      setSearchOpen(true);
    }
  }, []);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Global Search Modal */}
      <GlobalSearch
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelectFile={(file) => {
          console.log('Selected file:', file);
          // Could open file preview or navigate to it
        }}
      />

      {/* Chat Sidebar */}
      {chatOpen && (
        <div className="fixed right-0 top-0 bottom-0 w-96 z-40 shadow-2xl">
          <ChatInterface
            projectId={selectedProjectId || undefined}
            projectName={selectedProject?.name}
            onClose={() => setChatOpen(false)}
          />
        </div>
      )}

      {/* Header */}
      <header className="bg-white border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center">
                <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">
                  RFI Processing Tool
                </h1>
                <p className="text-sm text-slate-500">
                  Analyze RFIs and Submittals against specifications
                </p>
              </div>
            </div>

            {/* Search and Chat buttons */}
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSearchOpen(true)}
                className="flex items-center gap-2 px-4 py-2 text-sm text-slate-600 bg-slate-100 hover:bg-slate-200 rounded-lg transition"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <span>Search</span>
                <kbd className="hidden sm:inline px-1.5 py-0.5 text-xs bg-slate-200 rounded">⌘K</kbd>
              </button>
              <button
                onClick={() => setChatOpen(!chatOpen)}
                className={`flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition ${
                  chatOpen
                    ? 'bg-purple-600 text-white'
                    : 'text-slate-600 bg-slate-100 hover:bg-slate-200'
                }`}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
                </svg>
                <span>Ask OLI</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {selectedProjectId ? (
          <ProjectView
            projectId={selectedProjectId}
            onBack={() => setSelectedProjectId(null)}
          />
        ) : (
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
      </main>

      {/* Footer */}
      <footer className="border-t border-slate-200 mt-12 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
          <p className="text-center text-sm text-slate-400">
            RFI Processing Tool
          </p>
        </div>
      </footer>
    </div>
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
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
        <h2 className="text-lg font-semibold text-slate-900 mb-4">Your Projects</h2>
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-2 border-slate-300 border-t-blue-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6">
      <h2 className="text-lg font-semibold text-slate-900 mb-4">Your Projects</h2>
      {projects.length === 0 ? (
        <div className="text-center py-12">
          <div className="w-16 h-16 mx-auto rounded-full bg-slate-100 flex items-center justify-center mb-4">
            <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
            </svg>
          </div>
          <p className="text-slate-500">No projects yet</p>
          <p className="text-sm text-slate-400 mt-1">Create your first project using the form</p>
        </div>
      ) : (
        <div className="space-y-3">
          {projects.map((project) => (
            <button
              key={project.id}
              onClick={() => onSelect(project)}
              className={`w-full text-left p-4 rounded-xl border-2 transition-all duration-200 ${
                selectedId === project.id
                  ? 'border-blue-500 bg-blue-50 shadow-sm'
                  : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
              }`}
            >
              <div className="flex items-start justify-between">
                <h3 className="font-medium text-slate-900">{project.name}</h3>
                {project.result_count > 0 && (
                  <span className="px-2.5 py-0.5 bg-emerald-100 text-emerald-700 text-xs font-medium rounded-full">
                    {project.result_count} results
                  </span>
                )}
              </div>
              <div className="mt-3 flex flex-wrap gap-3">
                <StatBadge label="RFIs" count={project.rfi_count} color="blue" />
                <StatBadge label="Submittals" count={project.submittal_count || 0} color="indigo" />
                <StatBadge label="Specs" count={project.spec_count} color="emerald" />
              </div>
              {project.last_scanned && (
                <p className="mt-3 text-xs text-slate-400">
                  Last scanned: {new Date(project.last_scanned).toLocaleDateString()}
                </p>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StatBadge({ label, count, color }: { label: string; count: number; color: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700',
    indigo: 'bg-indigo-50 text-indigo-700',
    emerald: 'bg-emerald-50 text-emerald-700',
    amber: 'bg-amber-50 text-amber-700',
  };

  return (
    <span className={`px-2.5 py-1 text-xs font-medium rounded-lg ${colors[color]}`}>
      {count} {label}
    </span>
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
