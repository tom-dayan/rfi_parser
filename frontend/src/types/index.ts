export type RFIStatus = 'accepted' | 'rejected' | 'comment' | 'refer_to_consultant';
export type ContentType = 'rfi' | 'specification' | 'drawing' | 'image' | 'other';

// Project types
export interface Project {
  id: number;
  name: string;
  rfi_folder_path: string;
  specs_folder_path: string;
  created_date: string;
  last_scanned?: string;
}

export interface ProjectWithStats extends Project {
  total_files: number;
  rfi_count: number;
  spec_count: number;
  drawing_count: number;
  result_count: number;
}

export interface ProjectCreate {
  name: string;
  rfi_folder_path: string;
  specs_folder_path: string;
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
}

export interface ProjectFileSummary {
  id: number;
  filename: string;
  file_type: string;
  file_size: number;
  content_type: ContentType;
  has_content: boolean;
}

// Scan result
export interface ScanResult {
  project_id: number;
  files_found: number;
  files_added: number;
  files_updated: number;
  files_removed: number;
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

// RFI Result types
export interface SpecReference {
  file_id?: number;
  filename: string;
  section?: string;
  quote?: string;
}

export interface RFIResult {
  id: number;
  project_id: number;
  rfi_file_id: number;
  status: RFIStatus;
  consultant_type?: string;
  reason?: string;
  confidence: number;
  processed_date: string;
  referenced_file_ids?: number[];
  spec_references?: SpecReference[];
}

export interface RFIResultWithFile extends RFIResult {
  rfi_file: ProjectFileSummary;
}

// Processing types
export interface ProcessRequest {
  rfi_file_ids?: number[];
}

export interface ProcessResponse {
  message: string;
  results_count: number;
  results: RFIResult[];
}
