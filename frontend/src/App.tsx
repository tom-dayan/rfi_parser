import { useState, useEffect, useCallback } from 'react';
import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query';
import FolderConfig from './components/FolderConfig';
import ProjectDiscovery from './components/ProjectDiscovery';
import ProjectView from './components/ProjectView';
import GlobalSearch from './components/GlobalSearch';
import ChatInterface from './components/ChatInterface';
import { Card, CardHeader, CardTitle, Badge, Button, SkeletonList } from './components/ui';
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

// Icons
const SearchIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
  </svg>
);

const ChatIcon = () => (
  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
  </svg>
);

const FolderIcon = () => (
  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" />
  </svg>
);

const DocumentIcon = () => (
  <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
  </svg>
);

function AppContent() {
  const [selectedProjectId, setSelectedProjectId] = useState<number | null>(null);
  const [searchOpen, setSearchOpen] = useState(false);
  const [chatOpen, setChatOpen] = useState(false);
  const [showNewProject, setShowNewProject] = useState(false);
  const [showDiscovery, setShowDiscovery] = useState(false);

  const { data: projects = [], isLoading: projectsLoading, refetch } = useQuery({
    queryKey: ['projects'],
    queryFn: getProjects,
  });

  const handleProjectCreated = (projectId: number) => {
    setSelectedProjectId(projectId);
    setShowNewProject(false);
    setShowDiscovery(false);
    refetch();
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
    if (e.key === 'Escape') {
      if (searchOpen) setSearchOpen(false);
      if (chatOpen) setChatOpen(false);
    }
  }, [searchOpen, chatOpen]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const selectedProject = projects.find(p => p.id === selectedProjectId);

  return (
    <div className="min-h-screen bg-stone-50">
      {/* Global Search Modal */}
      <GlobalSearch
        isOpen={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelectFile={(file) => {
          console.log('Selected file:', file);
        }}
      />

      {/* Chat Sidebar */}
      {chatOpen && (
        <div className="fixed right-0 top-0 bottom-0 w-[420px] z-40 shadow-elevated animate-slide-in-right">
          <ChatInterface
            projectId={selectedProjectId || undefined}
            projectName={selectedProject?.name}
            onClose={() => setChatOpen(false)}
            onAction={(action) => {
              // Handle chat actions
              if (action.action_type === 'smart_analysis' && selectedProjectId) {
                setChatOpen(false);
                // Will be handled by ProjectView's SmartAnalysis
              } else if (action.action_type === 'navigate') {
                const path = action.params?.path as string;
                if (path === '/projects') {
                  setSelectedProjectId(null);
                } else if (path === '/settings') {
                  setShowNewProject(true);
                }
              } else if (action.action_type === 'find_specs' || action.action_type === 'browse_files') {
                // Close chat, user can use the file browser
                setChatOpen(false);
              }
            }}
          />
        </div>
      )}

      {/* Header */}
      <header className="bg-white border-b border-stone-200 sticky top-0 z-30">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            {/* Logo & Title */}
            <div className="flex items-center gap-4">
              <button 
                onClick={() => setSelectedProjectId(null)}
                className="flex items-center gap-3 hover:opacity-80 transition"
              >
                <img src="/olilogo.png" alt="OLI" className="w-10 h-10 rounded-xl object-contain" />
                <div>
                  <h1 className="text-lg font-semibold text-stone-900">OLILab</h1>
                  <p className="text-xs text-stone-500">Design Research Workshop</p>
                </div>
              </button>
            </div>

            {/* Center: Search Bar (if not in project) */}
            {!selectedProjectId && (
              <button
                onClick={() => setSearchOpen(true)}
                className="hidden md:flex items-center gap-3 px-4 py-2.5 w-80 bg-stone-100 hover:bg-stone-200 rounded-xl text-left transition group"
              >
                <SearchIcon />
                <span className="text-stone-500 text-sm flex-1">Search files, projects...</span>
                <kbd className="px-2 py-1 text-xs bg-white text-stone-400 rounded-md border border-stone-200 group-hover:bg-stone-50">
                  ⌘K
                </kbd>
              </button>
            )}

            {/* Right: Actions */}
            <div className="flex items-center gap-2">
              {selectedProjectId && (
                <Button
                  variant="secondary"
                  size="sm"
                  icon={<SearchIcon />}
                  onClick={() => setSearchOpen(true)}
                >
                  Search
                </Button>
              )}
              <Button
                variant={chatOpen ? 'primary' : 'secondary'}
                size="sm"
                icon={<ChatIcon />}
                onClick={() => setChatOpen(!chatOpen)}
              >
                Ask OLI
              </Button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {selectedProjectId ? (
          <ProjectView
            projectId={selectedProjectId}
            onBack={() => setSelectedProjectId(null)}
          />
        ) : (
          <div className="space-y-8">
            {/* Welcome Section */}
            <div className="text-center py-8">
              <h2 className="text-2xl font-semibold text-stone-900 mb-2">
                Welcome to OLILab
              </h2>
              <p className="text-stone-500 max-w-lg mx-auto">
                Search across all project documents, analyze RFIs and submittals, 
                and get AI-powered assistance for your architecture projects.
              </p>
            </div>

            {/* Quick Actions */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <button
                onClick={() => setSearchOpen(true)}
                className="flex items-center gap-4 p-5 bg-white rounded-2xl border border-stone-200 hover:border-primary-300 hover:shadow-soft transition text-left group"
              >
                <div className="w-12 h-12 rounded-xl bg-primary-50 text-primary-600 flex items-center justify-center group-hover:bg-primary-100 transition">
                  <SearchIcon />
                </div>
                <div>
                  <h3 className="font-medium text-stone-900">Search Files</h3>
                  <p className="text-sm text-stone-500">Find documents across all projects</p>
                </div>
              </button>
              
              <button
                onClick={() => setChatOpen(true)}
                className="flex items-center gap-4 p-5 bg-white rounded-2xl border border-stone-200 hover:border-primary-300 hover:shadow-soft transition text-left group"
              >
                <div className="w-12 h-12 rounded-xl bg-submittal-50 text-submittal-600 flex items-center justify-center group-hover:bg-submittal-100 transition">
                  <ChatIcon />
                </div>
                <div>
                  <h3 className="font-medium text-stone-900">Ask OLI</h3>
                  <p className="text-sm text-stone-500">Get AI-powered answers</p>
                </div>
              </button>
              
              <button
                onClick={() => { setShowDiscovery(true); setShowNewProject(false); }}
                className="flex items-center gap-4 p-5 bg-white rounded-2xl border border-stone-200 hover:border-primary-300 hover:shadow-soft transition text-left group"
              >
                <div className="w-12 h-12 rounded-xl bg-drawing-50 text-drawing-600 flex items-center justify-center group-hover:bg-drawing-100 transition">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-medium text-stone-900">Discover Projects</h3>
                  <p className="text-sm text-stone-500">Find projects in shared folders</p>
                </div>
              </button>
              
              <button
                onClick={() => { setShowNewProject(true); setShowDiscovery(false); }}
                className="flex items-center gap-4 p-5 bg-white rounded-2xl border border-stone-200 hover:border-primary-300 hover:shadow-soft transition text-left group"
              >
                <div className="w-12 h-12 rounded-xl bg-spec-50 text-spec-600 flex items-center justify-center group-hover:bg-spec-100 transition">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                </div>
                <div>
                  <h3 className="font-medium text-stone-900">New Project</h3>
                  <p className="text-sm text-stone-500">Create manually</p>
                </div>
              </button>
            </div>

            {/* Projects & New Project Form / Discovery */}
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Projects List */}
              <div className={showNewProject || showDiscovery ? "lg:col-span-2" : "lg:col-span-3"}>
                <Card padding="none">
                  <CardHeader className="px-6 pt-6 pb-4">
                    <CardTitle>Your Projects</CardTitle>
                    <Badge variant="default">{projects.length} projects</Badge>
                  </CardHeader>
                  
                  <div className="px-6 pb-6">
                    {projectsLoading ? (
                      <SkeletonList count={3} />
                    ) : projects.length === 0 ? (
                      <EmptyState 
                        onCreateProject={() => setShowNewProject(true)} 
                        onDiscover={() => setShowDiscovery(true)}
                      />
                    ) : (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                        {projects.map((project) => (
                          <ProjectCard
                            key={project.id}
                            project={project}
                            isSelected={selectedProjectId === project.id}
                            onClick={() => handleSelectProject(project)}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </Card>
              </div>

              {/* New Project Form */}
              {showNewProject && (
                <div className="lg:col-span-1">
                  <FolderConfig 
                    onProjectCreated={handleProjectCreated}
                    onCancel={() => setShowNewProject(false)}
                  />
                </div>
              )}

              {/* Project Discovery */}
              {showDiscovery && (
                <div className="lg:col-span-1">
                  <ProjectDiscovery
                    onProjectCreated={handleProjectCreated}
                    onClose={() => setShowDiscovery(false)}
                  />
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

function ProjectCard({
  project,
  isSelected,
  onClick,
}: {
  project: ProjectWithStats;
  isSelected: boolean;
  onClick: () => void;
}) {
  const totalDocs = project.rfi_count + (project.submittal_count || 0);
  
  return (
    <button
      onClick={onClick}
      className={`
        w-full text-left p-4 rounded-xl border-2 transition-all duration-200
        ${isSelected
          ? 'border-primary-500 bg-primary-50 shadow-sm'
          : 'border-stone-200 hover:border-stone-300 hover:bg-stone-50'
        }
      `}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
            isSelected ? 'bg-primary-100 text-primary-700' : 'bg-stone-100 text-stone-500'
          }`}>
            <FolderIcon />
          </div>
          <div>
            <h3 className="font-medium text-stone-900">{project.name}</h3>
            <p className="text-xs text-stone-500">
              {project.last_scanned 
                ? `Updated ${new Date(project.last_scanned).toLocaleDateString()}`
                : 'Not scanned yet'
              }
            </p>
          </div>
        </div>
        {project.result_count > 0 && (
          <Badge variant="success" size="sm">{project.result_count} analyzed</Badge>
        )}
      </div>
      
      <div className="flex flex-wrap gap-2">
        {project.rfi_count > 0 && <Badge variant="rfi">{project.rfi_count} RFIs</Badge>}
        {(project.submittal_count || 0) > 0 && <Badge variant="submittal">{project.submittal_count} Submittals</Badge>}
        {project.spec_count > 0 && <Badge variant="spec">{project.spec_count} Knowledge</Badge>}
        {totalDocs === 0 && project.spec_count === 0 && (
          <span className="text-xs text-stone-400">No documents yet</span>
        )}
      </div>
    </button>
  );
}

function EmptyState({ onCreateProject, onDiscover }: { onCreateProject: () => void; onDiscover?: () => void }) {
  return (
    <div className="text-center py-12">
      <div className="w-16 h-16 mx-auto rounded-2xl bg-stone-100 flex items-center justify-center mb-4">
        <FolderIcon />
      </div>
      <h3 className="text-lg font-medium text-stone-900 mb-2">No projects yet</h3>
      <p className="text-stone-500 mb-6 max-w-sm mx-auto">
        Discover projects from your shared folders, or create one manually to start analyzing RFIs and submittals.
      </p>
      <div className="flex gap-3 justify-center">
        {onDiscover && (
          <Button variant="primary" onClick={onDiscover}>
            Discover Projects
          </Button>
        )}
        <Button variant={onDiscover ? "secondary" : "primary"} onClick={onCreateProject}>
          Create Manually
        </Button>
      </div>
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
