import axios from 'axios';
import type {
  Project,
  ProjectWithStats,
  ProjectCreate,
  ProjectFileSummary,
  ProjectFile,
  ScanResult,
  ScanProgressEvent,
  FolderValidation,
  ProcessingResultWithFile,
  ProcessRequest,
  ProcessResponse,
  KnowledgeBaseStats,
  IndexResult,
  DocumentType,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Projects API
export const createProject = async (project: ProjectCreate): Promise<Project> => {
  const response = await api.post<Project>('/api/projects', project);
  return response.data;
};

export const getProjects = async (): Promise<ProjectWithStats[]> => {
  const response = await api.get<ProjectWithStats[]>('/api/projects');
  return response.data;
};

export const getProject = async (projectId: number): Promise<ProjectWithStats> => {
  const response = await api.get<ProjectWithStats>(`/api/projects/${projectId}`);
  return response.data;
};

export const updateProject = async (projectId: number, update: Partial<ProjectCreate>): Promise<Project> => {
  const response = await api.put<Project>(`/api/projects/${projectId}`, update);
  return response.data;
};

export const deleteProject = async (projectId: number): Promise<void> => {
  await api.delete(`/api/projects/${projectId}`);
};

export const scanProject = async (projectId: number, parseContent: boolean = true): Promise<ScanResult> => {
  const response = await api.post<ScanResult>(
    `/api/projects/${projectId}/scan`,
    null,
    { params: { parse_content: parseContent } }
  );
  return response.data;
};

// Streaming scan with progress updates
export const scanProjectStream = (
  projectId: number,
  onProgress: (event: ScanProgressEvent) => void,
  parseContent: boolean = true
): { cancel: () => void } => {
  const url = `${API_BASE_URL}/api/projects/${projectId}/scan-stream?parse_content=${parseContent}`;
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data: ScanProgressEvent = JSON.parse(event.data);
      onProgress(data);

      // Close connection when complete or error
      if (data.event_type === 'complete' || data.event_type === 'error') {
        eventSource.close();
      }
    } catch (e) {
      console.error('Failed to parse SSE event:', e);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    onProgress({
      event_type: 'error',
      current_file_index: 0,
      total_files: 0,
      error: 'Connection lost. Please try again.',
      message: 'Connection lost'
    });
  };

  return {
    cancel: () => {
      eventSource.close();
    }
  };
};

export const getProjectFiles = async (
  projectId: number,
  contentType?: string
): Promise<ProjectFileSummary[]> => {
  const response = await api.get<ProjectFileSummary[]>(
    `/api/projects/${projectId}/files`,
    { params: contentType ? { content_type: contentType } : undefined }
  );
  return response.data;
};

// Project Discovery API
export interface ProjectCandidate {
  name: string;
  root_path: string;
  rfi_folder: string | null;
  specs_folder: string | null;
  confidence: number;
  file_count: number;
  rfi_count: number;
  spec_count: number;
  reasons: string[];
}

export interface DiscoverProjectsResponse {
  root_paths: string[];
  candidates: ProjectCandidate[];
  total: number;
}

export const discoverProjects = async (
  rootPath?: string,
  maxDepth: number = 3,
  minConfidence: number = 0.3
): Promise<DiscoverProjectsResponse> => {
  const params: Record<string, string | number> = {
    max_depth: maxDepth,
    min_confidence: minConfidence,
  };
  if (rootPath) {
    params.root_path = rootPath;
  }
  const response = await api.get<DiscoverProjectsResponse>(
    '/api/projects/discover',
    { params }
  );
  return response.data;
};

// Files API
export const getFile = async (fileId: number): Promise<ProjectFile> => {
  const response = await api.get<ProjectFile>(`/api/files/${fileId}`);
  return response.data;
};

export const getFileContent = async (fileId: number): Promise<{
  id: number;
  filename: string;
  content_type: string;
  content_text: string | null;
  file_metadata: Record<string, unknown> | null;
}> => {
  const response = await api.get(`/api/files/${fileId}/content`);
  return response.data;
};

export const reparseFile = async (fileId: number): Promise<{
  success: boolean;
  message: string;
  content_length?: number;
}> => {
  const response = await api.post(`/api/files/${fileId}/reparse`);
  return response.data;
};

// Knowledge Base API
export const indexKnowledgeBase = async (
  projectId: number,
  force: boolean = false
): Promise<IndexResult> => {
  const response = await api.post<IndexResult>(
    `/api/projects/${projectId}/index`,
    null,
    { params: { force } }
  );
  return response.data;
};

export const getKnowledgeBaseStats = async (projectId: number): Promise<KnowledgeBaseStats> => {
  const response = await api.get<KnowledgeBaseStats>(
    `/api/projects/${projectId}/knowledge-base`
  );
  return response.data;
};

export const clearKnowledgeBase = async (projectId: number): Promise<void> => {
  await api.delete(`/api/projects/${projectId}/knowledge-base`);
};

// Processing API
export const processDocuments = async (
  projectId: number,
  request: ProcessRequest = {}
): Promise<ProcessResponse> => {
  const response = await api.post<ProcessResponse>(
    `/api/projects/${projectId}/process`,
    request
  );
  return response.data;
};

// Processing Progress Event type
export interface ProcessProgressEvent {
  event_type: 'start' | 'processing' | 'file_complete' | 'complete' | 'error';
  current_file?: string;
  current_file_index?: number;
  total_files?: number;
  processed?: number;
  errors?: number;
  success?: boolean;
  error?: string;
  message: string;
}

// Streaming process with progress updates
export const processDocumentsStream = (
  projectId: number,
  onProgress: (event: ProcessProgressEvent) => void,
  documentType?: string
): { cancel: () => void } => {
  const params = new URLSearchParams();
  if (documentType) params.append('document_type', documentType);
  
  const url = `${API_BASE_URL}/api/projects/${projectId}/process-stream${params.toString() ? `?${params}` : ''}`;
  
  const eventSource = new EventSource(url);

  eventSource.onmessage = (event) => {
    try {
      const data: ProcessProgressEvent = JSON.parse(event.data);
      onProgress(data);

      // Close connection when complete or error
      if (data.event_type === 'complete' || data.event_type === 'error') {
        eventSource.close();
      }
    } catch (e) {
      console.error('Failed to parse SSE event:', e);
    }
  };

  eventSource.onerror = () => {
    eventSource.close();
    onProgress({
      event_type: 'error',
      message: 'Connection lost. Please try again.'
    });
  };

  return {
    cancel: () => {
      eventSource.close();
    }
  };
};

export const getProjectResults = async (
  projectId: number,
  documentType?: DocumentType,
  status?: string
): Promise<ProcessingResultWithFile[]> => {
  const params: Record<string, string> = {};
  if (documentType) params.document_type = documentType;
  if (status) params.status = status;

  const response = await api.get<ProcessingResultWithFile[]>(
    `/api/projects/${projectId}/results`,
    { params: Object.keys(params).length > 0 ? params : undefined }
  );
  return response.data;
};

export const deleteResult = async (resultId: number): Promise<void> => {
  await api.delete(`/api/results/${resultId}`);
};

export const updateResult = async (
  resultId: number,
  data: { response_text?: string; status?: string }
): Promise<ProcessingResultWithFile> => {
  const response = await api.patch<ProcessingResultWithFile>(
    `/api/results/${resultId}`,
    data
  );
  return response.data;
};

// Refine result: re-analyze with updated spec selections
export interface RefineResultResponse {
  id: number;
  response_text: string;
  confidence: number;
  consultant_type?: string;
  status?: string;
  spec_references?: SpecReference[];
  processed_date?: string;
}

export const refineResult = async (
  resultId: number,
  specFilePaths: string[],
  instructions?: string
): Promise<RefineResultResponse> => {
  const response = await api.post<RefineResultResponse>(
    `/api/results/${resultId}/refine`,
    { spec_file_paths: specFilePaths, instructions }
  );
  return response.data;
};

// Utility API
export const validateFolder = async (path: string): Promise<FolderValidation> => {
  const response = await api.post<FolderValidation>(
    '/api/projects/validate-folder',
    null,
    { params: { path } }
  );
  return response.data;
};

// Directory browser
export interface DirectoryEntry {
  name: string;
  path: string;
  has_children: boolean;
  access_denied?: boolean;
}

export interface BrowseResult {
  current_path: string;
  parent_path: string | null;
  directories: DirectoryEntry[];
}

export const browseDirectory = async (path?: string): Promise<BrowseResult> => {
  const response = await api.get<BrowseResult>(
    '/api/files/browse',
    { params: path ? { path } : undefined }
  );
  return response.data;
};

// Chat API
export interface ChatMessage {
  content: string;
  project_id?: number;
  session_id?: string;
}

export interface ChatResponse {
  content: string;
  session_id: string;
  sources: Array<{
    filename: string;
    section?: string;
    path?: string;
    relevance?: number;
  }>;
  timestamp: string;
}

export const sendChatMessage = async (message: ChatMessage): Promise<ChatResponse> => {
  const response = await api.post<ChatResponse>('/api/chat/message', message);
  return response.data;
};

export const getChatHistory = async (sessionId: string): Promise<{ messages: Array<{
  role: string;
  content: string;
  timestamp: string;
  sources?: Array<{ filename: string }>;
}>}> => {
  const response = await api.get(`/api/chat/history/${sessionId}`);
  return response.data;
};

export const clearChatHistory = async (sessionId: string): Promise<void> => {
  await api.delete(`/api/chat/history/${sessionId}`);
};

// Search API
export interface SearchResult {
  path: string;
  filename: string;
  extension?: string;
  file_type?: string;
  size_bytes?: number;
  modified_at?: string;
  project_name?: string;
}

export interface SearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
  source: string;
}

export const searchFiles = async (params: {
  q: string;
  file_type?: string;
  extension?: string;
  project_id?: number;
  limit?: number;
}): Promise<SearchResponse> => {
  const response = await api.get<SearchResponse>('/api/search', { params });
  return response.data;
};

export const searchDrawings = async (params: {
  q: string;
  project_id?: number;
  limit?: number;
}): Promise<SearchResponse> => {
  const response = await api.get<SearchResponse>('/api/search/drawings', { params });
  return response.data;
};

export const getSearchContent = async (path: string, maxLength?: number): Promise<{
  path: string;
  filename: string;
  content: string;
  was_cached: boolean;
}> => {
  const response = await api.get('/api/search/content', {
    params: { path, max_length: maxLength }
  });
  return response.data;
};

export const getSearchStats = async (): Promise<{
  index: Record<string, unknown>;
  cache: Record<string, unknown>;
}> => {
  const response = await api.get('/api/search/stats');
  return response.data;
};

// Smart Analysis API

export interface BrowseFile {
  name: string;
  path: string;
  relative_path: string;
  size: number;
  modified: string;
  extension: string;
}

export interface BrowseFolderResponse {
  files: BrowseFile[];
  folder: string;
  folder_type: string;
  total: number;
  error?: string;
}

export const browseProjectFolder = async (
  projectId: number,
  folderType: 'rfi' | 'submittal' | 'spec' = 'rfi',
  recursive: boolean = true
): Promise<BrowseFolderResponse> => {
  const response = await api.get<BrowseFolderResponse>(
    `/api/projects/${projectId}/browse`,
    { params: { folder_type: folderType, recursive } }
  );
  return response.data;
};

export interface SpecSuggestion {
  name: string;
  path: string;
  relative_path: string;
  relevance_score: number;
  matched_terms: string[];
  extension: string;
  size?: number;
  modified?: string;
}

export interface RfiSpecSuggestions {
  rfi_id: number;
  rfi_filename: string;
  rfi_title: string | null;
  extracted_keywords: string[];
  spec_references: string[];
  suggested_specs: SpecSuggestion[];
  total_specs_found: number;
}

export interface SuggestSpecsResponse {
  suggestions: RfiSpecSuggestions[];
  project_id: number;
  specs_folder: string;
  total_spec_files: number;
}

export const suggestSpecs = async (
  projectId: number,
  rfiFileIds: number[]
): Promise<SuggestSpecsResponse> => {
  // Send rfi_file_ids as query params (FastAPI expects list as repeated params)
  const params = new URLSearchParams();
  rfiFileIds.forEach(id => params.append('rfi_file_ids', String(id)));
  
  const response = await api.post<SuggestSpecsResponse>(
    `/api/projects/${projectId}/suggest-specs?${params.toString()}`,
    null
  );
  return response.data;
};

export interface SmartAnalysisRequest {
  analyses: Array<{
    rfi_file_id: number;
    spec_file_paths: string[];
  }>;
}

export interface SmartAnalysisResult {
  rfi_file_id: number;
  rfi_filename: string;
  success: boolean;
  result_id?: number;
  response_preview?: string;
  confidence?: number;
  specs_used?: string[];
  error?: string;
}

export interface SmartAnalysisResponse {
  project_id: number;
  results: SmartAnalysisResult[];
  total_processed: number;
  successful: number;
}

export const smartAnalyze = async (
  projectId: number,
  request: SmartAnalysisRequest
): Promise<SmartAnalysisResponse> => {
  const response = await api.post<SmartAnalysisResponse>(
    `/api/projects/${projectId}/smart-analyze`,
    request
  );
  return response.data;
};

// Smart Analysis Progress Event type
export interface SmartAnalysisProgressEvent {
  event_type: 'start' | 'parsing' | 'parsing_spec' | 'generating' | 'completed' | 'warning' | 'error' | 'done' | 'fatal_error';
  rfi_id?: number;
  rfi_filename?: string;
  spec_name?: string;
  spec_count?: number;
  spec_index?: number;
  spec_total?: number;
  specs_parsed?: number;
  result_id?: number;
  confidence?: number;
  current_index?: number;
  total?: number;
  completed?: number;
  error?: string;
  message: string;
}

// Streaming smart analysis with progress updates
export const smartAnalyzeStream = (
  projectId: number,
  request: SmartAnalysisRequest,
  onProgress: (event: SmartAnalysisProgressEvent) => void
): { cancel: () => void } => {
  // For SSE, we need to send a POST first, then use EventSource
  // Since EventSource only supports GET, we'll use fetch with ReadableStream
  const controller = new AbortController();
  
  const fetchStream = async () => {
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/projects/${projectId}/smart-analyze-stream`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(request),
          signal: controller.signal,
        }
      );

      const reader = response.body?.getReader();
      if (!reader) {
        onProgress({ event_type: 'error', message: 'Failed to get stream reader' });
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data: SmartAnalysisProgressEvent = JSON.parse(line.slice(6));
              onProgress(data);
            } catch {
              console.warn('Failed to parse SSE data:', line);
            }
          }
        }
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        onProgress({ event_type: 'error', message: `Stream error: ${(error as Error).message}` });
      }
    }
  };

  fetchStream();

  return {
    cancel: () => controller.abort()
  };
};

// Updated Chat API with actions
export interface ChatAction {
  action_type: string;
  label: string;
  description: string;
  params: Record<string, unknown>;
  icon?: string;
}

export interface ChatResponseWithActions extends ChatResponse {
  actions: ChatAction[];
  detected_intent?: string;
}

// ============================================
// Path-based Smart Analysis (No DB required)
// ============================================

export interface RfiFileInput {
  path: string;
  name: string;
}

export interface PathBasedSpecSuggestion {
  name: string;
  path: string;
  relative_path: string;
  extension: string;
  relevance_score?: number;
  matched_terms?: string[];
  folder?: string;
  size?: number;
}

export interface PathBasedRfiSuggestions {
  rfi_path: string;
  rfi_filename: string;
  rfi_title: string | null;
  extracted_keywords: string[];
  spec_references: string[];
  suggested_specs: PathBasedSpecSuggestion[];
  total_specs_found: number;
}

export interface PathBasedSuggestResponse {
  suggestions: PathBasedRfiSuggestions[];
  project_id: number;
  specs_folder: string;
  total_spec_files: number;
  all_spec_files?: PathBasedSpecSuggestion[];
  folder_structure?: Record<string, unknown>;
  error?: string;
}

// Spec folder tree response
export interface SpecFolderTreeResponse {
  specs_folder: string;
  total_files: number;
  files: PathBasedSpecSuggestion[];
  folders: string[];
  error?: string;
}

// Suggest specs from file paths (no database required)
export const suggestSpecsFromPaths = async (
  projectId: number,
  rfiFiles: RfiFileInput[]
): Promise<PathBasedSuggestResponse> => {
  const response = await api.post<PathBasedSuggestResponse>(
    `/api/projects/${projectId}/suggest-specs-from-paths`,
    { rfi_files: rfiFiles }
  );
  return response.data;
};

// Get spec folder tree for browsing
export const getSpecFolderTree = async (
  projectId: number
): Promise<SpecFolderTreeResponse> => {
  const response = await api.get<SpecFolderTreeResponse>(
    `/api/projects/${projectId}/spec-folder-tree`
  );
  return response.data;
};

export interface PathBasedAnalysisRequest {
  analyses: Array<{
    rfi_path: string;
    rfi_name: string;
    spec_file_paths: string[];
  }>;
}

export interface PathBasedAnalysisResult {
  rfi_path: string;
  rfi_name: string;
  response: string | null;
  specs_used?: string[];
  result_id?: number;
  error?: string;
}

export interface PathBasedAnalysisResponse {
  results: PathBasedAnalysisResult[];
  project_id: number;
}

// Smart analyze from file paths (no database required for RFIs)
export const smartAnalyzeFromPaths = async (
  projectId: number,
  request: PathBasedAnalysisRequest
): Promise<PathBasedAnalysisResponse> => {
  const response = await api.post<PathBasedAnalysisResponse>(
    `/api/projects/${projectId}/smart-analyze-from-paths`,
    request
  );
  return response.data;
};
