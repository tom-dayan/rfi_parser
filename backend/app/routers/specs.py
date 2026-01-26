from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import Specification
from ..schemas import Specification as SpecificationSchema, UploadResponse
from ..services.document_parser import DocumentParser

router = APIRouter(prefix="/api/specifications", tags=["specifications"])


@router.post("/upload", response_model=UploadResponse)
async def upload_specification(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse a specification document"""

    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    allowed_extensions = ['.pdf', '.docx', '.doc', '.txt', '.md']
    if not any(file.filename.lower().endswith(ext) for ext in allowed_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    try:
        # Read file content
        content_bytes = await file.read()

        # Parse document
        parsed_content = DocumentParser.parse_document(content_bytes, file.filename)

        # Extract sections
        sections = DocumentParser.extract_sections(parsed_content)

        # Save to database
        spec = Specification(
            filename=file.filename,
            content=parsed_content,
            parsed_sections=sections
        )
        db.add(spec)
        db.commit()
        db.refresh(spec)

        return UploadResponse(
            id=spec.id,
            filename=spec.filename,
            message="Specification uploaded and parsed successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.get("", response_model=List[SpecificationSchema])
def get_specifications(db: Session = Depends(get_db)):
    """Get all specifications"""
    specs = db.query(Specification).all()
    return specs


@router.get("/{spec_id}", response_model=SpecificationSchema)
def get_specification(spec_id: int, db: Session = Depends(get_db)):
    """Get a specific specification"""
    spec = db.query(Specification).filter(Specification.id == spec_id).first()
    if not spec:
        raise HTTPException(status_code=404, detail="Specification not found")
    return spec


@router.delete("/{spec_id}")
def delete_specification(spec_id: int, db: Session = Depends(get_db)):
    """Delete a specification"""
    spec = db.query(Specification).filter(Specification.id == spec_id).first()
    if not spec:
        raise HTTPException(status_code=404, detail="Specification not found")

    db.delete(spec)
    db.commit()
    return {"message": "Specification deleted successfully"}
