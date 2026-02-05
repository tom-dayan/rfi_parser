"""
Content Cache for on-demand file parsing.

Caches parsed file content in memory (LRU) and optionally on disk
to avoid re-parsing frequently accessed files.
"""

import hashlib
import json
import os
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from .parsers.registry import get_parser_registry, ParseResult


@dataclass
class CacheEntry:
    """A cached content entry."""

    content: str
    metadata: dict
    file_path: str
    file_modified: float  # File mtime when cached
    cached_at: float  # Time when cached
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)


class ContentCache:
    """
    LRU cache for parsed file content.

    Provides in-memory caching with optional disk overflow for
    frequently accessed files.
    """

    def __init__(
        self,
        max_memory_items: int = 500,
        max_memory_bytes: int = 100 * 1024 * 1024,  # 100MB
        ttl_seconds: int = 24 * 60 * 60,  # 24 hours
        disk_cache_dir: Optional[str] = None,
    ):
        """
        Initialize the content cache.

        Args:
            max_memory_items: Maximum number of items in memory cache
            max_memory_bytes: Maximum total size of memory cache in bytes
            ttl_seconds: Time-to-live for cache entries
            disk_cache_dir: Directory for disk cache (optional)
        """
        self.max_memory_items = max_memory_items
        self.max_memory_bytes = max_memory_bytes
        self.ttl_seconds = ttl_seconds

        # In-memory LRU cache
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_size_bytes = 0
        self._lock = threading.RLock()

        # Disk cache directory
        if disk_cache_dir:
            self._disk_cache_dir = Path(disk_cache_dir)
            self._disk_cache_dir.mkdir(parents=True, exist_ok=True)
        else:
            self._disk_cache_dir = self._default_cache_dir()

        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "disk_hits": 0,
        }

    def _default_cache_dir(self) -> Path:
        """Get default cache directory based on OS."""
        import sys

        if sys.platform == "win32":
            base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        elif sys.platform == "darwin":
            base = Path.home() / "Library" / "Caches"
        else:
            base = Path.home() / ".cache"

        cache_dir = base / "rfi-parser" / "content_cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        return cache_dir

    def _get_cache_key(self, file_path: str) -> str:
        """Generate a cache key for a file path."""
        # Use hash for shorter, filesystem-safe keys
        return hashlib.sha256(file_path.encode()).hexdigest()[:32]

    def get(self, file_path: str, force_refresh: bool = False) -> Optional[CacheEntry]:
        """
        Get cached content for a file.

        Args:
            file_path: Path to the file
            force_refresh: If True, ignore cache and re-parse

        Returns:
            CacheEntry if found and valid, None otherwise
        """
        if force_refresh:
            self._stats["misses"] += 1
            return None

        key = self._get_cache_key(file_path)

        with self._lock:
            # Check memory cache first
            if key in self._cache:
                entry = self._cache[key]

                # Check if file has been modified
                try:
                    current_mtime = Path(file_path).stat().st_mtime
                    if current_mtime > entry.file_modified:
                        # File changed, invalidate cache
                        del self._cache[key]
                        self._stats["misses"] += 1
                        return None
                except (OSError, FileNotFoundError):
                    del self._cache[key]
                    self._stats["misses"] += 1
                    return None

                # Check TTL
                if time.time() - entry.cached_at > self.ttl_seconds:
                    del self._cache[key]
                    self._stats["misses"] += 1
                    return None

                # Move to end (most recently used)
                self._cache.move_to_end(key)
                entry.access_count += 1
                entry.last_accessed = time.time()
                self._stats["hits"] += 1
                return entry

        # Check disk cache
        disk_entry = self._get_from_disk(file_path, key)
        if disk_entry:
            # Promote to memory cache
            with self._lock:
                self._add_to_memory(key, disk_entry)
            self._stats["disk_hits"] += 1
            return disk_entry

        self._stats["misses"] += 1
        return None

    def put(
        self,
        file_path: str,
        content: str,
        metadata: Optional[dict] = None,
    ) -> CacheEntry:
        """
        Cache parsed content for a file.

        Args:
            file_path: Path to the file
            content: Parsed text content
            metadata: Optional metadata dict

        Returns:
            The created cache entry
        """
        key = self._get_cache_key(file_path)

        try:
            mtime = Path(file_path).stat().st_mtime
        except (OSError, FileNotFoundError):
            mtime = time.time()

        entry = CacheEntry(
            content=content,
            metadata=metadata or {},
            file_path=file_path,
            file_modified=mtime,
            cached_at=time.time(),
        )

        with self._lock:
            self._add_to_memory(key, entry)

        # Also save to disk for persistence
        self._save_to_disk(key, entry)

        return entry

    def get_or_parse(
        self,
        file_path: str,
        force_refresh: bool = False,
    ) -> tuple[str, dict, bool]:
        """
        Get cached content or parse the file.

        Args:
            file_path: Path to the file
            force_refresh: If True, ignore cache and re-parse

        Returns:
            Tuple of (content, metadata, was_cached)
        """
        # Try cache first
        entry = self.get(file_path, force_refresh=force_refresh)
        if entry:
            return entry.content, entry.metadata, True

        # Parse the file
        registry = get_parser_registry()
        result = registry.parse(file_path)

        if result.success:
            content = result.text_content or ""
            metadata = result.metadata or {}
        else:
            content = f"(parsing failed: {result.error})"
            metadata = {"error": result.error}

        # Cache the result
        self.put(file_path, content, metadata)

        return content, metadata, False

    def _add_to_memory(self, key: str, entry: CacheEntry) -> None:
        """Add entry to memory cache with LRU eviction."""
        content_size = len(entry.content.encode("utf-8"))

        # Remove existing entry if present
        if key in self._cache:
            old_entry = self._cache.pop(key)
            self._cache_size_bytes -= len(old_entry.content.encode("utf-8"))

        # Evict old entries if needed
        while (
            len(self._cache) >= self.max_memory_items
            or self._cache_size_bytes + content_size > self.max_memory_bytes
        ) and self._cache:
            oldest_key, oldest_entry = self._cache.popitem(last=False)
            self._cache_size_bytes -= len(oldest_entry.content.encode("utf-8"))
            self._stats["evictions"] += 1

            # Optionally save to disk before eviction
            if oldest_entry.access_count > 1:
                self._save_to_disk(oldest_key, oldest_entry)

        # Add new entry
        self._cache[key] = entry
        self._cache_size_bytes += content_size

    def _get_from_disk(self, file_path: str, key: str) -> Optional[CacheEntry]:
        """Get entry from disk cache."""
        cache_file = self._disk_cache_dir / f"{key}.json"
        if not cache_file.exists():
            return None

        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Verify file hasn't changed
            current_mtime = Path(file_path).stat().st_mtime
            if current_mtime > data["file_modified"]:
                cache_file.unlink()
                return None

            # Check TTL
            if time.time() - data["cached_at"] > self.ttl_seconds:
                cache_file.unlink()
                return None

            return CacheEntry(
                content=data["content"],
                metadata=data.get("metadata", {}),
                file_path=file_path,
                file_modified=data["file_modified"],
                cached_at=data["cached_at"],
                access_count=data.get("access_count", 0),
            )

        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def _save_to_disk(self, key: str, entry: CacheEntry) -> None:
        """Save entry to disk cache."""
        cache_file = self._disk_cache_dir / f"{key}.json"

        try:
            data = {
                "content": entry.content,
                "metadata": entry.metadata,
                "file_path": entry.file_path,
                "file_modified": entry.file_modified,
                "cached_at": entry.cached_at,
                "access_count": entry.access_count,
            }
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(data, f)
        except OSError:
            pass  # Disk cache is optional

    def invalidate(self, file_path: str) -> None:
        """Invalidate cache for a specific file."""
        key = self._get_cache_key(file_path)

        with self._lock:
            if key in self._cache:
                entry = self._cache.pop(key)
                self._cache_size_bytes -= len(entry.content.encode("utf-8"))

        # Remove from disk
        cache_file = self._disk_cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                cache_file.unlink()
            except OSError:
                pass

    def clear(self) -> None:
        """Clear all cached content."""
        with self._lock:
            self._cache.clear()
            self._cache_size_bytes = 0

        # Clear disk cache
        for cache_file in self._disk_cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
            except OSError:
                pass

        # Reset stats
        self._stats = {"hits": 0, "misses": 0, "evictions": 0, "disk_hits": 0}

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._stats["hits"] + self._stats["misses"]
            hit_rate = (
                self._stats["hits"] / total_requests if total_requests > 0 else 0
            )

            return {
                "memory_items": len(self._cache),
                "memory_bytes": self._cache_size_bytes,
                "max_memory_items": self.max_memory_items,
                "max_memory_bytes": self.max_memory_bytes,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "disk_hits": self._stats["disk_hits"],
                "evictions": self._stats["evictions"],
                "hit_rate": hit_rate,
            }

    def warm(self, file_paths: list[str]) -> int:
        """
        Pre-cache a list of files.

        Args:
            file_paths: List of file paths to cache

        Returns:
            Number of files successfully cached
        """
        cached = 0
        for path in file_paths:
            try:
                content, _, was_cached = self.get_or_parse(path)
                if not was_cached:
                    cached += 1
            except Exception:
                pass
        return cached


# Global instance
_cache: Optional[ContentCache] = None


def get_content_cache() -> ContentCache:
    """Get or create the global content cache."""
    global _cache
    if _cache is None:
        _cache = ContentCache()
    return _cache
