import axios from 'axios';
import type {
  Project,
  ProjectWithStats,
  ProjectCreate,
  ProjectFileSummary,
  ProjectFile,
  ScanResult,
  FolderValidation,
  RFIResultWithFile,
  ProcessRequest,
  ProcessResponse,
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

// Processing API
export const processProjectRFIs = async (
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
  status?: string
): Promise<RFIResultWithFile[]> => {
  const response = await api.get<RFIResultWithFile[]>(
    `/api/projects/${projectId}/results`,
    { params: status ? { status } : undefined }
  );
  return response.data;
};

export const deleteResult = async (resultId: number): Promise<void> => {
  await api.delete(`/api/results/${resultId}`);
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
