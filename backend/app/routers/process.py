"""Processing router for RFIs and Submittals using RAG-based retrieval."""
import os
import json
import logging
from datetime import datetime
from typing import Optional, Generator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

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


@router.post("/projects/{project_id}/process-stream")
async def process_documents_stream(
    project_id: int,
    document_type: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Process RFIs or Submittals with SSE streaming progress updates.
    Provides real-time feedback as each document is processed.
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

    if document_type:
        query = query.filter(ProjectFile.content_type == document_type)

    files_to_process = query.all()
    total_files = len(files_to_process)

    if total_files == 0:
        raise HTTPException(status_code=400, detail="No documents found to process")

    # Pre-load file data for the generator
    file_data = [
        {
            "id": f.id,
            "filename": f.filename,
            "content_type": f.content_type,
            "content_text": f.content_text
        }
        for f in files_to_process
    ]

    def generate_events() -> Generator[str, None, None]:
        from ..database import SessionLocal
        
        gen_db = SessionLocal()
        kb = get_knowledge_base(project_id)
        ai_service = _get_ai_service()
        
        processed = 0
        errors = []
        
        try:
            # Send start event
            start_msg = f'Starting to process {total_files} documents...'
            yield f"data: {json.dumps({'event_type': 'start', 'total_files': total_files, 'message': start_msg})}\n\n"
            
            for idx, file_info in enumerate(file_data):
                # Send progress event
                filename = file_info['filename']
                progress_msg = f'Analyzing {filename}...'
                yield f"data: {json.dumps({'event_type': 'processing', 'current_file': filename, 'current_file_index': idx + 1, 'total_files': total_files, 'message': progress_msg})}\n\n"
                
                try:
                    # Delete existing result
                    gen_db.query(ProcessingResult).filter(
                        ProcessingResult.source_file_id == file_info['id']
                    ).delete()
                    gen_db.commit()
                    
                    # Get document content
                    doc_content = file_info['content_text'] or f"[Document: {file_info['filename']}]"
                    doc_type = file_info['content_type']
                    
                    # Extract question and keywords
                    extracted = extract_question(doc_content, file_info['filename'])
                    search_queries = extracted.get_search_queries()
                    
                    # Search for relevant specs
                    if search_queries:
                        relevant_specs = kb.search_multi_query(
                            queries=search_queries,
                            n_results_per_query=5,
                            max_total_results=8,
                            context_chars=1200,
                            min_score=0.4
                        )
                    else:
                        relevant_specs = kb.search_with_context(
                            query=doc_content[:1000],
                            n_results=8,
                            context_chars=1200
                        )
                    
                    # Build enhanced content
                    enhanced_content = _build_enhanced_content(doc_content, extracted)
                    
                    # Generate AI response (this is async but we're in a generator)
                    import asyncio
                    loop = asyncio.new_event_loop()
                    ai_response = loop.run_until_complete(
                        ai_service.process_document(
                            document_content=enhanced_content,
                            document_type=doc_type,
                            spec_context=relevant_specs
                        )
                    )
                    loop.close()
                    
                    # Create result
                    db_result = ProcessingResult(
                        project_id=project_id,
                        source_file_id=file_info['id'],
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
                            for ref in relevant_specs[:5]
                        ]
                    )
                    gen_db.add(db_result)
                    gen_db.commit()
                    
                    processed += 1
                    
                    # Send success event for this file
                    complete_msg = f'Completed {filename}'
                    yield f"data: {json.dumps({'event_type': 'file_complete', 'filename': filename, 'current_file_index': idx + 1, 'total_files': total_files, 'success': True, 'message': complete_msg})}\n\n"
                    
                except Exception as e:
                    logger.error(f"Error processing {filename}: {e}")
                    errors.append(f"{filename}: {str(e)}")
                    
                    # Create error result
                    db_result = ProcessingResult(
                        project_id=project_id,
                        source_file_id=file_info['id'],
                        document_type=file_info['content_type'],
                        response_text=f"Processing failed: {str(e)}",
                        confidence=0.0
                    )
                    gen_db.add(db_result)
                    gen_db.commit()
                    
                    error_msg = f'Failed: {filename}'
                    error_str = str(e)
                    yield f"data: {json.dumps({'event_type': 'file_complete', 'filename': filename, 'current_file_index': idx + 1, 'total_files': total_files, 'success': False, 'error': error_str, 'message': error_msg})}\n\n"
            
            # Send complete event
            final_msg = f'Completed! Processed {processed} of {total_files} documents.'
            yield f"data: {json.dumps({'event_type': 'complete', 'processed': processed, 'errors': len(errors), 'total_files': total_files, 'message': final_msg})}\n\n"
            
        except Exception as e:
            error_msg = f'Processing failed: {str(e)}'
            yield f"data: {json.dumps({'event_type': 'error', 'error': str(e), 'message': error_msg})}\n\n"
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


@router.get("/projects/{project_id}/results")
def get_project_results(
    project_id: int,
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all results for a project (both file-based and path-based)."""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    query = db.query(ProcessingResult).filter(ProcessingResult.project_id == project_id)

    if document_type:
        query = query.filter(ProcessingResult.document_type == document_type)

    if status:
        query = query.filter(ProcessingResult.status == status)

    results = query.order_by(ProcessingResult.processed_date.desc()).all()

    # Build response with file info
    response = []
    for result in results:
        result_data = ProcessingResultSchema.model_validate(result).model_dump()
        
        if result.source_file_id:
            # Traditional result with a database file record
            source_file = db.query(ProjectFile).filter(
                ProjectFile.id == result.source_file_id
            ).first()

            if source_file:
                response.append({
                    **result_data,
                    "source_file": {
                        "id": source_file.id,
                        "filename": source_file.filename,
                        "file_type": source_file.file_type,
                        "file_size": source_file.file_size,
                        "content_type": source_file.content_type,
                        "has_content": bool(source_file.content_text),
                        "kb_indexed": source_file.kb_indexed,
                    }
                })
        else:
            # Path-based result (from Smart Analysis) - no database file record
            # Determine file extension from filename
            import os
            filename = result.source_filename or "Unknown"
            ext = os.path.splitext(filename)[1].lower().lstrip('.')
            doc_type = result.document_type or "rfi"
            
            response.append({
                **result_data,
                "source_filename": result.source_filename,
                "source_file_path": result.source_file_path,
                "source_file": {
                    "id": 0,  # Placeholder for path-based results
                    "filename": filename,
                    "file_type": ext or "pdf",
                    "file_size": 0,
                    "content_type": doc_type,
                    "has_content": False,
                    "kb_indexed": False,
                }
            })

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


@router.post("/results/{result_id}/refine")
async def refine_result(
    result_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Re-analyze an existing result with updated spec selections.
    
    Parses the original RFI and the newly-selected specs on-demand,
    regenerates the AI response, and updates the existing result record.
    
    Expected request body:
    {
        "spec_file_paths": ["/path/to/spec1.pdf", "/path/to/spec2.pdf"],
        "instructions": "Optional user instructions for the AI"
    }
    """
    import os
    
    result = db.query(ProcessingResult).filter(ProcessingResult.id == result_id).first()
    if not result:
        raise HTTPException(status_code=404, detail="Result not found")
    
    spec_paths = request.get("spec_file_paths", [])
    user_instructions = request.get("instructions", "").strip()
    if not spec_paths:
        raise HTTPException(status_code=400, detail="No specification files provided")
    
    # Determine the RFI file path
    rfi_path = result.source_file_path
    rfi_name = result.source_filename or "Unknown"
    
    # If path-based result doesn't have source_file_path, try getting it from the linked file
    if not rfi_path and result.source_file_id:
        source_file = db.query(ProjectFile).filter(ProjectFile.id == result.source_file_id).first()
        if source_file:
            rfi_path = source_file.file_path
            rfi_name = source_file.filename
    
    if not rfi_path or not os.path.exists(rfi_path):
        raise HTTPException(
            status_code=400, 
            detail=f"Source RFI file not found at path: {rfi_path}"
        )
    
    # Get AI service
    ai_service = _get_ai_service()
    if not ai_service:
        raise HTTPException(status_code=500, detail="AI service not configured")
    
    # Get parser registry for on-demand parsing
    from ..services.parsers import get_parser_registry
    parser_registry = get_parser_registry()
    
    # Parse the RFI file on-demand
    try:
        rfi_result_parsed = parser_registry.parse(rfi_path)
        rfi_content = rfi_result_parsed.text_content or ""
        if not rfi_result_parsed.success:
            rfi_content = f"Error parsing RFI: {rfi_result_parsed.error}"
            logger.warning(f"Refine: RFI parse failed for {rfi_name}: {rfi_result_parsed.error}")
        elif not rfi_content.strip():
            rfi_content = "[No text content could be extracted from this PDF]"
            logger.warning(f"Refine: RFI parse returned empty text for {rfi_name}")
        else:
            logger.info(f"Refine: Parsed RFI {rfi_name}: {len(rfi_content)} chars extracted")
    except Exception as e:
        rfi_content = f"Error parsing RFI: {str(e)}"
        logger.error(f"Refine: RFI parse exception for {rfi_name}: {e}", exc_info=True)
    
    # Parse each selected spec file on-demand
    spec_contents = []
    for spec_path in spec_paths:
        if os.path.exists(spec_path):
            try:
                spec_result_parsed = parser_registry.parse(spec_path)
                spec_text = spec_result_parsed.text_content or ""
                if not spec_result_parsed.success:
                    spec_text = f"Error parsing: {spec_result_parsed.error}"
                    logger.warning(f"Refine: Spec parse failed for {os.path.basename(spec_path)}: {spec_result_parsed.error}")
                else:
                    logger.info(f"Refine: Parsed spec {os.path.basename(spec_path)}: {len(spec_text)} chars extracted")
                spec_contents.append({
                    "path": spec_path,
                    "name": os.path.basename(spec_path),
                    "content": spec_text[:50000] if spec_text else ""
                })
            except Exception as e:
                logger.error(f"Refine: Spec parse exception for {os.path.basename(spec_path)}: {e}", exc_info=True)
                spec_contents.append({
                    "path": spec_path,
                    "name": os.path.basename(spec_path),
                    "content": f"Error parsing: {str(e)}"
                })
    
    # Build spec context
    spec_context = [
        {
            "text": s["content"][:20000],
            "source": s["name"],
            "section": s["name"],
            "score": 1.0,
        }
        for s in spec_contents
    ]
    
    # Determine document type
    doc_type = result.document_type or "rfi"
    
    try:
        # Build document content, appending user instructions if provided
        document_content = rfi_content[:30000]
        if user_instructions:
            document_content += (
                "\n\n--- ADDITIONAL INSTRUCTIONS FROM REVIEWER ---\n"
                f"{user_instructions}\n"
                "--- END OF INSTRUCTIONS ---\n"
            )
            logger.info(f"Refine: Including user instructions ({len(user_instructions)} chars)")
        
        # Generate new AI response
        doc_response = await ai_service.process_document(
            document_content=document_content,
            document_type=doc_type,
            spec_context=spec_context
        )
        
        # Update the existing result record
        result.response_text = doc_response.response_text
        result.confidence = doc_response.confidence
        result.consultant_type = doc_response.consultant_type
        if doc_type == "submittal":
            result.status = doc_response.status
        result.spec_references = [
            {"source_filename": s["name"], "text": "", "score": 1.0}
            for s in spec_contents
        ]
        
        db.commit()
        db.refresh(result)
        
        logger.info(f"Refine: Successfully regenerated response for result {result_id}")
        
        return {
            "id": result.id,
            "response_text": result.response_text,
            "confidence": result.confidence,
            "consultant_type": result.consultant_type,
            "status": result.status,
            "spec_references": result.spec_references,
            "processed_date": result.processed_date.isoformat() if result.processed_date else None,
        }
        
    except Exception as e:
        logger.error(f"Refine: AI error for result {result_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"AI analysis failed: {str(e)}")


@router.post("/projects/{project_id}/suggest-specs")
async def suggest_spec_files(
    project_id: int,
    rfi_file_ids: list[int] = Query(..., description="List of RFI file IDs to analyze"),
    db: Session = Depends(get_db)
):
    """
    AI-assisted spec discovery: Analyze RFI content and suggest relevant spec files.
    
    This is a FAST endpoint - it does NOT parse spec files.
    It uses the RFI content and filename matching to suggest relevant specs.
    
    Args:
        project_id: The project ID
        rfi_file_ids: List of RFI file IDs to analyze
    
    Returns:
        List of suggested spec files for each RFI
    """
    import os
    import re
    from collections import Counter
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Get the RFI files
    rfi_files = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.id.in_(rfi_file_ids)
    ).all()
    
    if not rfi_files:
        raise HTTPException(status_code=400, detail="No RFI files found")
    
    # Get all spec files from filesystem (fast - no parsing)
    specs_folder = project.specs_folder_path
    if not specs_folder or not os.path.exists(specs_folder):
        return {"suggestions": [], "error": "Specs folder not found"}
    
    # Collect all spec files
    spec_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    spec_files = []
    
    for root, _, files in os.walk(specs_folder):
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in spec_extensions:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, specs_folder).replace("\\", "/")
                spec_files.append({
                    "name": filename,
                    "path": full_path,
                    "relative_path": relative_path,
                    "extension": ext
                })
    
    # Analyze each RFI and suggest specs
    suggestions = []
    
    for rfi in rfi_files:
        # Extract keywords from RFI content and filename
        rfi_content = rfi.content_text or rfi.filename
        
        # Use question extractor for better keyword extraction
        extracted = extract_question(rfi_content, rfi.filename)
        
        # Combine all search terms
        search_terms = []
        if extracted.keywords:
            search_terms.extend(extracted.keywords)
        if extracted.spec_sections:
            search_terms.extend(extracted.spec_sections)
        if extracted.drawing_references:
            search_terms.extend(extracted.drawing_references)
        
        # Add extracted terms from RFI title
        if extracted.rfi_title:
            title_words = re.findall(r'\b\w{4,}\b', extracted.rfi_title.lower())
            search_terms.extend(title_words)
        
        # Score each spec file
        scored_specs = []
        for spec in spec_files:
            score = _score_spec_relevance(
                spec["name"], 
                spec["relative_path"],
                search_terms,
                extracted
            )
            if score > 0:
                scored_specs.append({
                    **spec,
                    "relevance_score": score,
                    "matched_terms": _get_matched_terms(spec["name"], search_terms)
                })
        
        # Sort by score and take top suggestions
        scored_specs.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_specs = scored_specs[:15]  # Top 15 suggestions
        
        suggestions.append({
            "rfi_id": rfi.id,
            "rfi_filename": rfi.filename,
            "rfi_title": extracted.rfi_title,
            "extracted_keywords": extracted.keywords[:10],
            "spec_references": extracted.spec_sections,
            "suggested_specs": top_specs,
            "total_specs_found": len(spec_files)
        })
    
    return {
        "suggestions": suggestions,
        "project_id": project_id,
        "specs_folder": specs_folder,
        "total_spec_files": len(spec_files)
    }


@router.post("/projects/{project_id}/suggest-specs-from-paths")
async def suggest_specs_from_file_paths(
    project_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    AI-assisted spec discovery from file paths (NO DATABASE REQUIRED).
    
    This endpoint works directly with the filesystem - no scanning needed.
    It analyzes RFI filenames to suggest relevant spec files.
    
    Expected request body:
    {
        "rfi_files": [
            {"path": "/path/to/rfi.pdf", "name": "RFI #92_Waterproofing.pdf"}
        ]
    }
    """
    import os
    import re
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    rfi_files = request.get("rfi_files", [])
    if not rfi_files:
        raise HTTPException(status_code=400, detail="No RFI files provided")
    
    # Get all spec files from filesystem (fast - no parsing)
    specs_folder = project.specs_folder_path
    if not specs_folder or not os.path.exists(specs_folder):
        return {"suggestions": [], "error": "Specs folder not configured or not found"}
    
    # Get exclude folders list and normalize them
    exclude_folders = project.exclude_folders or []
    
    # Build normalized exclusion sets
    exclude_folder_names = set()
    exclude_full_paths = set()
    for excl in exclude_folders:
        excl_clean = excl.strip()
        if not excl_clean:
            continue
        # Normalize path separators to OS native
        excl_normalized = os.path.normpath(excl_clean).lower()
        # Add the full normalized path
        exclude_full_paths.add(excl_normalized)
        # Also extract just the folder name (last component) for name-based matching
        folder_name = os.path.basename(excl_normalized)
        if folder_name:
            exclude_folder_names.add(folder_name)
    
    logger.info(f"Exclude folder names: {exclude_folder_names}")
    logger.info(f"Exclude full paths: {exclude_full_paths}")
    
    # Collect all spec files, respecting exclude_folders
    spec_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    spec_files = []
    
    for root, dirs, files in os.walk(specs_folder):
        root_normalized = os.path.normpath(root).lower()
        
        # Filter out excluded directories by name or if their full path matches
        def should_include_dir(d):
            d_lower = d.lower()
            if d_lower in exclude_folder_names:
                return False
            # Check if the full path of this dir matches any exclude path
            full_dir_path = os.path.normpath(os.path.join(root, d)).lower()
            for excl_path in exclude_full_paths:
                if full_dir_path == excl_path or full_dir_path.startswith(excl_path + os.sep):
                    return False
            return True
        
        dirs[:] = [d for d in dirs if should_include_dir(d)]
        
        # Check if current root should be skipped
        skip_this = False
        for excl_path in exclude_full_paths:
            if root_normalized == excl_path or root_normalized.startswith(excl_path + os.sep):
                skip_this = True
                break
        if skip_this:
            continue
        
        for filename in files:
            ext = os.path.splitext(filename)[1].lower()
            if ext in spec_extensions:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(full_path, specs_folder).replace("\\", "/")
                spec_files.append({
                    "name": filename,
                    "path": full_path,
                    "relative_path": relative_path,
                    "extension": ext
                })
    
    # Analyze each RFI file and suggest specs
    suggestions = []
    
    for rfi in rfi_files:
        rfi_path = rfi.get("path", "")
        rfi_name = rfi.get("name", os.path.basename(rfi_path))
        
        # Extract keywords from RFI filename (without parsing the file content)
        # This is fast because we only analyze the filename
        extracted = extract_question(rfi_name, rfi_name)
        
        # Combine all search terms
        search_terms = []
        if extracted.keywords:
            search_terms.extend(extracted.keywords)
        if extracted.spec_sections:
            search_terms.extend(extracted.spec_sections)
        if extracted.drawing_references:
            search_terms.extend(extracted.drawing_references)
        
        # Add extracted terms from RFI title
        if extracted.rfi_title:
            title_words = re.findall(r'\b\w{4,}\b', extracted.rfi_title.lower())
            search_terms.extend(title_words)
        
        # Also extract words from the filename directly
        filename_words = re.findall(r'\b\w{3,}\b', rfi_name.lower())
        # Filter out common words
        stopwords = {'the', 'and', 'for', 'with', 'from', 'pdf', 'rfi', 'submittal', 'request', 'review', 'approval'}
        filename_words = [w for w in filename_words if w not in stopwords and not w.isdigit()]
        search_terms.extend(filename_words)
        
        # Deduplicate search terms
        search_terms = list(set(search_terms))
        
        # Score each spec file
        scored_specs = []
        for spec in spec_files:
            score = _score_spec_relevance(
                spec["name"], 
                spec["relative_path"],
                search_terms,
                extracted
            )
            if score > 0:
                scored_specs.append({
                    **spec,
                    "relevance_score": score,
                    "matched_terms": _get_matched_terms(spec["name"], search_terms)
                })
        
        # Boost must-include folders: files from these folders always appear in suggestions
        # Accepts both folder names (e.g. "General") and full paths (e.g. "C:\Specs\General")
        include_folders_list = project.include_folders or []
        if include_folders_list:
            include_folder_names = set()
            include_full_paths = set()
            for inc in include_folders_list:
                inc_clean = inc.strip()
                if not inc_clean:
                    continue
                inc_normalized = os.path.normpath(inc_clean).lower()
                include_full_paths.add(inc_normalized)
                folder_name = os.path.basename(inc_normalized)
                if folder_name:
                    include_folder_names.add(folder_name)
            
            def _file_in_include(file_spec):
                """Check if a file is inside a must-include folder (by name or full path)."""
                # Check by relative path folder names
                rel_dir = os.path.dirname(file_spec["relative_path"]).replace("\\", "/").lower()
                rel_parts = set(rel_dir.split("/")) if rel_dir else set()
                if rel_parts & include_folder_names:
                    return True
                # Check by full directory path
                full_dir = os.path.normpath(os.path.dirname(file_spec["path"])).lower()
                for inc_path in include_full_paths:
                    if full_dir == inc_path or full_dir.startswith(inc_path + os.sep):
                        return True
                return False
            
            if include_folder_names or include_full_paths:
                # Boost scores for files in must-include folders
                for scored in scored_specs:
                    if _file_in_include(scored):
                        scored["relevance_score"] = max(scored["relevance_score"], 50) + 100
                
                # Also add any un-scored files from must-include folders
                scored_paths = {s["path"] for s in scored_specs}
                for spec in spec_files:
                    if spec["path"] in scored_paths:
                        continue
                    if _file_in_include(spec):
                        scored_specs.append({
                            **spec,
                            "relevance_score": 100,
                            "matched_terms": ["must-include folder"]
                        })
        
        # Sort by score and take top suggestions
        scored_specs.sort(key=lambda x: x["relevance_score"], reverse=True)
        top_specs = scored_specs[:15]  # Top 15 suggestions
        
        suggestions.append({
            "rfi_path": rfi_path,
            "rfi_filename": rfi_name,
            "rfi_title": extracted.rfi_title,
            "extracted_keywords": search_terms[:10],
            "spec_references": extracted.spec_sections,
            "suggested_specs": top_specs,
            "total_specs_found": len(spec_files)
        })
    
    # Also return ALL spec files (not just suggested) for folder tree browsing
    # Include folder structure information
    all_specs_with_folders = []
    folder_structure = {}
    
    for spec in spec_files:
        rel_path = spec["relative_path"].replace("\\", "/")
        folder = os.path.dirname(rel_path) if os.path.dirname(rel_path) else ""
        # Normalize folder separators for cross-platform consistency
        folder = folder.replace("\\", "/")
        
        # Build folder structure
        if folder:
            parts = folder.split("/")
            current = folder_structure
            for part in parts:
                if part not in current:
                    current[part] = {}
                current = current[part]
        
        all_specs_with_folders.append({
            **spec,
            "relative_path": rel_path,
            "folder": folder
        })
    
    return {
        "suggestions": suggestions,
        "project_id": project_id,
        "specs_folder": specs_folder,
        "total_spec_files": len(spec_files),
        "all_spec_files": all_specs_with_folders,
        "folder_structure": folder_structure
    }


# In-memory cache for spec folder trees (avoids re-walking large network folders)
_spec_tree_cache: dict = {}  # { project_id: { "data": ..., "timestamp": ..., "specs_folder": ... } }
_SPEC_TREE_CACHE_TTL = 300  # 5 minutes


@router.get("/projects/{project_id}/spec-folder-tree")
def get_spec_folder_tree(
    project_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get the complete folder tree structure of the specs folder.
    Returns all files organized by folder for tree navigation.
    
    Results are cached in memory for 5 minutes to avoid re-walking large folders.
    Pass ?refresh=true to force a fresh scan.
    
    NOTE: This is a sync def (not async) so FastAPI runs it in a 
    threadpool automatically, preventing event loop blocking on large folders.
    """
    import os
    import time
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    specs_folder = project.specs_folder_path
    if not specs_folder or not os.path.exists(specs_folder):
        return {"error": "Specs folder not configured or not found", "tree": {}, "files": [], "folders": []}
    
    # Check cache
    now = time.time()
    cached = _spec_tree_cache.get(project_id)
    if (
        not refresh
        and cached
        and cached["specs_folder"] == specs_folder
        and (now - cached["timestamp"]) < _SPEC_TREE_CACHE_TTL
    ):
        logger.info(f"Spec folder tree: returning cached result for project {project_id} ({cached['data']['total_files']} files)")
        return cached["data"]
    
    start_time = time.time()
    
    # Get exclude folders and normalize them
    exclude_folders = project.exclude_folders or []
    
    exclude_folder_names = set()
    exclude_full_paths = set()
    for excl in exclude_folders:
        excl_clean = excl.strip()
        if not excl_clean:
            continue
        excl_normalized = os.path.normpath(excl_clean).lower()
        exclude_full_paths.add(excl_normalized)
        folder_name = os.path.basename(excl_normalized)
        if folder_name:
            exclude_folder_names.add(folder_name)
    
    spec_extensions = {'.pdf', '.docx', '.doc', '.txt'}
    all_files = []
    folders_set = set()
    
    for root, dirs, files in os.walk(specs_folder):
        root_normalized = os.path.normpath(root).lower()
        
        # Filter out excluded directories by name or full path
        dirs[:] = [
            d for d in dirs
            if d.lower() not in exclude_folder_names
            and not any(
                os.path.normpath(os.path.join(root, d)).lower() == ep
                or os.path.normpath(os.path.join(root, d)).lower().startswith(ep + os.sep)
                for ep in exclude_full_paths
            )
        ]
        
        # Check if current root should be skipped
        skip_this = any(
            root_normalized == ep or root_normalized.startswith(ep + os.sep)
            for ep in exclude_full_paths
        )
        if skip_this:
            continue
        
        rel_root = os.path.relpath(root, specs_folder)
        if rel_root == ".":
            rel_root = ""
        else:
            # Normalize to forward slashes for cross-platform consistency
            rel_root = rel_root.replace("\\", "/")
        
        # Track folders
        if rel_root:
            folders_set.add(rel_root)
        
        # Use scandir for efficient stat access (avoids extra syscalls)
        try:
            with os.scandir(root) as entries:
                for entry in entries:
                    if not entry.is_file(follow_symlinks=False):
                        continue
                    ext = os.path.splitext(entry.name)[1].lower()
                    if ext not in spec_extensions:
                        continue
                    
                    try:
                        file_size = entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        file_size = 0
                    
                    full_path = entry.path
                    relative_path = os.path.relpath(full_path, specs_folder).replace("\\", "/")
                    
                    all_files.append({
                        "name": entry.name,
                        "path": full_path,
                        "relative_path": relative_path,
                        "folder": rel_root,
                        "extension": ext,
                        "size": file_size
                    })
        except OSError as e:
            logger.warning(f"Error scanning directory {root}: {e}")
            continue
    
    elapsed = time.time() - start_time
    logger.info(f"Spec folder tree: {len(all_files)} files, {len(folders_set)} folders in {elapsed:.2f}s")
    
    result = {
        "specs_folder": specs_folder,
        "total_files": len(all_files),
        "files": all_files,
        "folders": sorted(list(folders_set))
    }
    
    # Store in cache
    _spec_tree_cache[project_id] = {
        "data": result,
        "timestamp": time.time(),
        "specs_folder": specs_folder,
    }
    
    return result


# In-memory cache for project folder trees
_project_tree_cache: dict = {}
_PROJECT_TREE_CACHE_TTL = 300  # 5 minutes


@router.get("/projects/{project_id}/project-folder-tree")
def get_project_folder_tree(
    project_id: int,
    refresh: bool = False,
    db: Session = Depends(get_db)
):
    """
    Get the combined folder tree of both RFI and knowledge folders.
    Returns all files organized by source folder and subfolder for tree navigation.
    
    Cached in memory for 5 minutes. Pass ?refresh=true for a fresh scan.
    Sync def so FastAPI runs it in a threadpool automatically.
    """
    import os
    import time
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Check cache
    now = time.time()
    cached = _project_tree_cache.get(project_id)
    if (
        not refresh
        and cached
        and (now - cached["timestamp"]) < _PROJECT_TREE_CACHE_TTL
    ):
        return cached["data"]
    
    start_time = time.time()
    
    doc_extensions = {'.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls', '.dwg', '.dxf', '.png', '.jpg', '.jpeg'}
    
    def walk_folder(folder_path: str, label: str):
        """Walk a folder and return files with metadata."""
        files = []
        folders = set()
        
        if not folder_path or not os.path.exists(folder_path):
            return files, sorted(list(folders))
        
        for root, dirs, filenames in os.walk(folder_path):
            # Skip hidden directories
            dirs[:] = [d for d in dirs if not d.startswith('.')]
            
            rel_root = os.path.relpath(root, folder_path)
            if rel_root == ".":
                rel_root = ""
            else:
                rel_root = rel_root.replace("\\", "/")
            
            if rel_root:
                folders.add(rel_root)
            
            try:
                with os.scandir(root) as entries:
                    for entry in entries:
                        if not entry.is_file(follow_symlinks=False):
                            continue
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext not in doc_extensions:
                            continue
                        try:
                            file_size = entry.stat(follow_symlinks=False).st_size
                        except OSError:
                            file_size = 0
                        
                        relative_path = os.path.relpath(entry.path, folder_path).replace("\\", "/")
                        
                        files.append({
                            "name": entry.name,
                            "path": entry.path,
                            "relative_path": relative_path,
                            "folder": rel_root,
                            "extension": ext,
                            "size": file_size,
                            "source": label,
                        })
            except OSError:
                continue
        
        return files, sorted(list(folders))
    
    rfi_files, rfi_folders = walk_folder(project.rfi_folder_path, "RFI / Submittals")
    spec_files, spec_folders = walk_folder(project.specs_folder_path, "Project Knowledge")
    
    elapsed = time.time() - start_time
    logger.info(f"Project folder tree: {len(rfi_files)} RFI + {len(spec_files)} knowledge files in {elapsed:.2f}s")
    
    result = {
        "rfi_folder": project.rfi_folder_path,
        "specs_folder": project.specs_folder_path,
        "rfi_files": rfi_files,
        "rfi_folders": rfi_folders,
        "spec_files": spec_files,
        "spec_folders": spec_folders,
        "total_files": len(rfi_files) + len(spec_files),
    }
    
    # Store in cache
    _project_tree_cache[project_id] = {
        "data": result,
        "timestamp": time.time(),
    }
    
    return result


@router.post("/projects/{project_id}/smart-analyze-from-paths")
async def smart_analyze_from_paths(
    project_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Smart Analysis from file paths (NO DATABASE REQUIRED for RFIs).
    
    Parses RFI and spec files on-demand and generates responses.
    
    Expected request body:
    {
        "analyses": [
            {
                "rfi_path": "/path/to/rfi.pdf",
                "rfi_name": "RFI #92_Waterproofing.pdf",
                "spec_file_paths": ["/path/to/spec1.pdf"]
            }
        ]
    }
    """
    import os
    
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    analyses = request.get("analyses", [])
    if not analyses:
        raise HTTPException(status_code=400, detail="No analyses specified")
    
    # Get AI service
    ai_service = _get_ai_service()
    
    # Get parser registry for on-demand parsing
    from ..services.parsers import get_parser_registry
    parser_registry = get_parser_registry()
    
    results = []
    
    for analysis in analyses:
        rfi_path = analysis.get("rfi_path")
        rfi_name = analysis.get("rfi_name", os.path.basename(rfi_path) if rfi_path else "Unknown")
        spec_paths = analysis.get("spec_file_paths", [])
        
        if not rfi_path or not os.path.exists(rfi_path):
            results.append({
                "rfi_path": rfi_path,
                "rfi_name": rfi_name,
                "error": "RFI file not found",
                "response": None
            })
            continue
        
        # Parse the RFI file on-demand
        try:
            rfi_result = parser_registry.parse(rfi_path)
            rfi_content = rfi_result.text_content or ""
            if not rfi_result.success:
                rfi_content = f"Error parsing RFI: {rfi_result.error}"
                logger.warning(f"RFI parse failed for {rfi_name}: {rfi_result.error}")
            elif not rfi_content.strip():
                rfi_content = "[No text content could be extracted from this PDF]"
                logger.warning(f"RFI parse returned empty text for {rfi_name}")
            else:
                logger.info(f"Parsed RFI {rfi_name}: {len(rfi_content)} chars extracted")
        except Exception as e:
            rfi_content = f"Error parsing RFI: {str(e)}"
            logger.error(f"RFI parse exception for {rfi_name}: {e}", exc_info=True)
        
        # Parse each selected spec file on-demand
        spec_contents = []
        for spec_path in spec_paths:
            if os.path.exists(spec_path):
                try:
                    spec_result = parser_registry.parse(spec_path)
                    spec_text = spec_result.text_content or ""
                    if not spec_result.success:
                        spec_text = f"Error parsing: {spec_result.error}"
                        logger.warning(f"Spec parse failed for {os.path.basename(spec_path)}: {spec_result.error}")
                    else:
                        logger.info(f"Parsed spec {os.path.basename(spec_path)}: {len(spec_text)} chars extracted")
                    spec_contents.append({
                        "path": spec_path,
                        "name": os.path.basename(spec_path),
                        "content": spec_text[:50000] if spec_text else ""  # Limit content size
                    })
                except Exception as e:
                    logger.error(f"Spec parse exception for {os.path.basename(spec_path)}: {e}", exc_info=True)
                    spec_contents.append({
                        "path": spec_path,
                        "name": os.path.basename(spec_path),
                        "content": f"Error parsing: {str(e)}"
                    })
        
        # Generate response using AI
        if ai_service:
            try:
                # Determine document type from filename
                name_lower = rfi_name.lower()
                doc_type = "submittal" if "submittal" in name_lower else "rfi"
                
                # Build spec context in the format the AI service expects
                spec_context = [
                    {
                        "text": s["content"][:20000],
                        "source": s["name"],
                        "section": s["name"],
                        "score": 1.0,
                    }
                    for s in spec_contents
                ]
                
                # Use the proper process_document method (async)
                doc_response = await ai_service.process_document(
                    document_content=rfi_content[:30000],
                    document_type=doc_type,
                    spec_context=spec_context
                )
                
                response_text = doc_response.response_text
                confidence = doc_response.confidence
                consultant_type = doc_response.consultant_type
                status = doc_response.status if doc_type == "submittal" else None
                
                # Store the result in the database
                result_record = ProcessingResult(
                    project_id=project_id,
                    source_file_id=None,  # No database file record (path-based)
                    source_filename=rfi_name,
                    source_file_path=rfi_path,
                    document_type=doc_type,
                    response_text=response_text,
                    status=status,
                    consultant_type=consultant_type,
                    confidence=confidence,
                    spec_references=[
                        {"source_filename": s["name"], "text": "", "score": 1.0}
                        for s in spec_contents
                    ],
                )
                db.add(result_record)
                db.commit()
                
                results.append({
                    "rfi_path": rfi_path,
                    "rfi_name": rfi_name,
                    "response": response_text,
                    "specs_used": [s["name"] for s in spec_contents],
                    "result_id": result_record.id
                })
            except Exception as e:
                logger.error(f"Smart Analysis error for {rfi_name}: {e}", exc_info=True)
                results.append({
                    "rfi_path": rfi_path,
                    "rfi_name": rfi_name,
                    "error": str(e),
                    "response": None
                })
        else:
            results.append({
                "rfi_path": rfi_path,
                "rfi_name": rfi_name,
                "error": "AI service not configured",
                "response": None
            })
    
    return {"results": results, "project_id": project_id}


@router.post("/projects/{project_id}/smart-analyze")
async def smart_analyze_documents(
    project_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Smart Analysis: Analyze RFIs using user-selected spec files (on-demand parsing).
    
    This parses ONLY the spec files the user selected, then generates responses.
    
    Expected request body:
    {
        "analyses": [
            {
                "rfi_file_id": 123,
                "spec_file_paths": ["/path/to/spec1.pdf", "/path/to/spec2.pdf"]
            }
        ]
    }
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    analyses = request.get("analyses", [])
    if not analyses:
        raise HTTPException(status_code=400, detail="No analyses specified")
    
    # Get AI service
    ai_service = _get_ai_service()
    
    # Get parser registry for on-demand parsing
    from ..services.parsers import get_parser_registry
    parser_registry = get_parser_registry()
    
    results = []
    
    for analysis in analyses:
        rfi_file_id = analysis.get("rfi_file_id")
        spec_paths = analysis.get("spec_file_paths", [])
        
        # Get the RFI file
        rfi_file = db.query(ProjectFile).filter(
            ProjectFile.project_id == project_id,
            ProjectFile.id == rfi_file_id
        ).first()
        
        if not rfi_file:
            results.append({
                "rfi_file_id": rfi_file_id,
                "success": False,
                "error": "RFI file not found"
            })
            continue
        
        # Parse the selected spec files ON-DEMAND
        parsed_specs = []
        for spec_path in spec_paths[:10]:  # Limit to 10 spec files
            if not os.path.exists(spec_path):
                continue
            
            try:
                parse_result = parser_registry.parse(spec_path)
                if parse_result.success and parse_result.text_content:
                    # Truncate content for context
                    content = parse_result.text_content[:4000]
                    parsed_specs.append({
                        "source": os.path.basename(spec_path),
                        "path": spec_path,
                        "text": content,
                        "score": 1.0  # User-selected so high relevance
                    })
            except Exception as e:
                logger.warning(f"Failed to parse spec {spec_path}: {e}")
                continue
        
        if not parsed_specs:
            results.append({
                "rfi_file_id": rfi_file_id,
                "rfi_filename": rfi_file.filename,
                "success": False,
                "error": "No spec files could be parsed"
            })
            continue
        
        try:
            # Get RFI content
            rfi_content = rfi_file.content_text or f"[Document: {rfi_file.filename}]"
            doc_type = rfi_file.content_type or "rfi"
            
            # Extract question info
            extracted = extract_question(rfi_content, rfi_file.filename)
            enhanced_content = _build_enhanced_content(rfi_content, extracted)
            
            # Generate response using AI
            ai_response = await ai_service.process_document(
                document_content=enhanced_content,
                document_type=doc_type,
                spec_context=parsed_specs
            )
            
            # Delete existing result if any
            db.query(ProcessingResult).filter(
                ProcessingResult.source_file_id == rfi_file_id
            ).delete()
            
            # Create new result
            db_result = ProcessingResult(
                project_id=project_id,
                source_file_id=rfi_file.id,
                document_type=doc_type,
                response_text=ai_response.response_text,
                status=ai_response.status if doc_type == 'submittal' else None,
                consultant_type=ai_response.consultant_type,
                confidence=ai_response.confidence,
                spec_references=[
                    {
                        "source_filename": spec["source"],
                        "text": spec["text"][:500],  # First 500 chars as preview
                        "score": spec["score"]
                    }
                    for spec in parsed_specs[:5]
                ]
            )
            db.add(db_result)
            db.commit()
            db.refresh(db_result)
            
            results.append({
                "rfi_file_id": rfi_file_id,
                "rfi_filename": rfi_file.filename,
                "success": True,
                "result_id": db_result.id,
                "response_preview": ai_response.response_text[:200] + "..." if len(ai_response.response_text) > 200 else ai_response.response_text,
                "confidence": ai_response.confidence,
                "specs_used": [os.path.basename(p) for p in spec_paths if os.path.exists(p)]
            })
            
        except Exception as e:
            logger.error(f"Error in smart analysis for {rfi_file.filename}: {e}")
            results.append({
                "rfi_file_id": rfi_file_id,
                "rfi_filename": rfi_file.filename,
                "success": False,
                "error": str(e)
            })
    
    return {
        "project_id": project_id,
        "results": results,
        "total_processed": len(results),
        "successful": sum(1 for r in results if r.get("success"))
    }


@router.post("/projects/{project_id}/smart-analyze-stream")
async def smart_analyze_stream(
    project_id: int,
    request: dict,
    db: Session = Depends(get_db)
):
    """
    Smart Analysis with SSE streaming for progress updates.
    Shows real-time progress as specs are parsed and analyzed.
    """
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    
    analyses = request.get("analyses", [])
    if not analyses:
        raise HTTPException(status_code=400, detail="No analyses specified")
    
    # Pre-load RFI data
    rfi_ids = [a.get("rfi_file_id") for a in analyses]
    rfi_files = db.query(ProjectFile).filter(
        ProjectFile.project_id == project_id,
        ProjectFile.id.in_(rfi_ids)
    ).all()
    rfi_map = {f.id: f for f in rfi_files}
    
    def generate_events() -> Generator[str, None, None]:
        import asyncio
        from ..database import SessionLocal
        from ..services.parsers import get_parser_registry
        
        gen_db = SessionLocal()
        parser_registry = get_parser_registry()
        ai_service = _get_ai_service()
        
        total_analyses = len(analyses)
        completed = 0
        
        try:
            # Start event
            start_msg = f'Starting smart analysis for {total_analyses} document(s)...'
            yield f"data: {json.dumps({'event_type': 'start', 'total': total_analyses, 'message': start_msg})}\n\n"
            
            for idx, analysis in enumerate(analyses):
                rfi_file_id = analysis.get("rfi_file_id")
                spec_paths = analysis.get("spec_file_paths", [])
                
                rfi = rfi_map.get(rfi_file_id)
                if not rfi:
                    error_msg = f'RFI file {rfi_file_id} not found'
                    yield f"data: {json.dumps({'event_type': 'error', 'rfi_id': rfi_file_id, 'message': error_msg})}\n\n"
                    continue
                
                # Progress: parsing specs
                parse_msg = f'Parsing {len(spec_paths)} spec file(s) for {rfi.filename}...'
                yield f"data: {json.dumps({'event_type': 'parsing', 'rfi_id': rfi_file_id, 'rfi_filename': rfi.filename, 'spec_count': len(spec_paths), 'current_index': idx + 1, 'total': total_analyses, 'message': parse_msg})}\n\n"
                
                # Parse specs
                parsed_specs = []
                for spec_idx, spec_path in enumerate(spec_paths[:10]):
                    if not os.path.exists(spec_path):
                        continue
                    
                    spec_name = os.path.basename(spec_path)
                    spec_parse_msg = f'Parsing: {spec_name} ({spec_idx + 1}/{len(spec_paths)})'
                    yield f"data: {json.dumps({'event_type': 'parsing_spec', 'spec_name': spec_name, 'spec_index': spec_idx + 1, 'spec_total': len(spec_paths), 'message': spec_parse_msg})}\n\n"
                    
                    try:
                        parse_result = parser_registry.parse(spec_path)
                        if parse_result.success and parse_result.text_content:
                            parsed_specs.append({
                                "source": spec_name,
                                "path": spec_path,
                                "text": parse_result.text_content[:4000],
                                "score": 1.0
                            })
                    except Exception as e:
                        logger.warning(f"Failed to parse spec {spec_path}: {e}")
                
                if not parsed_specs:
                    no_specs_msg = f'No spec files could be parsed for {rfi.filename}'
                    yield f"data: {json.dumps({'event_type': 'warning', 'rfi_id': rfi_file_id, 'message': no_specs_msg})}\n\n"
                    continue
                
                # Progress: generating response
                gen_msg = f'Generating response for {rfi.filename}...'
                yield f"data: {json.dumps({'event_type': 'generating', 'rfi_id': rfi_file_id, 'rfi_filename': rfi.filename, 'specs_parsed': len(parsed_specs), 'message': gen_msg})}\n\n"
                
                try:
                    # Get RFI content
                    rfi_content = rfi.content_text or f"[Document: {rfi.filename}]"
                    doc_type = rfi.content_type or "rfi"
                    
                    # Generate response
                    extracted = extract_question(rfi_content, rfi.filename)
                    enhanced_content = _build_enhanced_content(rfi_content, extracted)
                    
                    loop = asyncio.new_event_loop()
                    ai_response = loop.run_until_complete(
                        ai_service.process_document(
                            document_content=enhanced_content,
                            document_type=doc_type,
                            spec_context=parsed_specs
                        )
                    )
                    loop.close()
                    
                    # Save result
                    gen_db.query(ProcessingResult).filter(
                        ProcessingResult.source_file_id == rfi_file_id
                    ).delete()
                    
                    db_result = ProcessingResult(
                        project_id=project_id,
                        source_file_id=rfi.id,
                        document_type=doc_type,
                        response_text=ai_response.response_text,
                        status=ai_response.status if doc_type == 'submittal' else None,
                        consultant_type=ai_response.consultant_type,
                        confidence=ai_response.confidence,
                        spec_references=[
                            {
                                "source_filename": spec["source"],
                                "text": spec["text"][:500],
                                "score": spec["score"]
                            }
                            for spec in parsed_specs[:5]
                        ]
                    )
                    gen_db.add(db_result)
                    gen_db.commit()
                    gen_db.refresh(db_result)
                    
                    completed += 1
                    
                    complete_msg = f'Completed analysis for {rfi.filename}'
                    yield f"data: {json.dumps({'event_type': 'completed', 'rfi_id': rfi_file_id, 'rfi_filename': rfi.filename, 'result_id': db_result.id, 'confidence': ai_response.confidence, 'current_index': idx + 1, 'total': total_analyses, 'message': complete_msg})}\n\n"
                    
                except Exception as e:
                    error_msg = f'Error analyzing {rfi.filename}: {str(e)}'
                    yield f"data: {json.dumps({'event_type': 'error', 'rfi_id': rfi_file_id, 'error': str(e), 'message': error_msg})}\n\n"
            
            # Final event
            final_msg = f'Smart analysis complete! Processed {completed} of {total_analyses} documents.'
            yield f"data: {json.dumps({'event_type': 'done', 'completed': completed, 'total': total_analyses, 'message': final_msg})}\n\n"
            
        except Exception as e:
            err_msg = f'Analysis failed: {str(e)}'
            yield f"data: {json.dumps({'event_type': 'fatal_error', 'error': str(e), 'message': err_msg})}\n\n"
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


def _score_spec_relevance(filename: str, relative_path: str, search_terms: list, extracted) -> float:
    """Score how relevant a spec file is to an RFI based on filename matching."""
    import re
    
    score = 0.0
    filename_lower = filename.lower()
    path_lower = relative_path.lower()
    
    # Check for spec section matches (e.g., "Section 08 71 00" -> look for "087100" or "08 71 00")
    if extracted.spec_sections:
        for section in extracted.spec_sections:
            # Normalize section number
            section_clean = re.sub(r'[\s\-_]', '', section.lower())
            filename_clean = re.sub(r'[\s\-_]', '', filename_lower)
            
            if section_clean in filename_clean or section_clean in path_lower.replace('\\', '/'):
                score += 5.0  # Strong match for spec section
    
    # Check for keyword matches
    for term in search_terms:
        term_lower = term.lower()
        if len(term_lower) < 3:
            continue
        
        if term_lower in filename_lower:
            score += 2.0  # Direct filename match
        elif term_lower in path_lower:
            score += 1.0  # Path match
    
    # Bonus for common spec patterns
    spec_patterns = [
        r'\d{2}\s?\d{2}\s?\d{2}',  # CSI spec numbers like "08 71 00"
        r'spec',
        r'section',
        r'div\d+',  # Division references
    ]
    
    for pattern in spec_patterns:
        if re.search(pattern, filename_lower):
            score += 0.5
    
    return score


def _get_matched_terms(filename: str, search_terms: list) -> list:
    """Return which search terms matched in the filename."""
    filename_lower = filename.lower()
    matched = []
    
    for term in search_terms:
        if term.lower() in filename_lower and term not in matched:
            matched.append(term)
    
    return matched[:5]  # Limit to 5


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
