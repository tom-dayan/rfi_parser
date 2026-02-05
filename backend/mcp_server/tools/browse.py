"""
Browse tools for navigating the file system.

Provides tools for listing folders and discovering files
within the firm's shared folders.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.types import Tool, TextContent

# Add backend to path for imports
_backend_dir = Path(__file__).parent.parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from mcp_server.config import get_config


def register_browse_tools(server: Server) -> None:
    """Register browse-related tools with the MCP server."""

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return list of browse tools."""
        return [
            Tool(
                name="browse_folder",
                description=(
                    "List files and folders in a directory. "
                    "Returns file names, types, sizes, and modification dates. "
                    "Use this to explore the firm's shared folders."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "path": {
                            "type": "string",
                            "description": (
                                "Path to browse. Use '/' or leave empty for root. "
                                "Supports both Windows (C:\\path) and Unix (/path) formats."
                            ),
                        },
                        "include_hidden": {
                            "type": "boolean",
                            "description": "Include hidden files (starting with .)",
                            "default": False,
                        },
                        "file_types": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Filter by file extensions (e.g., ['pdf', 'docx']). "
                                "Leave empty for all files."
                            ),
                        },
                    },
                    "required": [],
                },
            ),
            Tool(
                name="list_shared_roots",
                description=(
                    "List the configured shared folder roots. "
                    "These are the top-level folders you can browse."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        if name == "browse_folder":
            return await _browse_folder(arguments)
        elif name == "list_shared_roots":
            return await _list_shared_roots()
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


async def _browse_folder(arguments: dict[str, Any]) -> list[TextContent]:
    """Browse a folder and return its contents."""
    config = get_config()

    path_str = arguments.get("path", "")
    include_hidden = arguments.get("include_hidden", False)
    file_types = arguments.get("file_types", [])

    # Normalize file types (remove dots, lowercase)
    file_types = {ft.lstrip(".").lower() for ft in file_types} if file_types else set()

    # Determine the path to browse
    if not path_str or path_str in ("/", "\\", ""):
        # List all shared roots
        return await _list_shared_roots()

    target_path = Path(path_str).resolve()

    # Security check
    if not config.is_path_allowed(target_path):
        return [TextContent(
            type="text",
            text=f"Access denied: Path is outside allowed shared folders.\nPath: {target_path}"
        )]

    if not target_path.exists():
        return [TextContent(
            type="text",
            text=f"Path does not exist: {target_path}"
        )]

    if not target_path.is_dir():
        return [TextContent(
            type="text",
            text=f"Path is not a directory: {target_path}"
        )]

    # List directory contents
    entries = []
    try:
        for entry in sorted(target_path.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            # Skip hidden files if not requested
            if not include_hidden and entry.name.startswith("."):
                continue

            # Filter by file type if specified
            if file_types and entry.is_file():
                if entry.suffix.lstrip(".").lower() not in file_types:
                    continue

            try:
                stat = entry.stat()
                entries.append(_format_entry(entry, stat))
            except (PermissionError, OSError):
                entries.append(f"  [!] {entry.name} (access denied)")

    except PermissionError:
        return [TextContent(
            type="text",
            text=f"Permission denied: Cannot read directory {target_path}"
        )]

    # Format output
    result = f"Contents of: {target_path}\n"
    result += f"{'=' * 60}\n\n"

    if entries:
        result += "\n".join(entries)
    else:
        result += "(empty directory)"

    result += f"\n\n{len(entries)} items"

    return [TextContent(type="text", text=result)]


async def _list_shared_roots() -> list[TextContent]:
    """List configured shared folder roots."""
    config = get_config()

    if not config.shared_folders_root:
        return [TextContent(
            type="text",
            text=(
                "No shared folder roots configured.\n"
                "Set SHARED_FOLDERS_ROOT environment variable to configure access.\n\n"
                "Example:\n"
                "  Windows: SHARED_FOLDERS_ROOT=C:\\SharedFolders,D:\\Projects\n"
                "  macOS: SHARED_FOLDERS_ROOT=/Volumes/Shared,/Users/Shared/Projects"
            )
        )]

    result = "Configured Shared Folder Roots:\n"
    result += "=" * 40 + "\n\n"

    for root in config.shared_folders_root:
        if root.exists():
            try:
                item_count = len(list(root.iterdir()))
                result += f"  [OK] {root}\n"
                result += f"       ({item_count} items)\n\n"
            except PermissionError:
                result += f"  [!] {root}\n"
                result += f"       (permission denied)\n\n"
        else:
            result += f"  [X] {root}\n"
            result += f"       (does not exist)\n\n"

    return [TextContent(type="text", text=result)]


def _format_entry(entry: Path, stat: os.stat_result) -> str:
    """Format a directory entry for display."""
    if entry.is_dir():
        return f"  [DIR]  {entry.name}/"
    else:
        size = _format_size(stat.st_size)
        modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M")
        ext = entry.suffix.lower() or "(no ext)"
        return f"  [FILE] {entry.name:<40} {size:>10}  {modified}  {ext}"


def _format_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}" if unit != "B" else f"{size_bytes} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"
