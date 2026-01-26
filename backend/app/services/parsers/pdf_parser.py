import io
from typing import Optional
import PyPDF2
import pdfplumber
from .base import DocumentParser, ParseResult


class PDFParser(DocumentParser):
    """Parser for PDF documents"""

    supported_extensions = ['pdf']

    def parse(self, file_path: str) -> ParseResult:
        """Parse PDF file from path"""
        try:
            content = self._read_file(file_path)
            return self.parse_bytes(content, file_path)
        except Exception as e:
            return ParseResult.error_result(f"Failed to read file: {str(e)}")

    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """Parse PDF from bytes"""
        text_parts = []
        metadata = {
            'page_count': 0,
            'has_images': False,
            'has_tables': False,
        }

        # Try PyPDF2 first (faster for simple PDFs)
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            metadata['page_count'] = len(pdf_reader.pages)

            # Extract document info
            if pdf_reader.metadata:
                if pdf_reader.metadata.title:
                    metadata['title'] = pdf_reader.metadata.title
                if pdf_reader.metadata.author:
                    metadata['author'] = pdf_reader.metadata.author

            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(f"[Page {page_num + 1}]\n{text}")

                # Check for images
                if '/XObject' in page.get('/Resources', {}):
                    metadata['has_images'] = True

        except Exception as e:
            # PyPDF2 failed, try pdfplumber
            pass

        # If PyPDF2 didn't extract much text, try pdfplumber
        if not text_parts or all(len(t) < 50 for t in text_parts):
            try:
                pdf_file = io.BytesIO(content)
                with pdfplumber.open(pdf_file) as pdf:
                    metadata['page_count'] = len(pdf.pages)
                    text_parts = []

                    for page_num, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text and text.strip():
                            text_parts.append(f"[Page {page_num + 1}]\n{text}")

                        # Check for tables
                        tables = page.extract_tables()
                        if tables:
                            metadata['has_tables'] = True
                            for table in tables:
                                table_text = self._format_table(table)
                                if table_text:
                                    text_parts.append(f"[Table on Page {page_num + 1}]\n{table_text}")

                        # Check for images
                        if page.images:
                            metadata['has_images'] = True

            except Exception as e:
                return ParseResult.error_result(f"Failed to parse PDF: {str(e)}")

        if not text_parts:
            # PDF might be image-only (scanned document)
            metadata['is_scanned'] = True
            return ParseResult.success_result(
                text="[This appears to be a scanned/image-only PDF. Text extraction requires OCR.]",
                metadata=metadata
            )

        return ParseResult.success_result(
            text="\n\n".join(text_parts),
            metadata=metadata
        )

    def _format_table(self, table: list) -> Optional[str]:
        """Format extracted table as text"""
        if not table:
            return None

        rows = []
        for row in table:
            if row:
                cells = [str(cell) if cell else '' for cell in row]
                rows.append(' | '.join(cells))

        return '\n'.join(rows) if rows else None
