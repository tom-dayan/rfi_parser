from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from ..database import get_db
from ..models import RFIResult
from ..schemas import (
    ProcessingRequest,
    ProcessingResponse,
    RFIResult as RFIResultSchema
)
from ..services.rfi_processor import RFIProcessor
from ..services.ollama_service import OllamaService
from ..services.claude_service import ClaudeService
from ..config import settings

router = APIRouter(prefix="/api", tags=["processing"])


def get_ai_service():
    """Factory function to get AI service based on configuration"""
    if settings.ai_provider == "ollama":
        return OllamaService(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model
        )
    elif settings.ai_provider == "claude":
        if not settings.claude_api_key:
            raise ValueError("Claude API key not configured")
        return ClaudeService(api_key=settings.claude_api_key, model=settings.claude_model)
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")


@router.post("/process", response_model=ProcessingResponse)
async def process_rfis(
    request: ProcessingRequest,
    db: Session = Depends(get_db)
):
    """Process RFIs against specifications using AI"""

    try:
        # Get AI service
        ai_service = get_ai_service()

        # Check if Ollama is available (if using Ollama)
        if isinstance(ai_service, OllamaService):
            if not ai_service.check_availability():
                raise HTTPException(
                    status_code=503,
                    detail=f"Ollama service is not available. Please ensure Ollama is running and model '{settings.ollama_model}' is installed. Run: ollama pull {settings.ollama_model}"
                )

        # Create processor
        processor = RFIProcessor(ai_service)

        # Process RFIs
        results = await processor.process_all_rfis(
            rfi_ids=request.rfi_ids,
            spec_ids=request.spec_ids,
            db=db
        )

        # Load relationships for response
        for result in results:
            db.refresh(result)

        return ProcessingResponse(
            message=f"Successfully processed {len(results)} RFI(s)",
            results=results
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")


@router.get("/results", response_model=List[RFIResultSchema])
def get_results(db: Session = Depends(get_db)):
    """Get all RFI results"""
    results = db.query(RFIResult).all()

    # Load relationships
    for result in results:
        db.refresh(result)

    return results


@router.get("/results/rfi/{rfi_id}", response_model=List[RFIResultSchema])
def get_results_by_rfi(rfi_id: int, db: Session = Depends(get_db)):
    """Get all results for a specific RFI"""
    results = db.query(RFIResult).filter(RFIResult.rfi_id == rfi_id).all()

    if not results:
        raise HTTPException(status_code=404, detail="No results found for this RFI")

    # Load relationships
    for result in results:
        db.refresh(result)

    return results


@router.delete("/results/{result_id}")
def delete_result(result_id: int, db: Session = Depends(get_db)):
    """Delete an RFI result"""
    result = db.query(RFIResult).filter(RFIResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}
