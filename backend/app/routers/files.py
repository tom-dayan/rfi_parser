from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pathlib import Path
from typing import Optional
import os

from ..database import get_db
from ..models import ProjectFile
from ..schemas import ProjectFile as ProjectFileSchema

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/browse")
def browse_directory(path: Optional[str] = Query(default=None)):
    """
    Browse directories on the server for folder picker.
    Returns list of subdirectories at the given path.
    """
    # Default to user's home directory
    if not path:
        path = str(Path.home())
    
    try:
        target_path = Path(path).resolve()
        
        # Ensure path exists and is a directory
        if not target_path.exists():
            raise HTTPException(status_code=404, detail="Path does not exist")
        if not target_path.is_dir():
            raise HTTPException(status_code=400, detail="Path is not a directory")
        
        # Get parent directory
        parent = str(target_path.parent) if target_path.parent != target_path else None
        
        # List directories only (not files)
        directories = []
        try:
            for item in sorted(target_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    try:
                        # Check if we can read the directory
                        list(item.iterdir())
                        directories.append({
                            "name": item.name,
                            "path": str(item),
                            "has_children": any(
                                child.is_dir() and not child.name.startswith('.')
                                for child in item.iterdir()
                            ) if os.access(item, os.R_OK) else False
                        })
                    except PermissionError:
                        directories.append({
                            "name": item.name,
                            "path": str(item),
                            "has_children": False,
                            "access_denied": True
                        })
        except PermissionError:
            raise HTTPException(status_code=403, detail="Cannot read directory")
        
        return {
            "current_path": str(target_path),
            "parent_path": parent,
            "directories": directories
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{file_id}", response_model=ProjectFileSchema)
def get_file(file_id: int, db: Session = Depends(get_db)):
    """Get file details by ID"""
    db_file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")
    return db_file


@router.get("/{file_id}/content")
def get_file_content(file_id: int, db: Session = Depends(get_db)):
    """Get parsed content of a file"""
    db_file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    return {
        "id": db_file.id,
        "filename": db_file.filename,
        "content_type": db_file.content_type,
        "content_text": db_file.content_text,
        "metadata": db_file.file_metadata
    }


@router.get("/{file_id}/download")
def download_file(file_id: int, db: Session = Depends(get_db)):
    """Download the original file"""
    db_file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(db_file.file_path):
        raise HTTPException(status_code=404, detail="File no longer exists on disk")

    return FileResponse(
        db_file.file_path,
        filename=db_file.filename,
        media_type="application/octet-stream"
    )


@router.post("/{file_id}/reparse")
def reparse_file(file_id: int, db: Session = Depends(get_db)):
    """Re-parse a file's content"""
    from ..services.parsers import get_parser_registry
    from datetime import datetime

    db_file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
    if not db_file:
        raise HTTPException(status_code=404, detail="File not found")

    if not os.path.exists(db_file.file_path):
        raise HTTPException(status_code=404, detail="File no longer exists on disk")

    parser_registry = get_parser_registry()
    result = parser_registry.parse(db_file.file_path)

    if result.success:
        db_file.content_text = result.text_content
        db_file.file_metadata = result.metadata
        db_file.last_indexed = datetime.utcnow()
        db.commit()

        return {
            "success": True,
            "message": "File re-parsed successfully",
            "content_length": len(result.text_content) if result.text_content else 0
        }
    else:
        return {
            "success": False,
            "message": f"Failed to parse: {result.error}"
        }
