import os
import json
import asyncio
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional, Generator

from ..database import get_db
from ..models import Project, ProjectFile, ProcessingResult
from ..schemas import (
    ProjectCreate, ProjectUpdate, Project as ProjectSchema,
    ProjectWithStats, ProjectFileSummary, ScanResult, FolderValidation,
    ScanProgressEvent
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
        specs_folder_path=project.specs_folder_path,
        exclude_folders=project.exclude_folders or []
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
        results_count = db.query(ProcessingResult).filter(ProcessingResult.project_id == project.id).count()

        result.append(ProjectWithStats(
            **ProjectSchema.model_validate(project).model_dump(),
            total_files=len(files),
            rfi_count=sum(1 for f in files if f.content_type == 'rfi'),
            submittal_count=sum(1 for f in files if f.content_type == 'submittal'),
            spec_count=sum(1 for f in files if f.content_type == 'specification'),
            drawing_count=sum(1 for f in files if f.content_type == 'drawing'),
            result_count=results_count
        ))

    return result


@router.get("/discover")
def discover_projects_endpoint(
    root_path: Optional[str] = None,
    max_depth: int = 3,
    min_confidence: float = 0.3,
):
    """
    Discover potential projects from shared folder roots.
    
    If root_path is not provided, uses the configured SHARED_FOLDERS_ROOT.
    """
    from ..services.project_discovery import discover_projects
    from ..config import settings
    
    # Use provided root or fall back to configured root
    if root_path:
        root_paths = [root_path]
    elif settings.shared_folders_root:
        # Split by comma in case multiple roots are configured
        root_paths = [p.strip() for p in settings.shared_folders_root.split(',')]
    else:
        raise HTTPException(
            status_code=400, 
            detail="No root path provided and SHARED_FOLDERS_ROOT is not configured"
        )
    
    # Validate roots exist
    valid_roots = []
    for rp in root_paths:
        if os.path.exists(rp) and os.path.isdir(rp):
            valid_roots.append(rp)
    
    if not valid_roots:
        raise HTTPException(
            status_code=400,
            detail=f"None of the root paths exist: {root_paths}"
        )
    
    # Discover projects
    candidates = discover_projects(
        root_paths=valid_roots,
        max_depth=max_depth,
        min_confidence=min_confidence,
    )
    
    return {
        "root_paths": valid_roots,
        "candidates": [
            {
                "name": c.name,
                "root_path": c.root_path,
                "rfi_folder": c.rfi_folder,
                "specs_folder": c.specs_folder,
                "confidence": c.confidence,
                "file_count": c.file_count,
                "rfi_count": c.rfi_count,
                "spec_count": c.spec_count,
                "reasons": c.reasons,
            }
            for c in candidates
        ],
        "total": len(candidates),
    }


@router.get("/{project_id}/browse")
def browse_project_folder(
    project_id: int,
    folder_type: str = "rfi",
    recursive: bool = False,
    db: Session = Depends(get_db)
):
    """
    Browse files in a project folder WITHOUT parsing content.
    This is a fast, lightweight listing directly from the filesystem.
    
    Args:
        project_id: The project ID
        folder_type: 'rfi', 'submittal', or 'spec'
        recursive: Whether to include subdirectories
    
    Returns:
        List of files with basic metadata (no content parsing)
    """
    from typing import Literal
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Map folder type to path
    if folder_type in ("rfi", "submittal"):
        folder_path = project.rfi_folder_path
    elif folder_type == "spec":
        folder_path = project.specs_folder_path
    else:
        raise HTTPException(status_code=400, detail=f"Invalid folder_type: {folder_type}")
    
    if not folder_path or not os.path.exists(folder_path):
        return {
            "files": [],
            "folder": folder_path,
            "folder_type": folder_type,
            "total": 0,
            "error": "Folder does not exist" if folder_path else "Folder not configured"
        }
    
    # Supported file extensions for documents
    doc_extensions = {'.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls'}
    
    files = []
    try:
        if recursive:
            # Walk directory tree
            for root, dirs, filenames in os.walk(folder_path):
                for filename in filenames:
                    ext = os.path.splitext(filename)[1].lower()
                    if ext in doc_extensions:
                        file_path = os.path.join(root, filename)
                        try:
                            stat = os.stat(file_path)
                            files.append({
                                "name": filename,
                                "path": file_path,
                                "relative_path": os.path.relpath(file_path, folder_path),
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "extension": ext
                            })
                        except OSError:
                            continue
        else:
            # Single directory only
            for entry in os.scandir(folder_path):
                if entry.is_file():
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext in doc_extensions:
                        try:
                            stat = entry.stat()
                            files.append({
                                "name": entry.name,
                                "path": entry.path,
                                "relative_path": entry.name,
                                "size": stat.st_size,
                                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                                "extension": ext
                            })
                        except OSError:
                            continue
        
        # Sort by name
        files.sort(key=lambda x: x["name"].lower())
        
    except PermissionError as e:
        return {
            "files": [],
            "folder": folder_path,
            "folder_type": folder_type,
            "total": 0,
            "error": f"Permission denied: {str(e)}"
        }
    
    return {
        "files": files,
        "folder": folder_path,
        "folder_type": folder_type,
        "total": len(files)
    }


@router.get("/{project_id}", response_model=ProjectWithStats)
def get_project(project_id: int, db: Session = Depends(get_db)):
    """Get a project by ID with stats"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    files = db.query(ProjectFile).filter(ProjectFile.project_id == project.id).all()
    results_count = db.query(ProcessingResult).filter(ProcessingResult.project_id == project.id).count()

    return ProjectWithStats(
        **ProjectSchema.model_validate(project).model_dump(),
        total_files=len(files),
        rfi_count=sum(1 for f in files if f.content_type == 'rfi'),
        submittal_count=sum(1 for f in files if f.content_type == 'submittal'),
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
    if update.exclude_folders is not None:
        project.exclude_folders = update.exclude_folders

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


@router.get("/{project_id}/scan-stream")
def scan_project_stream(project_id: int, parse_content: bool = True, db: Session = Depends(get_db)):
    """Scan project folders with SSE progress updates"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Eagerly load all data needed before the generator starts
    # (since the session will be closed when the generator runs)
    rfi_folder_path = project.rfi_folder_path
    specs_folder_path = project.specs_folder_path
    
    # Load existing files with their data
    existing_files_data = {
        f.file_path: {
            'id': f.id,
            'modified_date': f.modified_date
        }
        for f in project.files
    }

    def generate_events() -> Generator[str, None, None]:
        # Import here to get a fresh session for the generator
        from ..database import SessionLocal
        
        gen_db = SessionLocal()
        files_found = 0
        files_added = 0
        files_updated = 0
        files_removed = 0

        try:
            found_paths = set()

            # Send start event
            start_event = ScanProgressEvent(
                event_type='start',
                message='Starting folder scan...'
            )
            yield f"data: {start_event.model_dump_json()}\n\n"

            # Scan RFI folder - first just discover files
            yield f"data: {ScanProgressEvent(event_type='scanning', phase='rfi', message='Scanning RFI folder...').model_dump_json()}\n\n"
            rfi_files = file_scanner.scan_folder(rfi_folder_path)

            # Scan specs folder - discover files
            yield f"data: {ScanProgressEvent(event_type='scanning', phase='specs', message='Scanning specs folder...').model_dump_json()}\n\n"
            spec_files = file_scanner.scan_folder(specs_folder_path)

            # Combine all files to process
            all_files = [(f, 'rfi') for f in rfi_files] + [(f, 'specs') for f in spec_files]
            total_files = len(all_files)

            yield f"data: {ScanProgressEvent(event_type='scanning', total_files=total_files, message=f'Found {total_files} files to process').model_dump_json()}\n\n"

            # Process each file with progress updates
            for idx, (scanned, folder_type) in enumerate(all_files):
                files_found += 1
                found_paths.add(scanned.file_path)
                content_type = file_scanner.classify_content_type(scanned.file_path, folder_type)

                # Send progress event
                progress_event = ScanProgressEvent(
                    event_type='parsing',
                    current_file=scanned.filename,
                    current_file_index=idx + 1,
                    total_files=total_files,
                    phase=folder_type,
                    message=f'Processing {scanned.filename}'
                )
                yield f"data: {progress_event.model_dump_json()}\n\n"

                if scanned.file_path in existing_files_data:
                    # Update if modified
                    existing_data = existing_files_data[scanned.file_path]
                    if existing_data['modified_date'] < scanned.modified_date:
                        existing_file = gen_db.query(ProjectFile).filter(
                            ProjectFile.id == existing_data['id']
                        ).first()
                        if existing_file:
                            _update_file(existing_file, scanned, content_type, parse_content, gen_db)
                            files_updated += 1
                else:
                    # Add new file
                    _add_file(project_id, scanned, content_type, parse_content, gen_db)
                    files_added += 1

            # Remove files that no longer exist
            for path, existing_data in existing_files_data.items():
                if path not in found_paths:
                    existing_file = gen_db.query(ProjectFile).filter(
                        ProjectFile.id == existing_data['id']
                    ).first()
                    if existing_file:
                        gen_db.delete(existing_file)
                        files_removed += 1

            # Update last scanned
            gen_project = gen_db.query(Project).filter(Project.id == project_id).first()
            if gen_project:
                gen_project.last_scanned = datetime.utcnow()
            gen_db.commit()

            # Send complete event
            result = ScanResult(
                project_id=project_id,
                files_found=files_found,
                files_added=files_added,
                files_updated=files_updated,
                files_removed=files_removed
            )
            complete_event = ScanProgressEvent(
                event_type='complete',
                current_file_index=total_files,
                total_files=total_files,
                message='Scan complete!',
                result=result
            )
            yield f"data: {complete_event.model_dump_json()}\n\n"

        except Exception as e:
            error_event = ScanProgressEvent(
                event_type='error',
                error=str(e),
                message=f'Scan failed: {str(e)}'
            )
            yield f"data: {error_event.model_dump_json()}\n\n"
            gen_db.rollback()
        finally:
            gen_db.close()

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
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
            has_content=bool(f.content_text),
            kb_indexed=f.kb_indexed
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
