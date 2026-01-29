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
