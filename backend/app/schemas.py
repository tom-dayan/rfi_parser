from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


# Enums for document types and statuses
DocumentType = Literal['rfi', 'submittal']
ContentType = Literal['rfi', 'submittal', 'specification', 'drawing', 'image', 'other']
SubmittalStatus = Literal[
    'no_exceptions',
    'approved_as_noted',
    'revise_and_resubmit',
    'rejected',
    'see_comments'
]


# Project schemas
class ProjectCreate(BaseModel):
    name: str
    rfi_folder_path: str
    specs_folder_path: str


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    rfi_folder_path: Optional[str] = None
    specs_folder_path: Optional[str] = None


class Project(BaseModel):
    id: int
    name: str
    rfi_folder_path: str
    specs_folder_path: str
    created_date: datetime
    last_scanned: Optional[datetime] = None
    kb_indexed: bool = False
    kb_last_indexed: Optional[datetime] = None
    kb_document_count: int = 0

    class Config:
        from_attributes = True


class ProjectWithStats(Project):
    """Project with file counts"""
    total_files: int = 0
    rfi_count: int = 0
    submittal_count: int = 0
    spec_count: int = 0
    drawing_count: int = 0
    result_count: int = 0


# Project File schemas
class ProjectFileBase(BaseModel):
    file_path: str
    filename: str
    file_type: str
    file_size: int
    modified_date: datetime
    content_type: ContentType


class ProjectFile(ProjectFileBase):
    id: int
    project_id: int
    last_indexed: Optional[datetime] = None
    content_text: Optional[str] = None
    file_metadata: Optional[dict] = None
    kb_indexed: bool = False
    kb_chunk_count: int = 0

    class Config:
        from_attributes = True


class ProjectFileSummary(BaseModel):
    """Lightweight file info for listing"""
    id: int
    filename: str
    file_type: str
    file_size: int
    content_type: str
    has_content: bool = False
    kb_indexed: bool = False

    class Config:
        from_attributes = True


# Scan result schemas
class ScanResult(BaseModel):
    project_id: int
    files_found: int
    files_added: int
    files_updated: int
    files_removed: int


# Knowledge base schemas
class KnowledgeBaseStats(BaseModel):
    project_id: int
    indexed: bool
    document_count: int
    last_indexed: Optional[datetime] = None
    embedding_model: Optional[str] = None


class IndexResult(BaseModel):
    project_id: int
    files_indexed: int
    chunks_created: int
    errors: list[str] = []


# Specification reference in results
class SpecReference(BaseModel):
    source_file_id: int
    source_filename: str
    section: Optional[str] = None
    text: str
    score: float


# Processing Result schemas
class ProcessingResultCreate(BaseModel):
    source_file_id: int
    document_type: DocumentType
    response_text: Optional[str] = None
    status: Optional[SubmittalStatus] = None  # Only for submittals
    consultant_type: Optional[str] = None
    confidence: float = 0.0
    spec_references: Optional[list[SpecReference]] = None


class ProcessingResult(BaseModel):
    id: int
    project_id: int
    source_file_id: int
    document_type: DocumentType
    response_text: Optional[str] = None
    status: Optional[SubmittalStatus] = None  # Only for submittals
    consultant_type: Optional[str] = None
    confidence: float
    processed_date: datetime
    spec_references: Optional[list[dict]] = None

    class Config:
        from_attributes = True


class ProcessingResultWithFile(ProcessingResult):
    """Processing Result with the associated source file info"""
    source_file: ProjectFileSummary


# Processing request schemas
class ProcessRequest(BaseModel):
    """Request to process documents"""
    file_ids: Optional[list[int]] = None  # Process specific files, or all if None
    document_type: Optional[DocumentType] = None  # Filter by type


class ProcessResponse(BaseModel):
    message: str
    results_count: int
    results: list[ProcessingResult]


# Folder validation
class FolderValidation(BaseModel):
    path: str
    exists: bool
    is_directory: bool
    readable: bool
    file_count: int = 0
    error: Optional[str] = None


# AI Response schemas (for structured AI output)
class RFIResponse(BaseModel):
    """AI response for an RFI (informational)"""
    response_text: str
    spec_references: list[SpecReference]
    consultant_type: Optional[str] = None
    confidence: float


class SubmittalResponse(BaseModel):
    """AI response for a Submittal (review with status)"""
    response_text: str
    status: SubmittalStatus
    spec_references: list[SpecReference]
    consultant_type: Optional[str] = None
    confidence: float


# Scan progress event schemas (for SSE streaming)
class ScanProgressEvent(BaseModel):
    """Progress event during folder scan"""
    event_type: Literal['start', 'scanning', 'parsing', 'complete', 'error']
    current_file: Optional[str] = None
    current_file_index: int = 0
    total_files: int = 0
    phase: Optional[str] = None  # 'rfi' or 'specs'
    message: Optional[str] = None
    # Final result (only on 'complete')
    result: Optional[ScanResult] = None
    error: Optional[str] = None
