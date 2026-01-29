"""
Question Extractor Service

Extracts the core question, keywords, and spec references from RFI documents.
RFIs typically have a standard structure with clearly marked "Question" sections.
"""
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class ExtractedQuestion:
    """Structured data extracted from an RFI document."""
    question: str  # The core question text
    keywords: list[str]  # Technical keywords for search
    spec_sections: list[str]  # Referenced spec sections (e.g., "033000")
    rfi_number: Optional[str] = None
    rfi_title: Optional[str] = None
    drawing_references: list[str] = None
    
    def __post_init__(self):
        if self.drawing_references is None:
            self.drawing_references = []
    
    def get_search_queries(self) -> list[str]:
        """
        Generate multiple search queries for RAG retrieval.
        Returns a list of queries optimized for finding relevant specs.
        """
        queries = []
        
        # Primary query: the core question (limited length)
        if self.question:
            # Take first 500 chars of question for focused search
            queries.append(self.question[:500])
        
        # Keyword-based queries
        if self.keywords:
            # Combine keywords into focused queries
            queries.append(" ".join(self.keywords[:5]))
        
        # Spec section queries
        for section in self.spec_sections:
            queries.append(f"specification section {section}")
        
        return queries


# Common construction/architecture terms for keyword extraction
CONSTRUCTION_KEYWORDS = {
    # Structural
    "rebar", "reinforcement", "reinforcing", "concrete", "footing", "foundation",
    "slab", "column", "beam", "truss", "shear wall", "mat", "pile", "grade beam",
    "anchor", "embed", "dowel", "stirrup", "tie", "spacing", "cover", "lap",
    
    # Waterproofing
    "waterproofing", "waterproof", "membrane", "vapor barrier", "dampproofing",
    "sealant", "caulking", "flashing", "drainage", "below grade", "hydrostatic",
    
    # Materials
    "sika", "thoroseal", "epoxy", "cementitious", "polymer", "adhesive",
    "grout", "mortar", "aggregate", "admixture",
    
    # MEP
    "electrical", "mechanical", "plumbing", "hvac", "ductwork", "conduit",
    "piping", "drainage", "sanitary", "fire protection", "sprinkler",
    
    # Architectural
    "finish", "ceiling", "flooring", "partition", "glazing", "door", "window",
    "hardware", "paint", "coating", "insulation", "acoustic",
    
    # Actions/Approvals
    "approval", "review", "confirm", "clarify", "coordinate", "verify",
    "submittal", "shop drawing", "mock-up", "sample",
}

# Regex pattern to find spec section numbers (CSI format)
SPEC_SECTION_PATTERN = re.compile(
    r'\b(\d{2}\s?\d{2}\s?\d{2})\b|'  # 033000 or 03 30 00
    r'\b(Section\s+\d{2}\s?\d{2}\s?\d{2})\b',  # Section 033000
    re.IGNORECASE
)

# Pattern to find drawing references
DRAWING_PATTERN = re.compile(
    r'\b([A-Z]-?\d{3}(?:\.\d)?)\b|'  # A501, S-106, A501.1
    r'\b(Drawing\s+(?:No\.?\s*)?[A-Z]?\d+)\b',
    re.IGNORECASE
)


def extract_question(document_content: str, filename: str = "") -> ExtractedQuestion:
    """
    Extract the core question and metadata from an RFI document.
    
    Args:
        document_content: Full text content of the RFI
        filename: Optional filename for additional context
        
    Returns:
        ExtractedQuestion with parsed data
    """
    # Extract RFI number from filename or content
    rfi_number = _extract_rfi_number(filename, document_content)
    
    # Extract the actual question section
    question_text = _extract_question_section(document_content)
    
    # If no clear question section found, try to get the main content
    if not question_text or len(question_text) < 50:
        question_text = _extract_main_content(document_content)
    
    # Extract keywords from the question
    keywords = _extract_keywords(question_text)
    
    # Extract spec section references
    spec_sections = _extract_spec_sections(document_content)
    
    # Extract drawing references
    drawing_refs = _extract_drawing_refs(document_content)
    
    # Extract title
    rfi_title = _extract_rfi_title(document_content, filename)
    
    return ExtractedQuestion(
        question=question_text,
        keywords=keywords,
        spec_sections=spec_sections,
        rfi_number=rfi_number,
        rfi_title=rfi_title,
        drawing_references=drawing_refs
    )


def _extract_rfi_number(filename: str, content: str) -> Optional[str]:
    """Extract RFI number from filename or content."""
    # Try filename first (e.g., "260113_RFI #91_...")
    match = re.search(r'RFI\s*#?\s*(\d+)', filename, re.IGNORECASE)
    if match:
        return f"RFI #{match.group(1)}"
    
    # Try content
    match = re.search(r'RFI\s*#?\s*(\d+)', content[:1000], re.IGNORECASE)
    if match:
        return f"RFI #{match.group(1)}"
    
    return None


def _extract_rfi_title(content: str, filename: str) -> Optional[str]:
    """Extract RFI title from content or filename."""
    # Try to find title after RFI number in content
    match = re.search(
        r'RFI\s*#?\s*\d+[:\s]*([^\n]+)',
        content[:2000],
        re.IGNORECASE
    )
    if match:
        title = match.group(1).strip()
        # Clean up common suffixes
        title = re.sub(r'\s*Revision\s*\d+.*$', '', title, flags=re.IGNORECASE)
        if len(title) > 10:
            return title[:200]
    
    # Try filename
    match = re.search(r'RFI\s*#?\s*\d+[_\s]*(.+?)(?:\.pdf|$)', filename, re.IGNORECASE)
    if match:
        title = match.group(1).replace('_', ' ').strip()
        if len(title) > 5:
            return title[:200]
    
    return None


def _extract_question_section(content: str) -> str:
    """
    Extract the actual question from the RFI document.
    RFIs typically have a "Question" section clearly marked.
    """
    # Common patterns for question sections in construction RFIs
    # Each pattern must have a capture group (1)
    patterns = [
        # "Question" followed by content
        r'Question[:\s]*(?:Question from[^:]+:)?\s*(.+?)(?=Attachments|Awaiting|Response|Official|$)',
        
        # "Question from [Name]" pattern
        r'Question from[^:]+:\s*(.+?)(?=Attachments|Awaiting|Response|$)',
        
        # Direct question pattern - wrapped in capture group
        r'((?:Please\s+)?(?:review|confirm|clarify|advise|provide)[^.]*\.[^.]*(?:\.[^.]*)?)',
    ]
    
    for pattern in patterns:
        try:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match and match.lastindex and match.lastindex >= 1:
                question = match.group(1).strip()
                # Clean up the extracted text
                question = _clean_extracted_text(question)
                if len(question) > 50:  # Minimum viable question length
                    return question
        except (IndexError, AttributeError):
            continue
    
    return ""


def _extract_main_content(content: str) -> str:
    """
    Fallback: Extract the main content area of the document.
    Skip headers, addresses, and other metadata.
    """
    lines = content.split('\n')
    
    # Skip initial metadata (addresses, project info)
    start_idx = 0
    for i, line in enumerate(lines):
        # Look for content start indicators
        if any(keyword in line.lower() for keyword in 
               ['question', 'request', 'please', 'confirm', 'review', 'clarify']):
            start_idx = i
            break
        # Skip past common header content
        if i > 30:  # Don't skip too much
            start_idx = 10  # Start after basic headers
            break
    
    # Get content until attachments/signatures
    end_idx = len(lines)
    for i in range(start_idx, len(lines)):
        line_lower = lines[i].lower()
        if any(keyword in line_lower for keyword in 
               ['attachment', 'awaiting', 'printed on', 'page 1 of', '-- 1 of']):
            end_idx = i
            break
    
    content_lines = lines[start_idx:end_idx]
    content = '\n'.join(content_lines)
    
    return _clean_extracted_text(content)[:2000]


def _clean_extracted_text(text: str) -> str:
    """Clean up extracted text, removing noise."""
    # Remove multiple newlines
    text = re.sub(r'\n\s*\n', '\n', text)
    
    # Remove page markers
    text = re.sub(r'--\s*\d+\s*of\s*\d+\s*--', '', text)
    
    # Remove common metadata patterns
    text = re.sub(r'Page\s*\d+\s*of\s*\d+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Printed On:.*$', '', text, flags=re.MULTILINE | re.IGNORECASE)
    
    # Clean up whitespace
    text = ' '.join(text.split())
    
    return text.strip()


def _extract_keywords(text: str) -> list[str]:
    """Extract relevant construction keywords from the text."""
    text_lower = text.lower()
    found_keywords = []
    
    for keyword in CONSTRUCTION_KEYWORDS:
        if keyword.lower() in text_lower:
            found_keywords.append(keyword)
    
    # Also extract any product names (capitalized multi-word terms)
    product_pattern = re.compile(r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b')
    products = product_pattern.findall(text)
    for product in products:
        if len(product) > 5 and product.lower() not in [k.lower() for k in found_keywords]:
            found_keywords.append(product)
    
    # Extract Sika or other brand names
    brand_pattern = re.compile(r'\b(Sika\s*\w+(?:\s*\d+)?)\b', re.IGNORECASE)
    brands = brand_pattern.findall(text)
    found_keywords.extend(brands)
    
    # Deduplicate while preserving order
    seen = set()
    unique_keywords = []
    for kw in found_keywords:
        kw_lower = kw.lower()
        if kw_lower not in seen:
            seen.add(kw_lower)
            unique_keywords.append(kw)
    
    return unique_keywords[:15]  # Limit to top 15


def _extract_spec_sections(content: str) -> list[str]:
    """Extract specification section references (CSI format)."""
    matches = SPEC_SECTION_PATTERN.findall(content)
    
    sections = []
    for match in matches:
        # match is a tuple from the alternation
        section = match[0] or match[1]
        if section:
            # Normalize format (remove "Section" prefix, standardize spacing)
            section = re.sub(r'Section\s*', '', section, flags=re.IGNORECASE)
            section = section.replace(' ', '')
            if len(section) >= 6 and section not in sections:
                sections.append(section)
    
    return sections[:5]  # Limit to 5 sections


def _extract_drawing_refs(content: str) -> list[str]:
    """Extract drawing references from the document."""
    matches = DRAWING_PATTERN.findall(content)
    
    drawings = []
    for match in matches:
        drawing = match[0] or match[1]
        if drawing and drawing not in drawings:
            drawings.append(drawing)
    
    return drawings[:10]  # Limit to 10 drawings
