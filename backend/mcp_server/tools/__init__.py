"""
MCP Tools for the Knowledge Base Server

These tools are exposed to MCP clients (Claude Desktop, Cursor, etc.)
and provide access to the firm's shared folders.
"""

from .browse import register_browse_tools
from .search import register_search_tools
from .content import register_content_tools

__all__ = [
    "register_browse_tools",
    "register_search_tools",
    "register_content_tools",
]
