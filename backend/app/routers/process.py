from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from ..database import get_db
from ..models import Project, ProjectFile, RFIResult
from ..schemas import (
    ProcessRequest, ProcessResponse, RFIResult as RFIResultSchema,
    RFIResultWithFile, ProjectFileSummary
)
from ..config import settings

router = APIRouter(prefix="/api", tags=["processing"])


@router.post("/projects/{project_id}/process", response_model=ProcessResponse)
async def process_project_rfis(
    project_id: int,
    request: ProcessRequest,
    db: Session = Depends(get_db)
):
    """Process RFIs in a project against specifications"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get RFI files to process
    rfi_query = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.content_type == 'rfi'
    )
    if request.rfi_file_ids:
        rfi_query = rfi_query.filter(ProjectFile.id.in_(request.rfi_file_ids))
    rfi_files = rfi_query.all()

    if not rfi_files:
        raise HTTPException(status_code=400, detail="No RFI files found to process")

    # Get specification files
    spec_files = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.content_type.in_(['specification', 'drawing'])
    ).all()

    if not spec_files:
        raise HTTPException(status_code=400, detail="No specification files found")

    # Get AI service
    ai_service = _get_ai_service()

    results = []
    for rfi in rfi_files:
        # Check if already processed
        existing = db.query(RFIResult).filter(
            RFIResult.rfi_file_id == rfi.id
        ).first()

        if existing:
            # Delete existing result for reprocessing
            db.delete(existing)

        # Process RFI
        try:
            analysis = await ai_service.analyze_rfi(
                rfi_content=rfi.content_text or f"[{rfi.filename}]",
                specifications=_build_spec_context(spec_files)
            )

            # Create result
            db_result = RFIResult(
                project_id=project_id,
                rfi_file_id=rfi.id,
                status=analysis.status,
                consultant_type=analysis.consultant_type,
                reason=analysis.reason,
                confidence=analysis.confidence,
                spec_references=_build_spec_references(analysis, spec_files)
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)

            results.append(RFIResultSchema.model_validate(db_result))

        except Exception as e:
            # Create error result
            db_result = RFIResult(
                project_id=project_id,
                rfi_file_id=rfi.id,
                status='comment',
                reason=f"Processing failed: {str(e)}",
                confidence=0.0
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)
            results.append(RFIResultSchema.model_validate(db_result))

    return ProcessResponse(
        message=f"Processed {len(results)} RFIs",
        results_count=len(results),
        results=results
    )


@router.get("/projects/{project_id}/results", response_model=list[RFIResultWithFile])
def get_project_results(
    project_id: int,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all results for a project"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(RFIResult).filter(RFIResult.project_id == project_id)
    if status:
        query = query.filter(RFIResult.status == status)

    results = query.all()

    # Build response with file info
    response = []
    for result in results:
        rfi_file = db.query(ProjectFile).filter(ProjectFile.id == result.rfi_file_id).first()
        response.append(RFIResultWithFile(
            **RFIResultSchema.model_validate(result).model_dump(),
            rfi_file=ProjectFileSummary(
                id=rfi_file.id,
                filename=rfi_file.filename,
                file_type=rfi_file.file_type,
                file_size=rfi_file.file_size,
                content_type=rfi_file.content_type,
                has_content=bool(rfi_file.content_text)
            )
        ))

    return response


@router.delete("/results/{result_id}")
def delete_result(result_id: int, db: Session = Depends(get_db)):
    """Delete a specific result"""
    result = db.query(RFIResult).filter(RFIResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}


# Helper functions
def _get_ai_service():
    """Get the configured AI service"""
    if settings.ai_provider == "ollama":
        from ..services.ai.ollama import OllamaService
        return OllamaService(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model
        )
    elif settings.ai_provider == "claude":
        from ..services.ai.claude import ClaudeService
        return ClaudeService(api_key=settings.claude_api_key)
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")


def _build_spec_context(spec_files: list[ProjectFile]) -> list:
    """Build specification context for AI"""
    from ..services.ai.base import SpecSection

    sections = []
    for spec in spec_files:
        if spec.content_text:
            # Truncate very long content
            content = spec.content_text[:10000] if len(spec.content_text) > 10000 else spec.content_text
            sections.append(SpecSection(
                title=spec.filename,
                content=content
            ))
    return sections


def _build_spec_references(analysis, spec_files: list[ProjectFile]) -> list:
    """Build spec references from analysis"""
    references = []
    if analysis.spec_reference:
        # Try to match spec_reference to a file
        for spec in spec_files:
            if analysis.spec_reference.lower() in spec.filename.lower():
                references.append({
                    "file_id": spec.id,
                    "filename": spec.filename,
                    "section": analysis.spec_reference,
                    "quote": analysis.spec_quote
                })
                break

        # If no match found, still include the reference
        if not references:
            references.append({
                "file_id": None,
                "filename": analysis.spec_reference,
                "section": analysis.spec_reference,
                "quote": analysis.spec_quote
            })

    return references
