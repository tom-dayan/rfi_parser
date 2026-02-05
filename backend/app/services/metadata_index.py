"""
Metadata Index for fast file discovery.

Uses SQLite to store file metadata (path, name, type, size, dates)
without parsing file content. This enables fast searching across
large file systems.
"""

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Optional

from ..config import settings


class MetadataIndex:
    """SQLite-based metadata index for fast file discovery."""

    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the metadata index.

        Args:
            db_path: Path to SQLite database. Defaults to app data directory.
        """
        if db_path is None:
            db_path = self._default_db_path()

        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _default_db_path(self) -> str:
        """Get default database path based on OS."""
        import sys

        if sys.platform == "win32":
            base = Path(os.environ.get("APPDATA", Path.home()))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Application Support"
        else:
            base = Path.home() / ".local" / "share"

        return str(base / "rfi-parser" / "metadata_index.db")

    @contextmanager
    def _get_conn(self) -> Generator[sqlite3.Connection, None, None]:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT UNIQUE NOT NULL,
                    filename TEXT NOT NULL,
                    extension TEXT,
                    file_type TEXT,
                    size_bytes INTEGER,
                    modified_at TIMESTAMP,
                    created_at TIMESTAMP,
                    project_id INTEGER,
                    project_name TEXT,
                    indexed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_files_filename ON files(filename);
                CREATE INDEX IF NOT EXISTS idx_files_extension ON files(extension);
                CREATE INDEX IF NOT EXISTS idx_files_file_type ON files(file_type);
                CREATE INDEX IF NOT EXISTS idx_files_project_id ON files(project_id);
                CREATE INDEX IF NOT EXISTS idx_files_modified_at ON files(modified_at);

                CREATE TABLE IF NOT EXISTS scan_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    root_path TEXT NOT NULL,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    files_found INTEGER DEFAULT 0,
                    files_added INTEGER DEFAULT 0,
                    files_updated INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'running'
                );
            """)
            conn.commit()

    def index_file(
        self,
        path: Path,
        project_id: Optional[int] = None,
        project_name: Optional[str] = None,
    ) -> bool:
        """
        Index a single file's metadata.

        Args:
            path: Path to the file
            project_id: Optional project ID
            project_name: Optional project name

        Returns:
            True if file was indexed, False if skipped
        """
        if not path.exists() or not path.is_file():
            return False

        try:
            stat = path.stat()
        except (PermissionError, OSError):
            return False

        file_type = self._classify_file(path)

        with self._get_conn() as conn:
            conn.execute(
                """
                INSERT INTO files (path, filename, extension, file_type, size_bytes,
                                   modified_at, created_at, project_id, project_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(path) DO UPDATE SET
                    filename = excluded.filename,
                    extension = excluded.extension,
                    file_type = excluded.file_type,
                    size_bytes = excluded.size_bytes,
                    modified_at = excluded.modified_at,
                    project_id = COALESCE(excluded.project_id, files.project_id),
                    project_name = COALESCE(excluded.project_name, files.project_name),
                    indexed_at = CURRENT_TIMESTAMP
                """,
                (
                    str(path.resolve()),
                    path.name,
                    path.suffix.lower().lstrip(".") or None,
                    file_type,
                    stat.st_size,
                    datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    datetime.fromtimestamp(stat.st_ctime).isoformat(),
                    project_id,
                    project_name,
                ),
            )
            conn.commit()

        return True

    def scan_directory(
        self,
        root_path: Path,
        project_id: Optional[int] = None,
        project_name: Optional[str] = None,
        allowed_extensions: Optional[set[str]] = None,
    ) -> dict:
        """
        Scan a directory and index all files.

        Args:
            root_path: Root directory to scan
            project_id: Optional project ID
            project_name: Optional project name
            allowed_extensions: Optional set of allowed extensions (without dots)

        Returns:
            Dict with scan statistics
        """
        stats = {
            "files_found": 0,
            "files_indexed": 0,
            "files_skipped": 0,
            "errors": 0,
        }

        # Start scan history record
        with self._get_conn() as conn:
            cursor = conn.execute(
                "INSERT INTO scan_history (root_path) VALUES (?)",
                (str(root_path),)
            )
            scan_id = cursor.lastrowid
            conn.commit()

        try:
            for dirpath, dirnames, filenames in os.walk(root_path):
                # Skip hidden directories
                dirnames[:] = [d for d in dirnames if not d.startswith(".")]

                current_dir = Path(dirpath)

                for filename in filenames:
                    # Skip hidden files
                    if filename.startswith("."):
                        continue

                    file_path = current_dir / filename
                    stats["files_found"] += 1

                    # Check extension filter
                    if allowed_extensions:
                        ext = file_path.suffix.lower().lstrip(".")
                        if ext not in allowed_extensions:
                            stats["files_skipped"] += 1
                            continue

                    try:
                        if self.index_file(file_path, project_id, project_name):
                            stats["files_indexed"] += 1
                        else:
                            stats["files_skipped"] += 1
                    except Exception:
                        stats["errors"] += 1

        except PermissionError:
            stats["errors"] += 1

        # Complete scan history record
        with self._get_conn() as conn:
            conn.execute(
                """
                UPDATE scan_history
                SET completed_at = CURRENT_TIMESTAMP,
                    files_found = ?,
                    files_added = ?,
                    status = 'completed'
                WHERE id = ?
                """,
                (stats["files_found"], stats["files_indexed"], scan_id),
            )
            conn.commit()

        return stats

    def search(
        self,
        query: str,
        file_types: Optional[list[str]] = None,
        extensions: Optional[list[str]] = None,
        project_id: Optional[int] = None,
        modified_after: Optional[datetime] = None,
        modified_before: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Search for files by name pattern.

        Args:
            query: Search query (supports % wildcards)
            file_types: Optional list of file types to filter
            extensions: Optional list of extensions to filter
            project_id: Optional project ID to filter
            modified_after: Optional minimum modification date
            modified_before: Optional maximum modification date
            limit: Maximum results to return

        Returns:
            List of matching file records
        """
        # Build query with wildcards if not already present
        if "%" not in query and "*" not in query:
            query = f"%{query}%"
        query = query.replace("*", "%")

        sql = "SELECT * FROM files WHERE filename LIKE ?"
        params: list = [query]

        if file_types:
            placeholders = ",".join("?" * len(file_types))
            sql += f" AND file_type IN ({placeholders})"
            params.extend(file_types)

        if extensions:
            # Normalize extensions (remove dots)
            extensions = [e.lstrip(".").lower() for e in extensions]
            placeholders = ",".join("?" * len(extensions))
            sql += f" AND extension IN ({placeholders})"
            params.extend(extensions)

        if project_id is not None:
            sql += " AND project_id = ?"
            params.append(project_id)

        if modified_after:
            sql += " AND modified_at >= ?"
            params.append(modified_after.isoformat())

        if modified_before:
            sql += " AND modified_at <= ?"
            params.append(modified_before.isoformat())

        sql += " ORDER BY modified_at DESC LIMIT ?"
        params.append(limit)

        with self._get_conn() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(row) for row in rows]

    def get_file(self, path: str) -> Optional[dict]:
        """Get file metadata by path."""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM files WHERE path = ?",
                (path,)
            ).fetchone()
            return dict(row) if row else None

    def get_stats(self) -> dict:
        """Get index statistics."""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
            by_type = conn.execute(
                "SELECT file_type, COUNT(*) as count FROM files GROUP BY file_type"
            ).fetchall()
            by_ext = conn.execute(
                "SELECT extension, COUNT(*) as count FROM files GROUP BY extension ORDER BY count DESC LIMIT 10"
            ).fetchall()

            return {
                "total_files": total,
                "by_type": {row["file_type"]: row["count"] for row in by_type},
                "top_extensions": {row["extension"]: row["count"] for row in by_ext},
            }

    def clear(self) -> None:
        """Clear all indexed files."""
        with self._get_conn() as conn:
            conn.execute("DELETE FROM files")
            conn.commit()

    def remove_missing(self) -> int:
        """Remove entries for files that no longer exist."""
        removed = 0
        with self._get_conn() as conn:
            rows = conn.execute("SELECT id, path FROM files").fetchall()
            for row in rows:
                if not Path(row["path"]).exists():
                    conn.execute("DELETE FROM files WHERE id = ?", (row["id"],))
                    removed += 1
            conn.commit()
        return removed

    def _classify_file(self, path: Path) -> str:
        """Classify a file by its extension and name."""
        ext = path.suffix.lower()
        name_lower = path.name.lower()

        # Check for RFI/Submittal patterns
        if "rfi" in name_lower:
            return "rfi"
        if "submittal" in name_lower:
            return "submittal"

        # Check by extension
        ext_types = {
            ".pdf": "document",
            ".docx": "document",
            ".doc": "document",
            ".xlsx": "spreadsheet",
            ".xls": "spreadsheet",
            ".txt": "text",
            ".md": "text",
            ".dwg": "drawing",
            ".dxf": "drawing",
            ".rvt": "model",
            ".rfa": "model",
            ".png": "image",
            ".jpg": "image",
            ".jpeg": "image",
            ".gif": "image",
            ".tif": "image",
            ".tiff": "image",
        }

        # Check for spec patterns
        if "spec" in name_lower:
            return "specification"

        return ext_types.get(ext, "other")


# Global instance
_index: Optional[MetadataIndex] = None


def get_metadata_index() -> MetadataIndex:
    """Get or create the global metadata index."""
    global _index
    if _index is None:
        _index = MetadataIndex()
    return _index
