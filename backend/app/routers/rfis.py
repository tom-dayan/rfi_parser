from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import RFI
from ..schemas import RFI as RFISchema, UploadResponse
from ..services.document_parser import DocumentParser

router = APIRouter(prefix="/api/rfis", tags=["rfis"])


@router.post("/upload", response_model=UploadResponse)
async def upload_rfi(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload and parse an RFI document"""

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

        # Extract question/request (first paragraph or first 500 chars)
        lines = [line.strip() for line in parsed_content.split('\n') if line.strip()]
        question = lines[0] if lines else parsed_content[:500]

        # Save to database
        rfi = RFI(
            filename=file.filename,
            content=parsed_content,
            question=question
        )
        db.add(rfi)
        db.commit()
        db.refresh(rfi)

        return UploadResponse(
            id=rfi.id,
            filename=rfi.filename,
            message="RFI uploaded and parsed successfully"
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")


@router.get("", response_model=List[RFISchema])
def get_rfis(db: Session = Depends(get_db)):
    """Get all RFIs"""
    rfis = db.query(RFI).all()
    return rfis


@router.get("/{rfi_id}", response_model=RFISchema)
def get_rfi(rfi_id: int, db: Session = Depends(get_db)):
    """Get a specific RFI"""
    rfi = db.query(RFI).filter(RFI.id == rfi_id).first()
    if not rfi:
        raise HTTPException(status_code=404, detail="RFI not found")
    return rfi


@router.delete("/{rfi_id}")
def delete_rfi(rfi_id: int, db: Session = Depends(get_db)):
    """Delete an RFI"""
    rfi = db.query(RFI).filter(RFI.id == rfi_id).first()
    if not rfi:
        raise HTTPException(status_code=404, detail="RFI not found")

    db.delete(rfi)
    db.commit()
    return {"message": "RFI deleted successfully"}
