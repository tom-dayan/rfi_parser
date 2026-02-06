// Document and content types
export type DocumentType = 'rfi' | 'submittal';
export type ContentType = 'rfi' | 'submittal' | 'specification' | 'drawing' | 'image' | 'other';
export type SubmittalStatus =
  | 'no_exceptions'
  | 'approved_as_noted'
  | 'revise_and_resubmit'
  | 'rejected'
  | 'see_comments';

// Project types
export interface Project {
  id: number;
  name: string;
  rfi_folder_path: string;
  specs_folder_path: string;
  created_date: string;
  last_scanned?: string;
  exclude_folders?: string[];
  kb_indexed: boolean;
  kb_last_indexed?: string;
  kb_document_count: number;
}

export interface ProjectWithStats extends Project {
  total_files: number;
  rfi_count: number;
  submittal_count: number;
  spec_count: number;
  drawing_count: number;
  result_count: number;
}

export interface ProjectCreate {
  name: string;
  rfi_folder_path: string;
  specs_folder_path: string;
  exclude_folders?: string[];
}

// Project File types
export interface ProjectFile {
  id: number;
  project_id: number;
  file_path: string;
  filename: string;
  file_type: string;
  file_size: number;
  modified_date: string;
  content_type: ContentType;
  last_indexed?: string;
  content_text?: string;
  file_metadata?: Record<string, unknown>;
  kb_indexed: boolean;
  kb_chunk_count: number;
}

export interface ProjectFileSummary {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  content_type: ContentType;
  has_content: boolean;
  kb_indexed: boolean;
}

// Scan result
export interface ScanResult {
  project_id: number;
  files_found: number;
  files_added: number;
  files_updated: number;
  files_removed: number;
}

// Scan progress event (for SSE streaming)
export type ScanEventType = 'start' | 'scanning' | 'parsing' | 'complete' | 'error';

export interface ScanProgressEvent {
  event_type: ScanEventType;
  current_file?: string;
  current_file_index: number;
  total_files: number;
  phase?: 'rfi' | 'specs';
  message?: string;
  result?: ScanResult;
  error?: string;
}

// Knowledge base types
export interface KnowledgeBaseStats {
  project_id: number;
  indexed: boolean;
  document_count: number;
  last_indexed?: string;
  embedding_model?: string;
}

export interface IndexResult {
  project_id: number;
  files_indexed: number;
  chunks_created: number;
  errors: string[];
}

// Folder validation
export interface FolderValidation {
  path: string;
  exists: boolean;
  is_directory: boolean;
  readable: boolean;
  file_count: number;
  error?: string;
}

// Specification reference in results
export interface SpecReference {
  source_file_id?: number;
  source_filename: string;
  section?: string;
  text: string;
  score: number;
}

// Processing Result types
export interface ProcessingResult {
  id: number;
  project_id: number;
  source_file_id: number;
  document_type: DocumentType;
  response_text?: string;
  status?: SubmittalStatus;  // Only for submittals
  consultant_type?: string;
  confidence: number;
  processed_date: string;
  spec_references?: SpecReference[];
}

export interface ProcessingResultWithFile extends ProcessingResult {
  source_file: ProjectFileSummary;
}

// Processing request types
export interface ProcessRequest {
  file_ids?: number[];
  document_type?: DocumentType;
}

export interface ProcessResponse {
  message: string;
  results_count: number;
  results: ProcessingResult[];
}

// Status display helpers
export const submittalStatusLabels: Record<SubmittalStatus, string> = {
  no_exceptions: 'No Exceptions Taken',
  approved_as_noted: 'Approved as Noted',
  revise_and_resubmit: 'Revise and Resubmit',
  rejected: 'Rejected',
  see_comments: 'See Comments'
};

export const submittalStatusColors: Record<SubmittalStatus, string> = {
  no_exceptions: 'bg-green-100 text-green-800',
  approved_as_noted: 'bg-blue-100 text-blue-800',
  revise_and_resubmit: 'bg-yellow-100 text-yellow-800',
  rejected: 'bg-red-100 text-red-800',
  see_comments: 'bg-gray-100 text-gray-800'
};
