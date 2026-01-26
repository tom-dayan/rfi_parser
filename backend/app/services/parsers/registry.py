from pathlib import Path
from typing import Optional
from .base import DocumentParser, ParseResult
from .pdf_parser import PDFParser
from .docx_parser import DocxParser
from .cad_parser import CADParser
from .image_parser import ImageParser


class TextParser(DocumentParser):
    """Simple parser for plain text files"""

    supported_extensions = ['txt', 'md', 'markdown', 'csv', 'json', 'xml', 'html']

    def parse(self, file_path: str) -> ParseResult:
        """Parse text file from path"""
        try:
            content = self._read_file(file_path)
            return self.parse_bytes(content, file_path)
        except Exception as e:
            return ParseResult.error_result(f"Failed to read file: {str(e)}")

    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """Parse text from bytes"""
        # Try different encodings
        for encoding in ['utf-8', 'utf-16', 'latin-1', 'cp1252']:
            try:
                text = content.decode(encoding)
                return ParseResult.success_result(
                    text=text,
                    metadata={
                        'encoding': encoding,
                        'line_count': text.count('\n') + 1,
                        'char_count': len(text)
                    }
                )
            except UnicodeDecodeError:
                continue

        return ParseResult.error_result("Failed to decode text file with supported encodings")


class ParserRegistry:
    """Registry of document parsers"""

    def __init__(self, enable_ocr: bool = False):
        """
        Initialize parser registry

        Args:
            enable_ocr: Whether to enable OCR for image parsing
        """
        self._parsers: dict[str, DocumentParser] = {}

        # Register default parsers
        self.register_parser(PDFParser())
        self.register_parser(DocxParser())
        self.register_parser(CADParser())
        self.register_parser(ImageParser(enable_ocr=enable_ocr))
        self.register_parser(TextParser())

    def register_parser(self, parser: DocumentParser) -> None:
        """Register a parser for its supported extensions"""
        for ext in parser.supported_extensions:
            self._parsers[ext.lower()] = parser

    def get_parser(self, file_path: str) -> Optional[DocumentParser]:
        """Get parser for a file based on extension"""
        extension = Path(file_path).suffix.lower().lstrip('.')
        return self._parsers.get(extension)

    def can_parse(self, file_path: str) -> bool:
        """Check if any parser can handle the file"""
        return self.get_parser(file_path) is not None

    def parse(self, file_path: str) -> ParseResult:
        """Parse a file using the appropriate parser"""
        parser = self.get_parser(file_path)
        if parser:
            return parser.parse(file_path)
        return ParseResult.error_result(f"No parser available for file: {file_path}")

    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """Parse file content from bytes"""
        parser = self.get_parser(filename)
        if parser:
            return parser.parse_bytes(content, filename)
        return ParseResult.error_result(f"No parser available for file: {filename}")

    @property
    def supported_extensions(self) -> list[str]:
        """Get list of all supported extensions"""
        return list(self._parsers.keys())


# Global registry instance
_registry: Optional[ParserRegistry] = None


def get_parser_registry(enable_ocr: bool = False) -> ParserRegistry:
    """Get or create the global parser registry"""
    global _registry
    if _registry is None:
        _registry = ParserRegistry(enable_ocr=enable_ocr)
    return _registry


def get_parser(file_path: str) -> Optional[DocumentParser]:
    """Convenience function to get parser for a file"""
    return get_parser_registry().get_parser(file_path)
