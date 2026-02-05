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

        return f"""You are responding to an RFI as OLI Architecture, PLLC (the Architect of Record). Write responses in OLI's professional style.

## OLI RESPONSE STYLE GUIDE:
- Begin with "OLI Comments:" followed by bullet points
- Be concise and direct - no fluff or pleasantries
- Reference specific drawings, spec sections, and consultants by name
- For structural matters (rebar, concrete, footings), defer to LERA with "Please refer to LERA comments"
- For MEP matters, defer to CES with "Please refer to CES comments"  
- Request shop drawings or submittals when needed for formal approval
- Note any deviations from Contract Documents

## EXAMPLE RFI RESPONSES (match this tone):

**Example 1 - Structural RFI:**
OLI Comments:
- Please refer to LERA comments.
- Increasing the top reinforcement cover to 2 inches will result in a potentially increased tendency for cracking due to greater concrete cover. The extent of additional cracking cannot be quantified. Acceptance of this condition differs from the Contract Documents and original design intent.

**Example 2 - Waterproofing RFI:**
OLI Comments:
- Please refer to LERA comments.
- Please provide shop drawings illustrating how the proposed system will interface at and around the footings, including transitions between the vertical and horizontal membranes.

## RFI DOCUMENT:
{document_content}

## PROJECT SPECIFICATIONS:
{spec_text}

## YOUR TASK:
Write an RFI response in OLI's style. Focus on the contractor's specific question.

### Response Format (JSON only):
{{
  "response_text": "OLI Comments:\\n- [Your bullet-pointed response...]",
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

        return f"""You are reviewing a submittal as OLI Architecture, PLLC (the Architect of Record). Use OLI's professional review format.

## OLI SUBMITTAL REVIEW STYLE:
- Use standard AIA-style review stamps/statuses
- Keep comments brief and specific
- Reference spec section numbers (e.g., "Per Section 260553...")
- For electrical submittals, CES is the MEP consultant
- For structural submittals, LERA is the structural engineer
- Include the standard disclaimer about general conformance review

## STATUS OPTIONS (use exact wording):
- "no_exceptions" = "Reviewed/No Exceptions Taken"
- "approved_as_noted" = "Furnish as Corrected" 
- "revise_and_resubmit" = "Revise and Resubmit"
- "rejected" = "Rejected"
- "see_comments" = "Submit Specific Item" or needs clarification

## STANDARD DISCLAIMER (include at end of all reviews):
"This review is only for general conformance with the design concept of the project and general compliance with the information given in the Contract Documents."

## SUBMITTAL DOCUMENT:
{document_content}

## PROJECT SPECIFICATIONS:
{spec_text}

## YOUR TASK:
Review this submittal against the specifications. Be concise and professional.

### Response Format (JSON only):
{{
  "status": "no_exceptions|approved_as_noted|revise_and_resubmit|rejected|see_comments",
  "response_text": "Your review comments...\\n\\nThis review is only for general conformance with the design concept of the project and general compliance with the information given in the Contract Documents.",
  "consultant_type": null or "structural|electrical|mechanical|plumbing|civil|fire_protection|other",
  "confidence": {min(0.95, avg_relevance + 0.3):.2f}
}}"""
