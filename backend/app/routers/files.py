from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
import os

from ..database import get_db
from ..models import ProjectFile
from ..schemas import ProjectFile as ProjectFileSchema

router = APIRouter(prefix="/api/files", tags=["files"])


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
