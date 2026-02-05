#!/usr/bin/env python3
"""
MCP Server for Firm Knowledge Base

Main entry point for the MCP server. Can be run directly or invoked
by MCP clients like Claude Desktop.

Cross-platform compatible (Windows, macOS, Linux).

Usage:
    python server.py                    # Run with stdio transport (for Claude Desktop)
    python server.py --transport sse    # Run with SSE transport (for web clients)

Environment Variables:
    SHARED_FOLDERS_ROOT     - Comma-separated list of allowed folder paths
    ALLOWED_EXTENSIONS      - Comma-separated list of allowed file extensions
    MCP_LOG_LEVEL          - Logging level (DEBUG, INFO, WARNING, ERROR)
    MCP_LOG_FILE           - Path to log file (optional)
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Ensure the directories are in the path for imports
_current_dir = Path(__file__).parent
_backend_dir = _current_dir.parent
# Add both mcp_server directory (for local imports) and backend directory
if str(_current_dir) not in sys.path:
    sys.path.insert(0, str(_current_dir))
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from mcp.server import Server
from mcp.server.stdio import stdio_server

from mcp_server.config import get_config, MCPConfig


def setup_logging(config: MCPConfig) -> logging.Logger:
    """Configure logging based on config."""
    logger = logging.getLogger("mcp_server")
    logger.setLevel(getattr(logging, config.log_level.upper(), logging.INFO))

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler (stderr to avoid interfering with stdio transport)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler if configured
    if config.log_file:
        try:
            config.log_file.parent.mkdir(parents=True, exist_ok=True)
            file_handler = logging.FileHandler(config.log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Could not set up file logging: {e}")

    return logger


def create_server() -> Server:
    """Create and configure the MCP server."""
    config = get_config()

    # Create the server
    server = Server(config.server_name)

    # Register all tools
    # Note: Due to how MCP decorators work, we need to carefully merge tool registrations
    _register_all_tools(server)

    return server


def _register_all_tools(server: Server) -> None:
    """Register all tools with the server."""
    from mcp.types import Tool, TextContent
    from typing import Any

    # Collect all tools from modules
    browse_tools = _get_browse_tools()
    search_tools = _get_search_tools()
    content_tools = _get_content_tools()
    oli_tools = _get_oli_tools()

    all_tools = browse_tools + search_tools + content_tools + oli_tools

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """Return all available tools."""
        return all_tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Route tool calls to the appropriate handler."""
        # Import handlers
        from mcp_server.tools.browse import _browse_folder, _list_shared_roots
        from mcp_server.tools.search import _search_files, _search_drawings
        from mcp_server.tools.content import _get_file_content, _get_file_metadata
        from mcp_server.tools.oli import OLI_HANDLERS

        handlers = {
            "browse_folder": _browse_folder,
            "list_shared_roots": _list_shared_roots,
            "search_files": _search_files,
            "search_drawings": _search_drawings,
            "get_file_content": _get_file_content,
            "get_file_metadata": _get_file_metadata,
            **OLI_HANDLERS,  # Add OLI-specific tools
        }

        handler = handlers.get(name)
        if handler:
            return await handler(arguments)
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]


def _get_browse_tools():
    """Get browse tool definitions."""
    from mcp.types import Tool

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


def _get_search_tools():
    """Get search tool definitions."""
    from mcp.types import Tool

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
                        "description": "Maximum results to return (default: 50, max: 100)",
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


def _get_content_tools():
    """Get content tool definitions."""
    from mcp.types import Tool

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


def _get_oli_tools():
    """Get OLI-specific tool definitions."""
    from mcp_server.tools.oli import get_oli_tools
    return get_oli_tools()


async def run_stdio_server(server: Server, logger: logging.Logger) -> None:
    """Run the server with stdio transport."""
    logger.info("Starting MCP server with stdio transport...")

    config = get_config()
    warnings = config.validate()
    for warning in warnings:
        logger.warning(warning)

    if config.shared_folders_root:
        logger.info(f"Shared folder roots: {[str(p) for p in config.shared_folders_root]}")
    else:
        logger.warning("No shared folder roots configured - all paths accessible")

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="MCP Server for Firm Knowledge Base",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="Transport type (default: stdio)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8001,
        help="Port for SSE transport (default: 8001)",
    )
    args = parser.parse_args()

    # Setup
    config = get_config()
    logger = setup_logging(config)
    server = create_server()

    if args.transport == "stdio":
        asyncio.run(run_stdio_server(server, logger))
    else:
        # SSE transport would go here
        logger.error("SSE transport not yet implemented")
        sys.exit(1)


if __name__ == "__main__":
    main()
