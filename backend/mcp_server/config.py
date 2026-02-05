"""
MCP Server Configuration

Cross-platform configuration for the MCP knowledge base server.
All paths use pathlib for Windows/Mac compatibility.
"""

import os
import sys
from pathlib import Path
from typing import Optional


class MCPConfig:
    """Configuration for the MCP server."""

    def __init__(self):
        # Root paths for shared folders (can be multiple, comma-separated)
        self.shared_folders_root: list[Path] = self._parse_paths(
            os.environ.get("SHARED_FOLDERS_ROOT", "")
        )

        # Allowed file extensions (comma-separated, with dots)
        allowed_ext = os.environ.get(
            "ALLOWED_EXTENSIONS",
            ".pdf,.docx,.doc,.txt,.md,.dwg,.dxf,.png,.jpg,.jpeg,.gif,.csv,.json,.xml"
        )
        self.allowed_extensions: set[str] = {
            ext.strip().lower() for ext in allowed_ext.split(",") if ext.strip()
        }

        # Maximum file size for content parsing (default: 50MB)
        self.max_file_size: int = int(
            os.environ.get("MCP_MAX_FILE_SIZE", str(50 * 1024 * 1024))
        )

        # Cache settings
        self.cache_ttl_seconds: int = int(
            os.environ.get("MCP_CACHE_TTL", str(24 * 60 * 60))  # 24 hours
        )
        self.cache_max_items: int = int(
            os.environ.get("MCP_CACHE_MAX_ITEMS", "1000")
        )

        # Database path for metadata index
        self.metadata_db_path: Path = Path(
            os.environ.get("MCP_METADATA_DB", self._default_db_path())
        )

        # Logging
        self.log_level: str = os.environ.get("MCP_LOG_LEVEL", "INFO")
        self.log_file: Optional[Path] = self._parse_log_path(
            os.environ.get("MCP_LOG_FILE")
        )

        # Server settings
        self.server_name: str = os.environ.get("MCP_SERVER_NAME", "firm-knowledge-base")

    def _parse_paths(self, paths_str: str) -> list[Path]:
        """Parse comma-separated paths, handling both Windows and Unix paths."""
        if not paths_str:
            return []

        paths = []
        for path_str in paths_str.split(","):
            path_str = path_str.strip()
            if path_str:
                path = Path(path_str).resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)
        return paths

    def _parse_log_path(self, log_path: Optional[str]) -> Optional[Path]:
        """Parse log file path."""
        if not log_path:
            return None
        return Path(log_path).resolve()

    def _default_db_path(self) -> str:
        """Get default database path based on OS."""
        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home()))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path.home() / ".local" / "share"

        db_dir = base / "rfi-parser"
        db_dir.mkdir(parents=True, exist_ok=True)
        return str(db_dir / "mcp_metadata.db")

    def is_path_allowed(self, path: Path) -> bool:
        """Check if a path is within allowed shared folders."""
        if not self.shared_folders_root:
            # If no roots configured, allow all paths (for development)
            return True

        resolved = path.resolve()
        for root in self.shared_folders_root:
            try:
                resolved.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def is_extension_allowed(self, path: Path) -> bool:
        """Check if file extension is allowed."""
        if not self.allowed_extensions:
            return True
        return path.suffix.lower() in self.allowed_extensions

    def validate(self) -> list[str]:
        """Validate configuration and return list of warnings."""
        warnings = []

        if not self.shared_folders_root:
            warnings.append(
                "SHARED_FOLDERS_ROOT not configured. "
                "All paths will be accessible (not recommended for production)."
            )

        for root in self.shared_folders_root:
            if not root.exists():
                warnings.append(f"Shared folder root does not exist: {root}")

        return warnings


# Global config instance
_config: Optional[MCPConfig] = None


def get_config() -> MCPConfig:
    """Get or create the global config instance."""
    global _config
    if _config is None:
        _config = MCPConfig()
    return _config
