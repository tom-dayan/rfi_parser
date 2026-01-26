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

        prompt = f"""You are an expert architectural consultant analyzing a Request for Information (RFI) against project specifications.

## RFI Content:
{rfi_content}

## Project Specifications:
{spec_text}

## Your Task:
Analyze the RFI against the specifications and determine:

1. **Status**: What is the appropriate response?
   - "accepted": The RFI request is valid and aligns with specifications
   - "rejected": The RFI request contradicts or is not supported by specifications
   - "comment": The RFI needs clarification or additional information
   - "refer_to_consultant": Requires expert consultation (specify which discipline)

2. **Consultant Type** (if referring): Which consultant should review this?
   - structural, electrical, mechanical, plumbing, civil, landscape, fire_protection, acoustics, lighting, other

3. **Reason**: Provide a clear explanation for your decision

4. **Spec Reference**: Which specification section is most relevant?

5. **Quote**: Include the relevant quote from specifications that supports your decision

## Response Format:
Respond ONLY with valid JSON in this exact format (no markdown, no explanation):
{{
  "status": "accepted|rejected|comment|refer_to_consultant",
  "consultant_type": "consultant type or null",
  "reason": "clear explanation of decision",
  "spec_reference": "specification section/filename",
  "spec_quote": "relevant quote from specifications",
  "confidence": 0.85
}}"""

        return prompt
