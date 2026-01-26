from abc import ABC, abstractmethod
from typing import Optional, Literal
from pydantic import BaseModel


class SpecSection(BaseModel):
    """A section of specification document"""
    title: str
    content: str


class RFIAnalysis(BaseModel):
    """Result of RFI analysis against specifications"""
    status: Literal["accepted", "rejected", "comment", "refer_to_consultant"]
    consultant_type: Optional[str] = None  # e.g., "structural", "electrical", "mechanical"
    reason: Optional[str] = None  # For rejected/comment
    spec_reference: Optional[str] = None  # Section number/title
    spec_quote: Optional[str] = None  # Relevant text from spec
    confidence: float = 0.0  # 0-1 confidence score


class AIService(ABC):
    """Abstract base class for AI services"""

    @abstractmethod
    async def analyze_rfi(
        self,
        rfi_content: str,
        specifications: list[SpecSection]
    ) -> RFIAnalysis:
        """
        Analyze an RFI against specifications

        Args:
            rfi_content: The full text content of the RFI
            specifications: List of relevant specification sections

        Returns:
            RFIAnalysis with status, reason, and references
        """
        pass

    def _build_prompt(self, rfi_content: str, specifications: list[SpecSection]) -> str:
        """Build the prompt for AI analysis"""

        spec_text = "\n\n".join([
            f"--- {spec.title} ---\n{spec.content}"
            for spec in specifications
        ])

        prompt = f"""You are analyzing a Request for Information (RFI) against architectural specifications.

RFI Content:
{rfi_content}

Relevant Specifications:
{spec_text}

Analyze the RFI and determine:
1. Status: Should it be "accepted", "rejected", "comment", or "refer_to_consultant"?
   - "accepted": The RFI request aligns with specifications
   - "rejected": The RFI request contradicts specifications
   - "comment": Need clarification or additional information
   - "refer_to_consultant": Requires expert consultation (specify which type)

2. If referring to consultant, specify type (structural, electrical, mechanical, plumbing, etc.)

3. Provide a clear reason for non-accepted RFIs

4. Reference the specific specification section that supports your decision

5. Quote the relevant text from the specification

Respond ONLY with valid JSON in this exact format:
{{
  "status": "accepted|rejected|comment|refer_to_consultant",
  "consultant_type": "structural|electrical|mechanical|etc or null",
  "reason": "explanation for rejection/comment or null",
  "spec_reference": "section title/number",
  "spec_quote": "relevant quote from specification",
  "confidence": 0.85
}}"""

        return prompt
