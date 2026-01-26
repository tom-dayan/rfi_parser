import os
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import Project, ProjectFile, RFIResult
from ..schemas import (
    ProjectCreate, ProjectUpdate, Project as ProjectSchema,
    ProjectWithStats, ProjectFileSummary, ScanResult, FolderValidation
)
from ..services.file_scanner import FileScanner
from ..services.parsers import get_parser_registry

router = APIRouter(prefix="/api/projects", tags=["projects"])

# Initialize services
file_scanner = FileScanner()
parser_registry = get_parser_registry()


@router.post("", response_model=ProjectSchema)
def create_project(project: ProjectCreate, db: Session = Depends(get_db)):
    """Create a new project with folder paths"""

    # Validate folders exist
    for path, name in [(project.rfi_folder_path, "RFI"), (project.specs_folder_path, "Specs")]:
        if not os.path.exists(path):
            raise HTTPException(status_code=400, detail=f"{name} folder does not exist: {path}")
        if not os.path.isdir(path):
            raise HTTPException(status_code=400, detail=f"{name} path is not a directory: {path}")

    db_project = Project(
        name=project.name,
        rfi_folder_path=project.rfi_folder_path,
        specs_folder_path=project.specs_folder_path
    )
    db.add(db_project)
    db.commit()
    db.refresh(db_project)

    return db_project


@router.get("", response_model=list[ProjectWithStats])
def list_projects(db: Session = Depends(get_db)):
    """List all projects with stats"""
    projects = db.query(Project).all()
    result = []

    for project in projects:
        # Count files by type
        files = db.query(ProjectFile).filter(ProjectFile.project_id == project.id).all()
        results_count = db.query(RFIResult).filter(RFIResult.project_id == project.id).count()

        result.append(ProjectWithStats(
            **ProjectSchema.model_validate(project).model_dump(),
            total_files=len(files),
            rfi_count=sum(1 for f in files if f.content_type == 'rfi'),
            spec_count=sum(1 for f in files if f.content_type == 'specification'),
            drawing_count=sum(1 for f in files if f.content_type == 'drawing'),
            result_count=results_count
        ))

    return result


@router.get("/{project_id}", response_model=ProjectWithStats)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a project by ID with stats"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    files = db.query(ProjectFile).filter(ProjectFile.project_id == project.id).all()
    results_count = db.query(RFIResult).filter(RFIResult.project_id == project.id).count()

    return ProjectWithStats(
        **ProjectSchema.model_validate(project).model_dump(),
        total_files=len(files),
        rfi_count=sum(1 for f in files if f.content_type == 'rfi'),
        spec_count=sum(1 for f in files if f.content_type == 'specification'),
        drawing_count=sum(1 for f in files if f.content_type == 'drawing'),
        result_count=results_count
    )


@router.put("/{project_id}", response_model=ProjectSchema)
def update_project(project_id: int, update: ProjectUpdate, db: Session = Depends(get_db)):
    """Update a project's configuration"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Validate new paths if provided
    if update.rfi_folder_path and not os.path.isdir(update.rfi_folder_path):
        raise HTTPException(status_code=400, detail="RFI folder does not exist")
    if update.specs_folder_path and not os.path.isdir(update.specs_folder_path):
        raise HTTPException(status_code=400, detail="Specs folder does not exist")

    # Update fields
    if update.name:
        project.name = update.name
    if update.rfi_folder_path:
        project.rfi_folder_path = update.rfi_folder_path
    if update.specs_folder_path:
        project.specs_folder_path = update.specs_folder_path

    db.commit()
    db.refresh(project)
    return project


@router.delete("/{project_id}")
def delete_project(project_id: int, db: Session = Depends(get_db)):
    """Delete a project and all its data"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    db.delete(project)
    db.commit()
    return {"message": "Project deleted successfully"}


@router.post("/{project_id}/scan", response_model=ScanResult)
def scan_project(project_id: int, parse_content: bool = True, db: Session = Depends(get_db)):
    """Scan project folders and index files"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    files_found = 0
    files_added = 0
    files_updated = 0
    files_removed = 0

    # Get existing files
    existing_files = {f.file_path: f for f in project.files}
    found_paths = set()

    # Scan RFI folder
    rfi_files = file_scanner.scan_folder(project.rfi_folder_path)
    for scanned in rfi_files:
        files_found += 1
        found_paths.add(scanned.file_path)
        content_type = file_scanner.classify_content_type(scanned.file_path, 'rfi')

        if scanned.file_path in existing_files:
            # Update if modified
            existing = existing_files[scanned.file_path]
            if existing.modified_date < scanned.modified_date:
                _update_file(existing, scanned, content_type, parse_content, db)
                files_updated += 1
        else:
            # Add new file
            _add_file(project.id, scanned, content_type, parse_content, db)
            files_added += 1

    # Scan specs folder
    spec_files = file_scanner.scan_folder(project.specs_folder_path)
    for scanned in spec_files:
        files_found += 1
        found_paths.add(scanned.file_path)
        content_type = file_scanner.classify_content_type(scanned.file_path, 'specs')

        if scanned.file_path in existing_files:
            existing = existing_files[scanned.file_path]
            if existing.modified_date < scanned.modified_date:
                _update_file(existing, scanned, content_type, parse_content, db)
                files_updated += 1
        else:
            _add_file(project.id, scanned, content_type, parse_content, db)
            files_added += 1

    # Remove files that no longer exist
    for path, existing in existing_files.items():
        if path not in found_paths:
            db.delete(existing)
            files_removed += 1

    # Update last scanned
    project.last_scanned = datetime.utcnow()
    db.commit()

    return ScanResult(
        project_id=project_id,
        files_found=files_found,
        files_added=files_added,
        files_updated=files_updated,
        files_removed=files_removed
    )


@router.get("/{project_id}/files", response_model=list[ProjectFileSummary])
def list_project_files(
    project_id: int,
    content_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List files in a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(ProjectFile).filter(ProjectFile.project_id == project_id)
    if content_type:
        query = query.filter(ProjectFile.content_type == content_type)

    files = query.all()
    return [
        ProjectFileSummary(
            id=f.id,
            filename=f.filename,
            file_type=f.file_type,
            file_size=f.file_size,
            content_type=f.content_type,
            has_content=bool(f.content_text)
        )
        for f in files
    ]


@router.post("/validate-folder", response_model=FolderValidation)
def validate_folder(path: str):
    """Validate a folder path"""
    result = FolderValidation(
        path=path,
        exists=os.path.exists(path),
        is_directory=os.path.isdir(path) if os.path.exists(path) else False,
        readable=os.access(path, os.R_OK) if os.path.exists(path) else False
    )

    if result.exists and result.is_directory and result.readable:
        try:
            files = file_scanner.scan_folder(path)
            result.file_count = len(files)
        except Exception as e:
            result.error = str(e)

    return result


# Helper functions
def _add_file(project_id: int, scanned, content_type: str, parse_content: bool, db: Session):
    """Add a new file to the database"""
    content_text = None
    metadata = None

    if parse_content:
        result = parser_registry.parse(scanned.file_path)
        if result.success:
            content_text = result.text_content
            metadata = result.metadata

    db_file = ProjectFile(
        project_id=project_id,
        file_path=scanned.file_path,
        filename=scanned.filename,
        file_type=scanned.file_type,
        file_size=scanned.file_size,
        modified_date=scanned.modified_date,
        content_type=content_type,
        content_text=content_text,
        file_metadata=metadata,
        last_indexed=datetime.utcnow() if parse_content else None
    )
    db.add(db_file)


def _update_file(existing: ProjectFile, scanned, content_type: str, parse_content: bool, db: Session):
    """Update an existing file"""
    existing.file_size = scanned.file_size
    existing.modified_date = scanned.modified_date
    existing.content_type = content_type

    if parse_content:
        result = parser_registry.parse(scanned.file_path)
        if result.success:
            existing.content_text = result.text_content
            existing.file_metadata = result.metadata
            existing.last_indexed = datetime.utcnow()
