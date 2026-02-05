"""
Search API endpoints for global document search.

Provides endpoints for searching across all indexed files
and retrieving file content.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from ..services.metadata_index import get_metadata_index
from ..services.content_cache import get_content_cache


router = APIRouter(prefix="/api/search", tags=["search"])


class SearchResult(BaseModel):
    """A search result."""
    path: str
    filename: str
    extension: Optional[str]
    file_type: Optional[str]
    size_bytes: Optional[int]
    modified_at: Optional[str]
    project_name: Optional[str]


class SearchResponse(BaseModel):
    """Search response with results and metadata."""
    query: str
    results: List[SearchResult]
    total: int
    source: str = "index"


class FileContentResponse(BaseModel):
    """File content response."""
    path: str
    filename: str
    content: str
    was_cached: bool


@router.get("", response_model=SearchResponse)
async def search_files(
    q: str = Query(..., description="Search query", min_length=1),
    file_type: Optional[str] = Query(None, description="Filter by file type (drawing, document, specification, etc.)"),
    extension: Optional[str] = Query(None, description="Filter by file extension (pdf, docx, dwg, etc.)"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    modified_after: Optional[str] = Query(None, description="Filter by modification date (YYYY-MM-DD)"),
    limit: int = Query(50, ge=1, le=100, description="Maximum results to return"),
):
    """
    Search for files by name pattern.
    
    Supports wildcards: * (any characters), ? (single character)
    
    Examples:
    - `*door*` - find files with "door" in the name
    - `RFI*.pdf` - find PDFs starting with "RFI"
    - `spec*` - find specification files
    """
    index = get_metadata_index()
    
    # Parse date if provided
    modified_after_dt = None
    if modified_after:
        try:
            modified_after_dt = datetime.strptime(modified_after, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    # Build filters
    file_types = [file_type] if file_type else None
    extensions = [extension.lstrip(".")] if extension else None
    
    # Search
    results = index.search(
        query=q,
        file_types=file_types,
        extensions=extensions,
        project_id=project_id,
        modified_after=modified_after_dt,
        limit=limit,
    )
    
    # Convert to response format
    search_results = [
        SearchResult(
            path=r["path"],
            filename=r["filename"],
            extension=r.get("extension"),
            file_type=r.get("file_type"),
            size_bytes=r.get("size_bytes"),
            modified_at=r.get("modified_at"),
            project_name=r.get("project_name"),
        )
        for r in results
    ]
    
    return SearchResponse(
        query=q,
        results=search_results,
        total=len(search_results),
        source="index",
    )


@router.get("/drawings", response_model=SearchResponse)
async def search_drawings(
    q: str = Query(..., description="Search query for drawings"),
    project_id: Optional[int] = Query(None, description="Filter by project ID"),
    limit: int = Query(50, ge=1, le=100),
):
    """
    Search specifically for drawing files (DWG, DXF, PDF drawings).
    
    Use this to find architectural details, sections, or plans.
    """
    index = get_metadata_index()
    
    results = index.search(
        query=q,
        file_types=["drawing"],
        project_id=project_id,
        limit=limit,
    )
    
    # If no results from type filter, try extension filter
    if not results:
        results = index.search(
            query=q,
            extensions=["dwg", "dxf"],
            project_id=project_id,
            limit=limit,
        )
    
    search_results = [
        SearchResult(
            path=r["path"],
            filename=r["filename"],
            extension=r.get("extension"),
            file_type=r.get("file_type"),
            size_bytes=r.get("size_bytes"),
            modified_at=r.get("modified_at"),
            project_name=r.get("project_name"),
        )
        for r in results
    ]
    
    return SearchResponse(
        query=q,
        results=search_results,
        total=len(search_results),
        source="index",
    )


@router.get("/content", response_model=FileContentResponse)
async def get_file_content(
    path: str = Query(..., description="Full path to the file"),
    max_length: int = Query(50000, ge=1000, le=200000, description="Maximum content length"),
):
    """
    Get the parsed text content of a file.
    
    Content is cached for faster subsequent access.
    """
    cache = get_content_cache()
    
    try:
        content, metadata, was_cached = cache.get_or_parse(path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error parsing file: {str(e)}")
    
    # Truncate if needed
    if len(content) > max_length:
        content = content[:max_length] + f"\n\n[... truncated at {max_length} characters ...]"
    
    # Extract filename from path
    from pathlib import Path
    filename = Path(path).name
    
    return FileContentResponse(
        path=path,
        filename=filename,
        content=content,
        was_cached=was_cached,
    )


@router.get("/stats")
async def get_search_stats():
    """Get statistics about the search index."""
    index = get_metadata_index()
    cache = get_content_cache()
    
    return {
        "index": index.get_stats(),
        "cache": cache.get_stats(),
    }


@router.post("/index")
async def trigger_indexing(
    path: str = Query(..., description="Path to index"),
    project_id: Optional[int] = Query(None, description="Associate with project"),
    project_name: Optional[str] = Query(None, description="Project name"),
):
    """
    Trigger indexing of a directory.
    
    This scans the directory and adds all files to the metadata index.
    """
    from pathlib import Path as PathLib
    
    index = get_metadata_index()
    target_path = PathLib(path)
    
    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Path not found")
    
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Path must be a directory")
    
    stats = index.scan_directory(
        root_path=target_path,
        project_id=project_id,
        project_name=project_name,
    )
    
    return {
        "status": "completed",
        "path": str(target_path),
        "stats": stats,
    }
