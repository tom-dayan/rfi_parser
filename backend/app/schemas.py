from pydantic import BaseModel
from datetime import datetime
from typing import Optional, Literal


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

    class Config:
        from_attributes = True


class ProjectWithStats(Project):
    """Project with file counts"""
    total_files: int = 0
    rfi_count: int = 0
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
    content_type: Literal['rfi', 'specification', 'drawing', 'image', 'other']


class ProjectFile(ProjectFileBase):
    id: int
    project_id: int
    last_indexed: Optional[datetime] = None
    content_text: Optional[str] = None
    file_metadata: Optional[dict] = None

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

    class Config:
        from_attributes = True


# Scan result schemas
class ScanResult(BaseModel):
    project_id: int
    files_found: int
    files_added: int
    files_updated: int
    files_removed: int


# RFI Result schemas
class SpecReference(BaseModel):
    file_id: int
    filename: str
    section: Optional[str] = None
    quote: Optional[str] = None


class RFIResultCreate(BaseModel):
    rfi_file_id: int
    status: Literal['accepted', 'rejected', 'comment', 'refer_to_consultant']
    consultant_type: Optional[str] = None
    reason: Optional[str] = None
    confidence: float = 0.0
    referenced_file_ids: Optional[list[int]] = None
    spec_references: Optional[list[dict]] = None


class RFIResult(BaseModel):
    id: int
    project_id: int
    rfi_file_id: int
    status: Literal['accepted', 'rejected', 'comment', 'refer_to_consultant']
    consultant_type: Optional[str] = None
    reason: Optional[str] = None
    confidence: float
    processed_date: datetime
    referenced_file_ids: Optional[list[int]] = None
    spec_references: Optional[list[dict]] = None

    class Config:
        from_attributes = True


class RFIResultWithFile(RFIResult):
    """RFI Result with the associated RFI file info"""
    rfi_file: ProjectFileSummary


# Processing schemas
class ProcessRequest(BaseModel):
    rfi_file_ids: Optional[list[int]] = None  # Process specific RFIs, or all if None


class ProcessResponse(BaseModel):
    message: str
    results_count: int
    results: list[RFIResult]


# Folder validation
class FolderValidation(BaseModel):
    path: str
    exists: bool
    is_directory: bool
    readable: bool
    file_count: int = 0
    error: Optional[str] = None
