from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


@dataclass
class ParseResult:
    """Result of parsing a document"""
    success: bool
    text_content: Optional[str] = None
    metadata: dict = field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def success_result(cls, text: str, metadata: Optional[dict] = None) -> 'ParseResult':
        return cls(success=True, text_content=text, metadata=metadata or {})

    @classmethod
    def error_result(cls, error: str) -> 'ParseResult':
        return cls(success=False, error=error)


class DocumentParser(ABC):
    """Abstract base class for document parsers"""

    # File extensions this parser handles (lowercase, without dot)
    supported_extensions: list[str] = []

    @abstractmethod
    def parse(self, file_path: str) -> ParseResult:
        """
        Parse a document and extract text content and metadata

        Args:
            file_path: Absolute path to the file

        Returns:
            ParseResult with text content and metadata
        """
        pass

    @abstractmethod
    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """
        Parse document from bytes

        Args:
            content: File content as bytes
            filename: Original filename (for extension detection)

        Returns:
            ParseResult with text content and metadata
        """
        pass

    def can_parse(self, file_path: str) -> bool:
        """Check if this parser can handle the given file"""
        extension = Path(file_path).suffix.lower().lstrip('.')
        return extension in self.supported_extensions

    def _read_file(self, file_path: str) -> bytes:
        """Read file content as bytes"""
        with open(file_path, 'rb') as f:
            return f.read()
