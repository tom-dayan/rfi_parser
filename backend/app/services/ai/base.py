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

# Consultant types with their areas of expertise
CONSULTANT_MAPPING = {
    "structural": {
        "name": "LERA Consulting Structural Engineers",
        "keywords": ["rebar", "concrete", "footing", "foundation", "steel", "beam", "column", "slab", "structural", "reinforcement", "shear", "moment", "load", "bearing", "framing"],
        "prefix": "LERA"
    },
    "electrical": {
        "name": "CES Consulting Engineering Services",
        "keywords": ["electrical", "power", "lighting", "panel", "circuit", "conduit", "wire", "outlet", "switch", "receptacle", "transformer", "generator", "voltage"],
        "prefix": "CES"
    },
    "mechanical": {
        "name": "CES Consulting Engineering Services", 
        "keywords": ["hvac", "mechanical", "duct", "air handling", "chiller", "boiler", "fan", "diffuser", "thermostat", "ventilation", "exhaust"],
        "prefix": "CES"
    },
    "plumbing": {
        "name": "CES Consulting Engineering Services",
        "keywords": ["plumbing", "pipe", "drain", "water", "sanitary", "fixture", "valve", "pump", "sprinkler", "fire protection"],
        "prefix": "CES"
    },
    "lighting": {
        "name": "HLB Lighting Design",
        "keywords": ["lighting design", "fixture", "luminaire", "illumination", "dimming", "control system"],
        "prefix": "HLB"
    },
    "civil": {
        "name": "Civil Engineer",
        "keywords": ["site", "grading", "drainage", "stormwater", "utilities", "paving", "curb"],
        "prefix": "Civil"
    }
}


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
    suggested_followup: Optional[str] = None
    similar_rfis: Optional[list[str]] = None
    citations: Optional[list[dict]] = None


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

    def _detect_consultant_type(self, document_content: str) -> Optional[str]:
        """Detect which consultant should be referenced based on document content."""
        content_lower = document_content.lower()
        
        for consultant_type, info in CONSULTANT_MAPPING.items():
            keyword_matches = sum(1 for kw in info["keywords"] if kw in content_lower)
            if keyword_matches >= 2:  # At least 2 keyword matches
                return consultant_type
        return None

    def _build_rfi_prompt(self, document_content: str, spec_context: list[dict]) -> str:
        """Build prompt for RFI processing (informational response)."""

        # Detect consultant type from content
        detected_consultant = self._detect_consultant_type(document_content)
        consultant_guidance = ""
        if detected_consultant and detected_consultant in CONSULTANT_MAPPING:
            info = CONSULTANT_MAPPING[detected_consultant]
            consultant_guidance = f"\n**NOTE:** This RFI appears to be {detected_consultant}-related. You should defer to {info['name']} with 'Please refer to {info['prefix']} comments.'"

        # Build spec context with clear formatting
        spec_text = ""
        if spec_context:
            spec_entries = []
            for ctx in spec_context:
                source = ctx.get('source', 'Unknown')
                section = ctx.get('section', 'N/A')
                score = int(ctx.get('score', 0) * 100)
                text = ctx.get('text', '')[:2000]  # Limit each section
                spec_entries.append(f"### {source} (Section: {section}, Relevance: {score}%)\n{text}")
            spec_text = "\n\n".join(spec_entries)
        else:
            spec_text = "(No specification sections found - respond based on general architectural knowledge)"

        # Calculate confidence based on spec relevance
        avg_relevance = sum(ctx.get('score', 0) for ctx in spec_context) / len(spec_context) if spec_context else 0.3
        confidence = min(0.95, avg_relevance + 0.3)

        return f"""<role>
You are responding to a Request for Information (RFI) as OLI Architecture, PLLC - the Architect of Record for this project. Your responses represent the official position of the architecture firm.
</role>

<style_guide>
FORMAT:
- Always begin with "OLI Comments:" on its own line
- Use bullet points (starting with "-") for each comment
- Be concise and direct - architects value brevity over verbosity
- One clear thought per bullet point

CONTENT:
- Reference specific drawings by number (e.g., "per S-036", "refer to A-201")
- Reference spec sections when applicable (e.g., "Per Section 033000...")
- Acknowledge when something deviates from Contract Documents
- Request shop drawings or submittals when formal review is needed

CONSULTANT REFERRALS:
- For structural (rebar, concrete, steel, footings): "Please refer to LERA comments."
- For MEP (electrical, mechanical, plumbing): "Please refer to CES comments."
- For lighting design: "Please refer to HLB comments."
- Always include your own architectural comments even when deferring
{consultant_guidance}
</style_guide>

<examples>
EXAMPLE 1 - Structural RFI (Top Mat Rebar Spacing):
---
OLI Comments:
- Please refer to LERA comments.
- Increasing the top reinforcement cover to 2 inches will result in a potentially increased tendency for cracking due to greater concrete cover. The extent of additional cracking cannot be quantified.
- Acceptance of this condition differs from the Contract Documents and original design intent.
---

EXAMPLE 2 - Waterproofing RFI (Sika Footing Waterproofing):
---
OLI Comments:
- Please refer to LERA comments.
- Please provide shop drawings illustrating how the proposed system will interface at and around the footings, including transitions between the vertical and horizontal membranes.
- Shop drawings should clearly indicate membrane terminations and any required protection board.
---

EXAMPLE 3 - Finish RFI (Interior Paint):
---
OLI Comments:
- The proposed paint system is acceptable provided the manufacturer's recommended surface preparation is followed.
- Confirm all surfaces are primed per Section 099113 prior to finish coat application.
- Submit color samples for Architect's approval prior to proceeding.
---

EXAMPLE 4 - Door Hardware RFI:
---
OLI Comments:
- Refer to Door Schedule on A-601 for complete hardware requirements.
- The proposed substitution for the lockset at Door 101 is not acceptable as it does not meet the specified security rating.
- For acoustic doors, verify all hardware meets STC rating requirements per Section 087100.
---
</examples>

<rfi_document>
{document_content}
</rfi_document>

<specifications>
{spec_text}
</specifications>

<task>
Write an RFI response in OLI's exact style. Focus on:
1. Answering the contractor's specific question
2. Referencing relevant drawings/specs
3. Deferring to appropriate consultants when needed
4. Noting any deviations from Contract Documents

Return ONLY valid JSON in this exact format:
</task>

```json
{{
  "response_text": "OLI Comments:\\n- [Your response in bullet points...]",
  "consultant_type": null,
  "confidence": {confidence:.2f},
  "citations": [
    {{"source": "document name", "section": "section reference", "page": null}}
  ],
  "suggested_followup": "Optional: suggest if contractor should submit shop drawings, clarification, etc."
}}
```"""

    def _build_submittal_prompt(self, document_content: str, spec_context: list[dict]) -> str:
        """Build prompt for Submittal processing (review with status)."""

        # Detect consultant type from content
        detected_consultant = self._detect_consultant_type(document_content)
        consultant_guidance = ""
        if detected_consultant and detected_consultant in CONSULTANT_MAPPING:
            info = CONSULTANT_MAPPING[detected_consultant]
            consultant_guidance = f"\n**NOTE:** This submittal appears to be {detected_consultant}-related. Reference {info['name']} in your review."

        # Build spec context with clear formatting
        spec_text = ""
        if spec_context:
            spec_entries = []
            for ctx in spec_context:
                source = ctx.get('source', 'Unknown')
                section = ctx.get('section', 'N/A')
                score = int(ctx.get('score', 0) * 100)
                text = ctx.get('text', '')[:2000]
                spec_entries.append(f"### {source} (Section: {section}, Relevance: {score}%)\n{text}")
            spec_text = "\n\n".join(spec_entries)
        else:
            spec_text = "(No specification sections found - review based on general requirements)"

        # Calculate confidence
        avg_relevance = sum(ctx.get('score', 0) for ctx in spec_context) / len(spec_context) if spec_context else 0.3
        confidence = min(0.95, avg_relevance + 0.3)

        return f"""<role>
You are reviewing a submittal as OLI Architecture, PLLC - the Architect of Record. Your review represents the official position of the architecture firm and must follow AIA standard review practices.
</role>

<review_statuses>
Use EXACTLY one of these statuses:
- "no_exceptions" = REVIEWED - NO EXCEPTIONS TAKEN (submittal fully complies)
- "approved_as_noted" = FURNISH AS CORRECTED (minor issues, can proceed with noted corrections)
- "revise_and_resubmit" = REVISE AND RESUBMIT (significant issues, must resubmit before proceeding)
- "rejected" = REJECTED (does not comply, provide alternate)
- "see_comments" = SUBMIT SPECIFIC ITEM (incomplete or needs clarification)
</review_statuses>

<style_guide>
FORMAT:
- Begin with the review status stamp
- List specific comments with bullet points
- Reference spec sections (e.g., "Per Section 260553-1...")
- Always end with the standard disclaimer

CONTENT:
- Note specific deviations from specifications
- Identify missing information
- Reference relevant spec sections for each comment
- Keep comments actionable and specific
{consultant_guidance}

CONSULTANT INVOLVEMENT:
- For electrical/mechanical/plumbing: Note "CES Review" with separate comments
- For structural: Note "LERA Review" with separate comments
- For lighting: Note "HLB Review" with separate comments
</style_guide>

<examples>
EXAMPLE 1 - Electrical Submittal (No Exceptions):
---
Status: REVIEWED - NO EXCEPTIONS TAKEN

OLI Comments:
- Submittal reviewed for general conformance with Contract Documents.
- Please refer to CES comments for electrical review.

CES Review:
- Panel schedule reviewed per Section 260553.
- Equipment meets specified requirements.

This review is only for general conformance with the design concept of the project and general compliance with the information given in the Contract Documents.
---

EXAMPLE 2 - Door Hardware (Furnish as Corrected):
---
Status: FURNISH AS CORRECTED

OLI Comments:
- Hinge specification for Door Type A does not match Section 087100 requirement for heavy-duty hinges. Furnish heavy-duty hinges as specified.
- All other hardware acceptable as submitted.
- Contractor to maintain copy of approved submittal at job site.

This review is only for general conformance with the design concept of the project and general compliance with the information given in the Contract Documents.
---

EXAMPLE 3 - MEP Equipment (Revise and Resubmit):
---
Status: REVISE AND RESUBMIT

OLI Comments:
- Please refer to CES comments.

CES Review:
- Submitted unit capacity (15 tons) does not meet specified capacity (20 tons) per Section 238123.
- Electrical data sheet missing - provide complete electrical requirements.
- Sound power levels not indicated - verify compliance with NC-35 requirement.
- Resubmit with corrections noted above.

This review is only for general conformance with the design concept of the project and general compliance with the information given in the Contract Documents.
---
</examples>

<submittal_document>
{document_content}
</submittal_document>

<specifications>
{spec_text}
</specifications>

<task>
Review this submittal against the project specifications. Determine the appropriate status and provide specific comments. Always include the standard disclaimer.

Return ONLY valid JSON in this exact format:
</task>

```json
{{
  "status": "no_exceptions|approved_as_noted|revise_and_resubmit|rejected|see_comments",
  "response_text": "Status: [STATUS]\\n\\nOLI Comments:\\n- [Your comments...]\\n\\nThis review is only for general conformance with the design concept of the project and general compliance with the information given in the Contract Documents.",
  "consultant_type": null,
  "confidence": {confidence:.2f},
  "citations": [
    {{"source": "specification section", "section": "section number", "page": null}}
  ]
}}
```"""
