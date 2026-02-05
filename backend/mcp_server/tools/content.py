"""
Content tools for retrieving file contents.

Provides tools for reading and parsing file contents
using the existing document parsers and content cache.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.types import Tool, TextContent

# Add backend to path for imports
_backend_dir = Path(__file__).parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from mcp_server.config import get_config


def _get_content_cache():
    """Get the content cache, or None if not available."""
    try:
        from app.services.content_cache import get_content_cache
        return get_content_cache()
    except ImportError:
        return None


def register_content_tools(server: Server) -> None:
    """Register content-related tools with the MCP server."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of content tools."""
        return [
            Tool(
                name="get_file_content",
                description=(
                    "Get the parsed text content of a file. "
                    "Supports PDF, DOCX, TXT, MD, and other text-based formats. "
                    "For drawings (DWG/DXF), returns metadata and text annotations."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full path to the file to read.",
                        },
                        "max_length": {
                            "type": "integer",
                            "description": (
                                "Maximum characters to return. "
                                "Default: 50000. Use smaller values for large files."
                            ),
                            "default": 50000,
                        },
                    },
                    "required": ["path"],
                },
            ),
            Tool(
                name="get_file_metadata",
                description=(
                    "Get metadata about a file without reading its full content. "
                    "Returns size, type, modification date, and basic info."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": "Full path to the file.",
                        },
                    },
                    "required": ["path"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        if name == "get_file_content":
            return await _get_file_content(arguments)
        elif name == "get_file_metadata":
            return await _get_file_metadata(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _get_file_content(arguments: dict[str, Any]) -> list[TextContent]:
    """Get parsed content of a file."""
    config = get_config()
    path_str = arguments.get("path", "")
    max_length = arguments.get("max_length", 50000)

    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    file_path = Path(path_str).resolve()

    # Security check
    if not config.is_path_allowed(file_path):
        return [TextContent(
            type="text",
            text=f"Access denied: Path is outside allowed shared folders.\nPath: {file_path}"
        )]

    if not file_path.exists():
        return [TextContent(type="text", text=f"File not found: {file_path}")]

    if not file_path.is_file():
        return [TextContent(type="text", text=f"Not a file: {file_path}")]

    # Check extension
    if not config.is_extension_allowed(file_path):
        return [TextContent(
            type="text",
            text=f"File type not allowed: {file_path.suffix}"
        )]

    # Check file size
    try:
        stat = file_path.stat()
        if stat.st_size > config.max_file_size:
            return [TextContent(
                type="text",
                text=(
                    f"File too large: {_format_size(stat.st_size)} "
                    f"(max: {_format_size(config.max_file_size)})"
                )
            )]
    except (PermissionError, OSError) as e:
        return [TextContent(type="text", text=f"Cannot access file: {e}")]

    # Try to get from cache or parse
    was_cached = False
    try:
        cache = _get_content_cache()
        if cache:
            content, metadata, was_cached = cache.get_or_parse(str(file_path))
        else:
            content = await _parse_file(file_path)
            metadata = {}
    except Exception as e:
        return [TextContent(type="text", text=f"Error parsing file: {e}")]

    # Truncate if needed
    if len(content) > max_length:
        content = content[:max_length] + f"\n\n[... truncated at {max_length} characters ...]"

    # Add header
    header = f"File: {file_path.name}\n"
    header += f"Path: {file_path}\n"
    header += f"Size: {_format_size(stat.st_size)}\n"
    if was_cached:
        header += "(from cache)\n"
    header += "=" * 60 + "\n\n"

    return [TextContent(type="text", text=header + content)]


async def _get_file_metadata(arguments: dict[str, Any]) -> list[TextContent]:
    """Get metadata about a file."""
    config = get_config()
    path_str = arguments.get("path", "")

    if not path_str:
        return [TextContent(type="text", text="Error: path is required")]

    file_path = Path(path_str).resolve()

    # Security check
    if not config.is_path_allowed(file_path):
        return [TextContent(
            type="text",
            text=f"Access denied: Path is outside allowed shared folders.\nPath: {file_path}"
        )]

    if not file_path.exists():
        return [TextContent(type="text", text=f"Path not found: {file_path}")]

    try:
        stat = file_path.stat()
    except (PermissionError, OSError) as e:
        return [TextContent(type="text", text=f"Cannot access path: {e}")]

    if file_path.is_file():
        info = _format_file_metadata(file_path, stat)
    else:
        info = _format_dir_metadata(file_path, stat)

    return [TextContent(type="text", text=info)]


async def _parse_file(file_path: Path) -> str:
    """Parse a file using the appropriate parser."""
    # Import parser registry lazily to avoid circular imports
    try:
        from app.services.parsers.registry import get_parser_registry
        registry = get_parser_registry()

        if registry.can_parse(str(file_path)):
            result = registry.parse(str(file_path))
            if result.success:
                return result.text or "(no text content extracted)"
            else:
                return f"(parsing failed: {result.error})"
    except ImportError:
        pass  # Fall back to basic text reading

    # Fallback: try to read as text
    ext = file_path.suffix.lower()
    if ext in {".txt", ".md", ".csv", ".json", ".xml", ".html", ".log"}:
        for encoding in ["utf-8", "utf-16", "latin-1", "cp1252"]:
            try:
                return file_path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return "(unable to decode text file)"

    return f"(no parser available for {ext} files)"


def _format_file_metadata(file_path: Path, stat: os.stat_result) -> str:
    """Format file metadata for display."""
    modified = datetime.fromtimestamp(stat.st_mtime)
    created = datetime.fromtimestamp(stat.st_ctime)

    output = f"File Metadata: {file_path.name}\n"
    output += "=" * 50 + "\n\n"
    output += f"Full Path:    {file_path}\n"
    output += f"Extension:    {file_path.suffix or '(none)'}\n"
    output += f"Size:         {_format_size(stat.st_size)}\n"
    output += f"Modified:     {modified.strftime('%Y-%m-%d %H:%M:%S')}\n"
    output += f"Created:      {created.strftime('%Y-%m-%d %H:%M:%S')}\n"

    # File type classification
    file_type = _classify_file(file_path)
    output += f"Type:         {file_type}\n"

    # Check if parseable
    parseable = _is_parseable(file_path)
    output += f"Parseable:    {'Yes' if parseable else 'No'}\n"

    return output


def _format_dir_metadata(dir_path: Path, stat: os.stat_result) -> str:
    """Format directory metadata for display."""
    modified = datetime.fromtimestamp(stat.st_mtime)

    output = f"Directory: {dir_path.name}/\n"
    output += "=" * 50 + "\n\n"
    output += f"Full Path:    {dir_path}\n"
    output += f"Modified:     {modified.strftime('%Y-%m-%d %H:%M:%S')}\n"

    try:
        items = list(dir_path.iterdir())
        files = [i for i in items if i.is_file()]
        dirs = [i for i in items if i.is_dir()]
        output += f"Contents:     {len(files)} files, {len(dirs)} folders\n"
    except PermissionError:
        output += "Contents:     (permission denied)\n"

    return output


def _classify_file(file_path: Path) -> str:
    """Classify a file by its extension."""
    ext = file_path.suffix.lower()

    classifications = {
        ".pdf": "Document (PDF)",
        ".docx": "Document (Word)",
        ".doc": "Document (Word Legacy)",
        ".xlsx": "Spreadsheet (Excel)",
        ".xls": "Spreadsheet (Excel Legacy)",
        ".txt": "Text File",
        ".md": "Markdown Document",
        ".dwg": "CAD Drawing (AutoCAD)",
        ".dxf": "CAD Drawing (DXF)",
        ".rvt": "BIM Model (Revit)",
        ".rfa": "Revit Family",
        ".png": "Image (PNG)",
        ".jpg": "Image (JPEG)",
        ".jpeg": "Image (JPEG)",
        ".gif": "Image (GIF)",
        ".tif": "Image (TIFF)",
        ".tiff": "Image (TIFF)",
        ".csv": "Data (CSV)",
        ".json": "Data (JSON)",
        ".xml": "Data (XML)",
    }

    return classifications.get(ext, f"Unknown ({ext})")


def _is_parseable(file_path: Path) -> bool:
    """Check if a file can be parsed for text content."""
    try:
        from app.services.parsers.registry import get_parser_registry
        registry = get_parser_registry()
        return registry.can_parse(str(file_path))
    except ImportError:
        # Fallback: check common text extensions
        ext = file_path.suffix.lower()
        return ext in {".txt", ".md", ".csv", ".json", ".xml", ".html"}


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
