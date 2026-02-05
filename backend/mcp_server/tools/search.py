"""
Search tools for finding files and content.

Provides tools for searching files by name, type, and content
within the firm's shared folders.

Uses the metadata index for fast filename searches when available,
falling back to filesystem walking for direct access.
"""

import os
import re
import fnmatch
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

# Add backend to path for app imports
_backend_dir = Path(__file__).parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from mcp_server.config import get_config


# Maximum number of results to return
MAX_RESULTS = 100


def _get_metadata_index():
    """Get the metadata index, or None if not available."""
    try:
        from app.services.metadata_index import get_metadata_index
        return get_metadata_index()
    except ImportError:
        return None


def register_search_tools(server: Server) -> None:
    """Register search-related tools with the MCP server."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of search tools."""
        return [
            Tool(
                name="search_files",
                description=(
                    "Search for files by name pattern, type, or date. "
                    "Use this to find drawings, specifications, RFIs, or other documents. "
                    "Supports glob patterns (e.g., '*door*', '*.pdf')."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query. Matches against filename. "
                                "Supports wildcards: * (any chars), ? (single char). "
                                "Examples: '*door*', 'RFI*.pdf', 'spec_??_*.docx'"
                            ),
                        },
                        "path": {
                            "type": "string",
                            "description": (
                                "Folder to search in. Leave empty to search all shared roots."
                            ),
                        },
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Filter by file extensions (e.g., ['pdf', 'dwg']). "
                                "Leave empty for all file types."
                            ),
                        },
                        "modified_after": {
                            "type": "string",
                            "description": (
                                "Only include files modified after this date. "
                                "Format: YYYY-MM-DD"
                            ),
                        },
                        "modified_before": {
                            "type": "string",
                            "description": (
                                "Only include files modified before this date. "
                                "Format: YYYY-MM-DD"
                            ),
                        },
                        "max_results": {
                            "type": "integer",
                            "description": f"Maximum results to return (default: 50, max: {MAX_RESULTS})",
                            "default": 50,
                        },
                    },
                    "required": ["query"],
                },
            ),
            Tool(
                name="search_drawings",
                description=(
                    "Search specifically for drawing files (DWG, DXF, PDF drawings). "
                    "Useful for finding architectural details, sections, or plans."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": (
                                "Search query for drawing name. "
                                "Examples: 'door detail', 'section A', 'foundation plan'"
                            ),
                        },
                        "path": {
                            "type": "string",
                            "description": "Folder to search in. Leave empty to search all.",
                        },
                        "drawing_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Types of drawings to include. "
                                "Options: 'dwg', 'dxf', 'pdf'. Default: all."
                            ),
                        },
                    },
                    "required": ["query"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        if name == "search_files":
            return await _search_files(arguments)
        elif name == "search_drawings":
            return await _search_drawings(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _search_files(arguments: dict[str, Any]) -> list[TextContent]:
    """Search for files matching criteria."""
    config = get_config()

    query = arguments.get("query", "*")
    path_str = arguments.get("path", "")
    file_types = arguments.get("file_types", [])
    modified_after = _parse_date(arguments.get("modified_after"))
    modified_before = _parse_date(arguments.get("modified_before"))
    max_results = min(arguments.get("max_results", 50), MAX_RESULTS)

    # Normalize file types
    file_types_set = {ft.lstrip(".").lower() for ft in file_types} if file_types else set()

    # Try metadata index first (faster for indexed folders)
    index = _get_metadata_index()
    if index:
        try:
            indexed_results = index.search(
                query=query,
                extensions=list(file_types_set) if file_types_set else None,
                modified_after=modified_after,
                modified_before=modified_before,
                limit=max_results,
            )
            if indexed_results:
                # Filter by path if specified
                if path_str:
                    path_prefix = str(Path(path_str).resolve())
                    indexed_results = [
                        r for r in indexed_results
                        if r["path"].startswith(path_prefix)
                    ]
                
                # Convert to standard result format
                results = [
                    {
                        "path": r["path"],
                        "name": r["filename"],
                        "size": r["size_bytes"],
                        "modified": datetime.fromisoformat(r["modified_at"]) if isinstance(r["modified_at"], str) else r["modified_at"],
                        "extension": f".{r['extension']}" if r["extension"] else "",
                    }
                    for r in indexed_results
                ]
                return _format_search_results(query, results, max_results, source="index")
        except Exception:
            pass  # Fall back to filesystem walk

    # Determine search roots
    if path_str:
        search_roots = [Path(path_str).resolve()]
        if not config.is_path_allowed(search_roots[0]):
            return [TextContent(
                type="text",
                text=f"Access denied: Path is outside allowed shared folders.\nPath: {search_roots[0]}"
            )]
    else:
        search_roots = config.shared_folders_root or [Path.home()]

    # Build the search pattern
    pattern = _build_pattern(query)

    # Search for files
    results = []

    for root in search_roots:
        if not root.exists():
            continue

        for match in _walk_and_match(root, pattern, file_types_set, modified_after, modified_before, config):
            results.append(match)
            if len(results) >= max_results:
                break

        if len(results) >= max_results:
            break

    # Format results
    return _format_search_results(query, results, max_results)


async def _search_drawings(arguments: dict[str, Any]) -> list[TextContent]:
    """Search specifically for drawing files."""
    query = arguments.get("query", "*")
    path_str = arguments.get("path", "")
    drawing_types = arguments.get("drawing_types", ["dwg", "dxf", "pdf"])

    # Normalize drawing types
    drawing_types = [dt.lstrip(".").lower() for dt in drawing_types]

    # Use the general search with drawing-specific filters
    return await _search_files({
        "query": query,
        "path": path_str,
        "file_types": drawing_types,
        "max_results": 50,
    })


def _build_pattern(query: str) -> re.Pattern:
    """Build a regex pattern from a glob-like query."""
    # If query doesn't have wildcards, wrap in wildcards for partial match
    if "*" not in query and "?" not in query:
        query = f"*{query}*"

    # Convert glob to regex
    regex = fnmatch.translate(query)
    return re.compile(regex, re.IGNORECASE)


def _parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string in YYYY-MM-DD format."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def _walk_and_match(
    root: Path,
    pattern: re.Pattern,
    file_types: set[str],
    modified_after: datetime | None,
    modified_before: datetime | None,
    config,
) -> Generator[dict, None, None]:
    """Walk directory tree and yield matching files."""
    try:
        for dirpath, dirnames, filenames in os.walk(root):
            # Skip hidden directories
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]

            current_dir = Path(dirpath)

            for filename in filenames:
                # Skip hidden files
                if filename.startswith("."):
                    continue

                file_path = current_dir / filename

                # Check extension filter
                if file_types:
                    ext = file_path.suffix.lstrip(".").lower()
                    if ext not in file_types:
                        continue

                # Check allowed extensions
                if not config.is_extension_allowed(file_path):
                    continue

                # Check name pattern
                if not pattern.match(filename):
                    continue

                # Get file stats
                try:
                    stat = file_path.stat()
                except (PermissionError, OSError):
                    continue

                # Check date filters
                mtime = datetime.fromtimestamp(stat.st_mtime)
                if modified_after and mtime < modified_after:
                    continue
                if modified_before and mtime > modified_before:
                    continue

                yield {
                    "path": str(file_path),
                    "name": filename,
                    "size": stat.st_size,
                    "modified": mtime,
                    "extension": file_path.suffix.lower(),
                }

    except PermissionError:
        pass  # Skip directories we can't access


def _format_search_results(query: str, results: list[dict], max_results: int, source: str = "filesystem") -> list[TextContent]:
    """Format search results for display."""
    if not results:
        return [TextContent(
            type="text",
            text=f"No files found matching: {query}"
        )]

    output = f"Search results for: {query}\n"
    output += "=" * 60 + "\n\n"

    for i, result in enumerate(results, 1):
        size = _format_size(result["size"])
        if isinstance(result["modified"], datetime):
            modified = result["modified"].strftime("%Y-%m-%d %H:%M")
        else:
            modified = str(result["modified"])
        output += f"{i:3}. {result['name']}\n"
        output += f"     Path: {result['path']}\n"
        output += f"     Size: {size}  |  Modified: {modified}\n\n"

    if len(results) >= max_results:
        output += f"\n(Showing first {max_results} results. Refine your search for more specific results.)"
    else:
        output += f"\n{len(results)} file(s) found."
    
    if source == "index":
        output += "\n(Results from metadata index)"

    return [TextContent(type="text", text=output)]


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
