"""Document chunking for knowledge base indexing."""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class Chunk:
    """A chunk of document text with metadata."""
    text: str
    source_file_id: int
    source_filename: str
    chunk_index: int
    section_title: Optional[str] = None
    page_number: Optional[int] = None

    def to_metadata(self) -> dict:
        """Convert to metadata dict for vector store."""
        return {
            "source_file_id": self.source_file_id,
            "source_filename": self.source_filename,
            "chunk_index": self.chunk_index,
            "section_title": self.section_title or "",
            "page_number": self.page_number or 0,
        }


class DocumentChunker:
    """Chunks documents into smaller pieces for embedding."""

    def __init__(
        self,
        chunk_size: int = 1000,
        chunk_overlap: int = 200,
        min_chunk_size: int = 100
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.min_chunk_size = min_chunk_size

    def chunk_document(
        self,
        text: str,
        file_id: int,
        filename: str,
        content_type: str
    ) -> list[Chunk]:
        """
        Chunk a document into smaller pieces.

        Uses different strategies based on content type:
        - specifications: Split by section headers
        - other: Split by paragraphs/size
        """
        if not text or len(text.strip()) < self.min_chunk_size:
            return []

        if content_type == "specification":
            return self._chunk_specification(text, file_id, filename)
        else:
            return self._chunk_generic(text, file_id, filename)

    def _chunk_specification(
        self,
        text: str,
        file_id: int,
        filename: str
    ) -> list[Chunk]:
        """
        Chunk specification documents by section.

        Specifications typically have structure like:
        PART 1 GENERAL
        1.1 SECTION INCLUDES
        1.2 RELATED REQUIREMENTS
        etc.
        """
        chunks = []

        # Pattern to match spec section headers (e.g., "1.1", "2.3.A", "PART 1")
        section_pattern = re.compile(
            r'^(PART\s+\d+[A-Z\s]*|'  # PART 1 GENERAL
            r'\d+\.\d+(?:\.\d+)?(?:\.[A-Z])?\.?\s+[A-Z])',  # 1.1 SECTION INCLUDES
            re.MULTILINE
        )

        # Find all section starts
        matches = list(section_pattern.finditer(text))

        if not matches:
            # No sections found, fall back to generic chunking
            return self._chunk_generic(text, file_id, filename)

        # Extract sections
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)

            section_text = text[start:end].strip()
            section_title = match.group(0).strip()

            # If section is too large, split it further
            if len(section_text) > self.chunk_size * 2:
                sub_chunks = self._split_by_size(section_text, file_id, filename)
                for j, sub_chunk in enumerate(sub_chunks):
                    sub_chunk.section_title = section_title
                    sub_chunk.chunk_index = len(chunks)
                    chunks.append(sub_chunk)
            elif len(section_text) >= self.min_chunk_size:
                chunks.append(Chunk(
                    text=section_text,
                    source_file_id=file_id,
                    source_filename=filename,
                    chunk_index=len(chunks),
                    section_title=section_title
                ))

        return chunks

    def _chunk_generic(
        self,
        text: str,
        file_id: int,
        filename: str
    ) -> list[Chunk]:
        """Generic chunking by paragraphs and size."""
        # First try to split by paragraphs
        paragraphs = re.split(r'\n\s*\n', text)

        chunks = []
        current_chunk = ""

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # If adding this paragraph would exceed chunk size, save current and start new
            if len(current_chunk) + len(para) > self.chunk_size and current_chunk:
                if len(current_chunk) >= self.min_chunk_size:
                    chunks.append(Chunk(
                        text=current_chunk,
                        source_file_id=file_id,
                        source_filename=filename,
                        chunk_index=len(chunks)
                    ))
                # Start new chunk with overlap
                overlap_start = max(0, len(current_chunk) - self.chunk_overlap)
                current_chunk = current_chunk[overlap_start:] + "\n\n" + para
            else:
                current_chunk = (current_chunk + "\n\n" + para).strip()

        # Don't forget the last chunk
        if current_chunk and len(current_chunk) >= self.min_chunk_size:
            chunks.append(Chunk(
                text=current_chunk,
                source_file_id=file_id,
                source_filename=filename,
                chunk_index=len(chunks)
            ))

        return chunks

    def _split_by_size(
        self,
        text: str,
        file_id: int,
        filename: str
    ) -> list[Chunk]:
        """Split text into fixed-size chunks with overlap."""
        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size

            # Try to break at a sentence boundary
            if end < len(text):
                # Look for sentence end near the chunk boundary
                break_point = text.rfind('. ', start + self.chunk_size // 2, end + 100)
                if break_point > start:
                    end = break_point + 1

            chunk_text = text[start:end].strip()

            if len(chunk_text) >= self.min_chunk_size:
                chunks.append(Chunk(
                    text=chunk_text,
                    source_file_id=file_id,
                    source_filename=filename,
                    chunk_index=len(chunks)
                ))

            start = end - self.chunk_overlap

        return chunks
