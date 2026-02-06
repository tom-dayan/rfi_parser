"""
OLI-specific tools for Claude Desktop integration.

Provides tools to:
- Access project data and RFI/Submittal analysis
- Search the indexed knowledge base
- Get context for drafting responses
"""

import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
import json

from mcp.types import TextContent

# Add backend to path for imports
_backend_dir = Path(__file__).parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def get_oli_tools():
    """Get OLI tool definitions."""
    from mcp.types import Tool
    
    return [
        Tool(
            name="list_projects",
            description=(
                "List all projects in OLILab. "
                "Returns project names, document counts, and status."
            ),
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="get_project_info",
            description=(
                "Get detailed information about a specific project including "
                "document counts, analysis results, and knowledge base status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "integer",
                        "description": "The project ID to get information for.",
                    },
                    "project_name": {
                        "type": "string",
                        "description": (
                            "Project name to search for (alternative to project_id). "
                            "Will return the best matching project."
                        ),
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="get_rfi_context",
            description=(
                "Get full context for an RFI or Submittal to help draft a response. "
                "Returns the document content, extracted question, "
                "relevant specification references, and any existing AI analysis. "
                "Use this when helping draft or refine RFI/Submittal responses."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "file_id": {
                        "type": "integer",
                        "description": "The file ID of the RFI/Submittal.",
                    },
                    "filename": {
                        "type": "string",
                        "description": (
                            "Filename to search for (alternative to file_id). "
                            "Partial match supported."
                        ),
                    },
                    "project_id": {
                        "type": "integer",
                        "description": "Project ID to search within (optional).",
                    },
                },
                "required": [],
            },
        ),
        Tool(
            name="search_specs",
            description=(
                "Search the indexed specifications in the knowledge base. "
                "Uses semantic search to find relevant specification sections. "
                "Useful for finding requirements, standards, or details related to a topic."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Search query. Can be a question or keywords. "
                            "Examples: 'door hardware requirements', 'waterproofing membrane'"
                        ),
                    },
                    "project_id": {
                        "type": "integer",
                        "description": "Project ID to search within (required).",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 5, max: 10).",
                        "default": 5,
                    },
                },
                "required": ["query", "project_id"],
            },
        ),
        Tool(
            name="get_analysis_results",
            description=(
                "Get the AI analysis results for a project. "
                "Returns the list of analyzed RFIs/Submittals with their responses."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_id": {
                        "type": "integer",
                        "description": "Project ID to get results for.",
                    },
                    "document_type": {
                        "type": "string",
                        "enum": ["rfi", "submittal"],
                        "description": "Filter by document type (optional).",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum results to return (default: 20).",
                        "default": 20,
                    },
                },
                "required": ["project_id"],
            },
        ),
    ]


def _get_db():
    """Get a database session."""
    try:
        from app.database import SessionLocal
        return SessionLocal()
    except ImportError:
        return None


async def _list_projects(arguments: dict[str, Any]) -> list[TextContent]:
    """List all projects."""
    db = _get_db()
    if not db:
        return [TextContent(type="text", text="Error: Database not available")]
    
    try:
        from app.models import Project, ProjectFile, ProcessingResult
        
        projects = db.query(Project).all()
        
        if not projects:
            return [TextContent(type="text", text="No projects found.")]
        
        output = "OLILab Projects\n"
        output += "=" * 50 + "\n\n"
        
        for p in projects:
            files = db.query(ProjectFile).filter(ProjectFile.project_id == p.id).all()
            results_count = db.query(ProcessingResult).filter(
                ProcessingResult.project_id == p.id
            ).count()
            
            rfi_count = sum(1 for f in files if f.content_type == 'rfi')
            submittal_count = sum(1 for f in files if f.content_type == 'submittal')
            spec_count = sum(1 for f in files if f.content_type == 'specification')
            
            output += f"Project: {p.name} (ID: {p.id})\n"
            output += f"  RFIs: {rfi_count}, Submittals: {submittal_count}, Specs: {spec_count}\n"
            output += f"  Analyzed: {results_count}, KB Indexed: {'Yes' if p.kb_indexed else 'No'}\n"
            if p.last_scanned:
                output += f"  Last Scanned: {p.last_scanned.strftime('%Y-%m-%d %H:%M')}\n"
            output += "\n"
        
        return [TextContent(type="text", text=output)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    finally:
        db.close()


async def _get_project_info(arguments: dict[str, Any]) -> list[TextContent]:
    """Get detailed project information."""
    db = _get_db()
    if not db:
        return [TextContent(type="text", text="Error: Database not available")]
    
    project_id = arguments.get("project_id")
    project_name = arguments.get("project_name")
    
    if not project_id and not project_name:
        return [TextContent(type="text", text="Error: Either project_id or project_name is required")]
    
    try:
        from app.models import Project, ProjectFile, ProcessingResult
        
        if project_id:
            project = db.query(Project).filter(Project.id == project_id).first()
        else:
            # Search by name
            project = db.query(Project).filter(
                Project.name.ilike(f"%{project_name}%")
            ).first()
        
        if not project:
            return [TextContent(type="text", text="Project not found.")]
        
        files = db.query(ProjectFile).filter(ProjectFile.project_id == project.id).all()
        results = db.query(ProcessingResult).filter(
            ProcessingResult.project_id == project.id
        ).all()
        
        # Categorize files
        rfi_files = [f for f in files if f.content_type == 'rfi']
        submittal_files = [f for f in files if f.content_type == 'submittal']
        spec_files = [f for f in files if f.content_type == 'specification']
        drawing_files = [f for f in files if f.content_type == 'drawing']
        
        output = f"Project: {project.name}\n"
        output += "=" * 50 + "\n\n"
        output += f"ID: {project.id}\n"
        output += f"RFI Folder: {project.rfi_folder_path}\n"
        output += f"Specs Folder: {project.specs_folder_path}\n\n"
        
        output += "Document Summary:\n"
        output += f"  RFIs: {len(rfi_files)}\n"
        output += f"  Submittals: {len(submittal_files)}\n"
        output += f"  Specifications: {len(spec_files)}\n"
        output += f"  Drawings: {len(drawing_files)}\n\n"
        
        output += "Analysis Status:\n"
        output += f"  Documents Analyzed: {len(results)}\n"
        output += f"  Knowledge Base Indexed: {'Yes' if project.kb_indexed else 'No'}\n"
        if project.kb_document_count:
            output += f"  KB Chunks: {project.kb_document_count}\n"
        
        if project.last_scanned:
            output += f"\nLast Scanned: {project.last_scanned.strftime('%Y-%m-%d %H:%M')}\n"
        if project.kb_last_indexed:
            output += f"Last Indexed: {project.kb_last_indexed.strftime('%Y-%m-%d %H:%M')}\n"
        
        return [TextContent(type="text", text=output)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    finally:
        db.close()


async def _get_rfi_context(arguments: dict[str, Any]) -> list[TextContent]:
    """Get full context for drafting an RFI/Submittal response."""
    db = _get_db()
    if not db:
        return [TextContent(type="text", text="Error: Database not available")]
    
    file_id = arguments.get("file_id")
    filename = arguments.get("filename")
    project_id = arguments.get("project_id")
    
    if not file_id and not filename:
        return [TextContent(type="text", text="Error: Either file_id or filename is required")]
    
    try:
        from app.models import ProjectFile, ProcessingResult
        
        if file_id:
            file = db.query(ProjectFile).filter(ProjectFile.id == file_id).first()
        else:
            query = db.query(ProjectFile).filter(
                ProjectFile.filename.ilike(f"%{filename}%"),
                ProjectFile.content_type.in_(['rfi', 'submittal'])
            )
            if project_id:
                query = query.filter(ProjectFile.project_id == project_id)
            file = query.first()
        
        if not file:
            return [TextContent(type="text", text="Document not found.")]
        
        # Get any existing analysis
        result = db.query(ProcessingResult).filter(
            ProcessingResult.source_file_id == file.id
        ).first()
        
        output = f"{'RFI' if file.content_type == 'rfi' else 'Submittal'} Context\n"
        output += "=" * 60 + "\n\n"
        
        output += f"File: {file.filename}\n"
        output += f"Path: {file.file_path}\n"
        output += f"Type: {file.content_type}\n"
        output += f"ID: {file.id}\n\n"
        
        # Document content
        output += "--- DOCUMENT CONTENT ---\n\n"
        if file.content_text:
            content = file.content_text[:10000]  # Limit content length
            if len(file.content_text) > 10000:
                content += "\n\n[... truncated ...]"
            output += content
        else:
            output += "(No text content available)"
        
        output += "\n\n"
        
        # Existing analysis
        if result:
            output += "--- EXISTING ANALYSIS ---\n\n"
            output += f"Confidence: {result.confidence * 100:.0f}%\n"
            if result.consultant_type:
                output += f"Consultant: {result.consultant_type}\n"
            if result.status:
                output += f"Status: {result.status}\n"
            
            output += "\nAI Response:\n"
            output += result.response_text or "(no response)"
            
            output += "\n\nSpecification References:\n"
            if result.spec_references:
                for ref in result.spec_references[:5]:
                    output += f"  - {ref.get('source_filename', 'Unknown')}"
                    if ref.get('section'):
                        output += f" (Section: {ref['section']})"
                    output += f" [{ref.get('score', 0) * 100:.0f}% relevance]\n"
            else:
                output += "  (none)\n"
        else:
            output += "--- NO EXISTING ANALYSIS ---\n"
            output += "This document has not been analyzed yet.\n"
        
        return [TextContent(type="text", text=output)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    finally:
        db.close()


async def _search_specs(arguments: dict[str, Any]) -> list[TextContent]:
    """Search the knowledge base for specification content."""
    query = arguments.get("query")
    project_id = arguments.get("project_id")
    max_results = min(arguments.get("max_results", 5), 10)
    
    if not query:
        return [TextContent(type="text", text="Error: query is required")]
    if not project_id:
        return [TextContent(type="text", text="Error: project_id is required")]
    
    try:
        from app.services.knowledge_base import get_knowledge_base
        
        kb = get_knowledge_base(project_id)
        
        # Check if KB is initialized
        stats = kb.get_stats()
        if stats.get("document_count", 0) == 0:
            return [TextContent(
                type="text", 
                text="Knowledge base is empty. Please index specifications first."
            )]
        
        # Search
        results = kb.search_with_context(
            query=query,
            n_results=max_results,
            context_chars=1500
        )
        
        if not results:
            return [TextContent(type="text", text=f"No results found for: {query}")]
        
        output = f"Specification Search: {query}\n"
        output += "=" * 60 + "\n\n"
        output += f"Found {len(results)} relevant sections:\n\n"
        
        for i, result in enumerate(results, 1):
            output += f"--- Result {i} ---\n"
            output += f"Source: {result.get('source', 'Unknown')}\n"
            if result.get('section'):
                output += f"Section: {result['section']}\n"
            output += f"Relevance: {result.get('score', 0) * 100:.0f}%\n\n"
            output += result.get('text', '(no content)')[:2000]
            output += "\n\n"
        
        return [TextContent(type="text", text=output)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def _get_analysis_results(arguments: dict[str, Any]) -> list[TextContent]:
    """Get analysis results for a project."""
    db = _get_db()
    if not db:
        return [TextContent(type="text", text="Error: Database not available")]
    
    project_id = arguments.get("project_id")
    document_type = arguments.get("document_type")
    limit = arguments.get("limit", 20)
    
    if not project_id:
        return [TextContent(type="text", text="Error: project_id is required")]
    
    try:
        from app.models import ProcessingResult, ProjectFile
        
        query = db.query(ProcessingResult).filter(
            ProcessingResult.project_id == project_id
        )
        
        if document_type:
            query = query.filter(ProcessingResult.document_type == document_type)
        
        results = query.limit(limit).all()
        
        if not results:
            return [TextContent(type="text", text="No analysis results found.")]
        
        output = f"Analysis Results (Project ID: {project_id})\n"
        output += "=" * 60 + "\n\n"
        
        for result in results:
            file = db.query(ProjectFile).filter(
                ProjectFile.id == result.source_file_id
            ).first()
            
            output += f"Document: {file.filename if file else 'Unknown'}\n"
            output += f"Type: {result.document_type}, Confidence: {result.confidence * 100:.0f}%\n"
            if result.consultant_type:
                output += f"Consultant: {result.consultant_type}\n"
            if result.status:
                output += f"Status: {result.status}\n"
            output += f"Response Preview: {(result.response_text or '')[:200]}...\n"
            output += "-" * 40 + "\n\n"
        
        return [TextContent(type="text", text=output)]
        
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]
    finally:
        db.close()


# Handler registry
OLI_HANDLERS = {
    "list_projects": _list_projects,
    "get_project_info": _get_project_info,
    "get_rfi_context": _get_rfi_context,
    "search_specs": _search_specs,
    "get_analysis_results": _get_analysis_results,
}
