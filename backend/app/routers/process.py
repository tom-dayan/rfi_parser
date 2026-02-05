"""Processing router for RFIs and Submittals using RAG-based retrieval."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging

from ..database import get_db
from ..models import Project, ProjectFile, ProcessingResult
from ..schemas import (
    ProcessRequest, ProcessResponse,
    ProcessingResult as ProcessingResultSchema,
    ProcessingResultWithFile, ProjectFileSummary,
    KnowledgeBaseStats, IndexResult
)
from ..config import settings
from ..services.knowledge_base import get_knowledge_base, KnowledgeBase
from ..services.question_extractor import extract_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["processing"])


@router.post("/projects/{project_id}/index", response_model=IndexResult)
async def index_project_knowledge_base(
    project_id: int,
    force: bool = False,
    db: Session = Depends(get_db)
):
    """
    Index project specifications into the knowledge base.

    This builds the vector store for RAG-based retrieval.
    Only indexes specification files (not RFIs/submittals).
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Get the knowledge base for this project
    kb = get_knowledge_base(project_id)

    # Get specification files
    spec_files = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.content_type.in_(['specification', 'drawing'])
    ).all()

    if not spec_files:
        raise HTTPException(status_code=400, detail="No specification files found to index")

    files_indexed = 0
    chunks_created = 0
    errors = []

    for spec in spec_files:
        # Skip if already indexed and not forcing re-index
        if spec.kb_indexed and not force:
            chunks_created += spec.kb_chunk_count
            files_indexed += 1
            continue

        if not spec.content_text:
            errors.append(f"{spec.filename}: No text content available")
            continue

        try:
            # Index the document
            chunk_count = kb.index_document(
                content=spec.content_text,
                file_id=spec.id,
                filename=spec.filename,
                is_specification=spec.content_type == 'specification'
            )

            # Update file record
            spec.kb_indexed = True
            spec.kb_chunk_count = chunk_count
            chunks_created += chunk_count
            files_indexed += 1

        except Exception as e:
            logger.error(f"Error indexing {spec.filename}: {e}")
            errors.append(f"{spec.filename}: {str(e)}")

    # Update project knowledge base status
    project.kb_indexed = files_indexed > 0
    project.kb_last_indexed = datetime.utcnow()
    project.kb_document_count = kb.count()

    db.commit()

    return IndexResult(
        project_id=project_id,
        files_indexed=files_indexed,
        chunks_created=chunks_created,
        errors=errors
    )


@router.get("/projects/{project_id}/knowledge-base", response_model=KnowledgeBaseStats)
def get_knowledge_base_stats(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Get knowledge base statistics for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    kb = get_knowledge_base(project_id)
    stats = kb.get_stats()

    return KnowledgeBaseStats(
        project_id=project_id,
        indexed=project.kb_indexed,
        document_count=stats.get("document_count", 0),
        last_indexed=project.kb_last_indexed,
        embedding_model=stats.get("embedding_model")
    )


@router.delete("/projects/{project_id}/knowledge-base")
def clear_knowledge_base(
    project_id: int,
    db: Session = Depends(get_db)
):
    """Clear the knowledge base for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    kb = get_knowledge_base(project_id)
    kb.clear()

    # Update project and file records
    project.kb_indexed = False
    project.kb_document_count = 0

    db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id
    ).update({
        ProjectFile.kb_indexed: False,
        ProjectFile.kb_chunk_count: 0
    })

    db.commit()

    return {"message": "Knowledge base cleared successfully"}


@router.post("/projects/{project_id}/process", response_model=ProcessResponse)
async def process_documents(
    project_id: int,
    request: ProcessRequest,
    db: Session = Depends(get_db)
):
    """
    Process RFIs or Submittals against the project knowledge base.

    Uses RAG to retrieve relevant specification sections and generate responses.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Check if knowledge base is indexed
    if not project.kb_indexed:
        raise HTTPException(
            status_code=400,
            detail="Knowledge base not indexed. Please index specifications first."
        )

    # Get files to process
    query = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.content_type.in_(['rfi', 'submittal'])
    )

    if request.file_ids:
        query = query.filter(ProjectFile.id.in_(request.file_ids))

    if request.document_type:
        query = query.filter(ProjectFile.content_type == request.document_type)

    files_to_process = query.all()

    if not files_to_process:
        raise HTTPException(status_code=400, detail="No documents found to process")

    # Get knowledge base and AI service
    kb = get_knowledge_base(project_id)
    ai_service = _get_ai_service()

    results = []
    for doc_file in files_to_process:
        # Delete existing result for reprocessing
        existing = db.query(ProcessingResult).filter(
            ProcessingResult.source_file_id == doc_file.id
        ).first()
        if existing:
            db.delete(existing)

        try:
            # Get document content
            doc_content = doc_file.content_text or f"[Document: {doc_file.filename}]"
            
            # Determine document type
            doc_type = doc_file.content_type  # 'rfi' or 'submittal'
            
            # Extract the core question and keywords for better RAG retrieval
            extracted = extract_question(doc_content, doc_file.filename)
            search_queries = extracted.get_search_queries()
            
            logger.info(f"Extracted from {doc_file.filename}: "
                       f"RFI={extracted.rfi_number}, "
                       f"Keywords={extracted.keywords[:5]}, "
                       f"Queries={len(search_queries)}")
            
            # Use multi-query search for better spec retrieval
            if search_queries:
                relevant_specs = kb.search_multi_query(
                    queries=search_queries,
                    n_results_per_query=5,
                    max_total_results=8,
                    context_chars=1200,
                    min_score=0.4
                )
            else:
                # Fallback to original method if extraction fails
                relevant_specs = kb.search_with_context(
                    query=doc_content[:1000],
                    n_results=8,
                    context_chars=1200
                )
            
            # Build enhanced document content for AI with extracted info
            enhanced_content = _build_enhanced_content(doc_content, extracted)

            # Generate response using AI with RAG context
            ai_response = await ai_service.process_document(
                document_content=enhanced_content,
                document_type=doc_type,
                spec_context=relevant_specs
            )

            # Create result
            db_result = ProcessingResult(
                project_id=project_id,
                source_file_id=doc_file.id,
                document_type=doc_type,
                response_text=ai_response.response_text,
                status=ai_response.status if doc_type == 'submittal' else None,
                consultant_type=ai_response.consultant_type,
                confidence=ai_response.confidence,
                spec_references=[
                    {
                        "source_file_id": ref.get("source_file_id"),
                        "source_filename": ref.get("source"),
                        "section": ref.get("section"),
                        "text": ref.get("text"),
                        "score": ref.get("score")
                    }
                    for ref in relevant_specs[:5]  # Top 5 references
                ]
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)

            results.append(ProcessingResultSchema.model_validate(db_result))

        except Exception as e:
            logger.error(f"Error processing {doc_file.filename}: {e}")

            # Create error result
            db_result = ProcessingResult(
                project_id=project_id,
                source_file_id=doc_file.id,
                document_type=doc_file.content_type,
                response_text=f"Processing failed: {str(e)}",
                confidence=0.0
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)
            results.append(ProcessingResultSchema.model_validate(db_result))

    return ProcessResponse(
        message=f"Processed {len(results)} documents",
        results_count=len(results),
        results=results
    )


@router.get("/projects/{project_id}/results", response_model=list[ProcessingResultWithFile])
def get_project_results(
    project_id: int,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all results for a project."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(ProcessingResult).filter(ProcessingResult.project_id == project_id)

    if document_type:
        query = query.filter(ProcessingResult.document_type == document_type)

    if status:
        query = query.filter(ProcessingResult.status == status)

    results = query.all()

    # Build response with file info
    response = []
    for result in results:
        source_file = db.query(ProjectFile).filter(
            ProjectFile.id == result.source_file_id
        ).first()

        if source_file:
            response.append(ProcessingResultWithFile(
                **ProcessingResultSchema.model_validate(result).model_dump(),
                source_file=ProjectFileSummary(
                    id=source_file.id,
                    filename=source_file.filename,
                    file_type=source_file.file_type,
                    file_size=source_file.file_size,
                    content_type=source_file.content_type,
                    has_content=bool(source_file.content_text),
                    kb_indexed=source_file.kb_indexed
                )
            ))

    return response


@router.delete("/results/{result_id}")
def delete_result(result_id: int, db: Session = Depends(get_db)):
    """Delete a specific result."""
    result = db.query(ProcessingResult).filter(ProcessingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    db.delete(result)
    db.commit()
    return {"message": "Result deleted successfully"}


@router.patch("/results/{result_id}")
def update_result(
    result_id: int,
    update_data: dict,
    db: Session = Depends(get_db)
):
    """Update a result's response text or status."""
    result = db.query(ProcessingResult).filter(ProcessingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")

    # Only allow updating specific fields
    allowed_fields = {"response_text", "status"}
    for field, value in update_data.items():
        if field in allowed_fields and hasattr(result, field):
            setattr(result, field, value)

    db.commit()
    db.refresh(result)

    # Return updated result with source file
    source_file = db.query(ProjectFile).filter(ProjectFile.id == result.source_file_id).first()
    return {
        "id": result.id,
        "source_file_id": result.source_file_id,
        "document_type": result.document_type,
        "response_text": result.response_text,
        "status": result.status,
        "consultant_type": result.consultant_type,
        "confidence": result.confidence,
        "spec_references": result.spec_references,
        "processed_date": result.processed_date.isoformat() if result.processed_date else None,
        "source_file": {
            "id": source_file.id,
            "filename": source_file.filename,
            "file_path": source_file.file_path,
            "file_type": source_file.file_type,
            "file_size": source_file.file_size,
            "content_type": source_file.content_type,
        } if source_file else None
    }


def _build_enhanced_content(doc_content: str, extracted) -> str:
    """
    Build enhanced document content with extracted question highlighted.
    This helps the AI focus on the actual question rather than metadata.
    """
    parts = []
    
    # Add RFI metadata
    if extracted.rfi_number:
        parts.append(f"Document: {extracted.rfi_number}")
    if extracted.rfi_title:
        parts.append(f"Title: {extracted.rfi_title}")
    
    # Add the core question prominently
    if extracted.question and len(extracted.question) > 50:
        parts.append(f"\n## CORE QUESTION:\n{extracted.question}")
    
    # Add keywords for focus
    if extracted.keywords:
        parts.append(f"\n## KEY TERMS: {', '.join(extracted.keywords[:8])}")
    
    # Add spec section references
    if extracted.spec_sections:
        parts.append(f"\n## REFERENCED SPEC SECTIONS: {', '.join(extracted.spec_sections)}")
    
    # Add drawing references
    if extracted.drawing_references:
        parts.append(f"\n## REFERENCED DRAWINGS: {', '.join(extracted.drawing_references[:5])}")
    
    # Add truncated original content for context
    parts.append(f"\n## FULL DOCUMENT CONTENT:\n{doc_content[:3000]}")
    
    return "\n".join(parts)


def _get_ai_service():
    """Get the configured AI service."""
    if settings.ai_provider == "ollama":
        from ..services.ai.ollama import OllamaService
        return OllamaService(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model
        )
    elif settings.ai_provider == "claude":
        from ..services.ai.claude import ClaudeService
        return ClaudeService(api_key=settings.claude_api_key, model=settings.claude_model)
    elif settings.ai_provider == "gemini":
        from ..services.ai.gemini import GeminiService
        return GeminiService(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model
        )
    else:
        raise ValueError(f"Unknown AI provider: {settings.ai_provider}")
