"""Base classes for AI services."""
from abc import ABC, abstractmethod
from typing import Optional, Literal
from pydantic import BaseModel


# Document types
DocumentType = Literal["rfi", "submittal"]

# Submittal statuses
SubmittalStatus = Literal[
    "no_exceptions",
    "approved_as_noted",
    "revise_and_resubmit",
    "rejected",
    "see_comments"
]


class SpecContext(BaseModel):
    """A specification context retrieved via RAG."""
    text: str
    source: str
    source_file_id: Optional[int] = None
    section: Optional[str] = None
    score: float = 0.0


class DocumentResponse(BaseModel):
    """Response from processing a document (RFI or Submittal)."""
    response_text: str
    status: Optional[SubmittalStatus] = None  # Only for submittals
    consultant_type: Optional[str] = None
    confidence: float = 0.0


# Legacy classes for backwards compatibility
class SpecSection(BaseModel):
    """A section of specification document."""
    title: str
    content: str


class RFIAnalysis(BaseModel):
    """Result of RFI analysis (legacy)."""
    status: Literal["accepted", "rejected", "comment", "refer_to_consultant"]
    consultant_type: Optional[str] = None
    reason: Optional[str] = None
    spec_reference: Optional[str] = None
    spec_quote: Optional[str] = None
    confidence: float = 0.0


class AIService(ABC):
    """Abstract base class for AI services."""

    @abstractmethod
    async def process_document(
        self,
        document_content: str,
        document_type: DocumentType,
        spec_context: list[dict]
    ) -> DocumentResponse:
        """
        Process a document (RFI or Submittal) against specifications.

        Args:
            document_content: The text content of the document
            document_type: Either "rfi" or "submittal"
            spec_context: List of relevant spec sections from RAG retrieval

        Returns:
            DocumentResponse with response text and status (for submittals)
        """
        pass

    # Legacy method for backwards compatibility
    async def analyze_rfi(
        self,
        rfi_content: str,
        specifications: list[SpecSection]
    ) -> RFIAnalysis:
        """Legacy method - use process_document instead."""
        spec_context = [
            {"text": s.content, "source": s.title, "section": s.title, "score": 1.0}
            for s in specifications
        ]
        response = await self.process_document(
            document_content=rfi_content,
            document_type="rfi",
            spec_context=spec_context
        )
        return RFIAnalysis(
            status="comment",
            reason=response.response_text,
            consultant_type=response.consultant_type,
            confidence=response.confidence
        )

    def _build_rfi_prompt(self, document_content: str, spec_context: list[dict]) -> str:
        """Build prompt for RFI processing (informational response)."""

        # Include relevance scores so AI knows how reliable each reference is
        spec_text = "\n\n".join([
            f"--- Source: {ctx.get('source', 'Unknown')} | Section: {ctx.get('section', 'N/A')} | Relevance: {int(ctx.get('score', 0) * 100)}% ---\n{ctx.get('text', '')}"
            for ctx in spec_context
        ])

        # Calculate average relevance to inform confidence
        avg_relevance = sum(ctx.get('score', 0) for ctx in spec_context) / len(spec_context) if spec_context else 0

        return f"""You are an expert construction document reviewer for an architecture firm (the Architect of Record), responding to a Request for Information (RFI) from a general contractor.

## RFI DOCUMENT:
{document_content}

## PROJECT SPECIFICATIONS (retrieved for this RFI):
These are specification sections that may be relevant. Higher relevance % = more applicable.
Average relevance: {int(avg_relevance * 100)}%

{spec_text}

## YOUR TASK:
Write a professional RFI response. Focus on the CORE QUESTION section if present.

### Response Requirements:
1. **DIRECTLY ANSWER THE QUESTION** - Address the specific issue raised
2. **CITE SPECIFICATIONS** - Reference spec section numbers (e.g., "Per Section 033000...")
3. **BE ACTIONABLE** - Tell the contractor exactly what to do next
4. **REQUEST CLARIFICATION IF NEEDED** - Ask for shop drawings, submittals, or additional info

### Response Structure:
- Start with your answer or recommendation
- Reference applicable specification sections
- List any required submittals, shop drawings, or approvals
- Note if consultant review is required (structural, MEP, etc.)

### CRITICAL RULES:
- NO placeholder text ([Name], [Date], etc.) - write the actual response
- NO salutations or sign-offs - just technical content
- If specs don't address the question, say so and recommend consulting the appropriate discipline
- For structural questions (rebar, concrete, footings), recommend LERA/structural engineer review
- For MEP questions, recommend MEP consultant review

## Response Format (JSON only):
{{
  "response_text": "Your complete technical response...",
  "consultant_type": null or "structural|electrical|mechanical|plumbing|civil|fire_protection|other",
  "confidence": {min(0.95, avg_relevance + 0.3):.2f}
}}"""

    def _build_submittal_prompt(self, document_content: str, spec_context: list[dict]) -> str:
        """Build prompt for Submittal processing (review with status)."""

        # Include relevance scores so AI knows how reliable each reference is
        spec_text = "\n\n".join([
            f"--- Source: {ctx.get('source', 'Unknown')} | Section: {ctx.get('section', 'N/A')} | Relevance: {int(ctx.get('score', 0) * 100)}% ---\n{ctx.get('text', '')}"
            for ctx in spec_context
        ])

        # Calculate average relevance to inform confidence
        avg_relevance = sum(ctx.get('score', 0) for ctx in spec_context) / len(spec_context) if spec_context else 0

        return f"""You are an expert construction document reviewer for an architecture firm (the Architect of Record), reviewing a product/material submittal from a contractor.

## SUBMITTAL DOCUMENT:
{document_content}

## PROJECT SPECIFICATIONS (retrieved for this submittal):
These are specification sections that may be relevant. Higher relevance % = more applicable.
Average relevance: {int(avg_relevance * 100)}%

{spec_text}

## YOUR TASK:
Review this submittal against project specifications and provide a formal review.

### Status Options:
- **no_exceptions**: Fully complies with specs, approved as submitted
- **approved_as_noted**: Acceptable with minor notes/clarifications
- **revise_and_resubmit**: Does not meet specs, must be revised (explain what's wrong)
- **rejected**: Fundamentally non-compliant (explain why)
- **see_comments**: Needs clarification or additional information

### Review Comment Requirements:
1. **Compliance Check** - Does the product meet specified requirements?
2. **Cite Specifications** - Reference spec sections (e.g., "Per Section 265113...")
3. **List Issues** - Specific items that don't comply (if any)
4. **Corrections Required** - What needs to be changed for approval

### CRITICAL RULES:
- NO placeholder text - write actual review comments
- Be specific about what complies and what doesn't
- For electrical submittals, verify against Division 26 specs
- For structural/MEP items, note if consultant review is required
- If specs don't cover this item, note it and recommend "see_comments"

## Response Format (JSON only):
{{
  "status": "no_exceptions|approved_as_noted|revise_and_resubmit|rejected|see_comments",
  "response_text": "Your complete review comments...",
  "consultant_type": null or "structural|electrical|mechanical|plumbing|civil|fire_protection|other",
  "confidence": {min(0.95, avg_relevance + 0.3):.2f}
}}"""
