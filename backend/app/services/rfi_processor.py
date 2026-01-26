from sqlalchemy.orm import Session
from typing import Optional
from ..models import RFI, Specification, RFIResult
from ..schemas import RFIResultCreate
from .ai_service import AIService, SpecSection
from .document_parser import DocumentParser


class RFIProcessor:
    """Orchestrates RFI processing using AI service"""

    def __init__(self, ai_service: AIService):
        self.ai_service = ai_service

    async def process_rfi(
        self,
        rfi: RFI,
        specification: Specification,
        db: Session
    ) -> RFIResult:
        """
        Process a single RFI against a specification

        Args:
            rfi: RFI database object
            specification: Specification database object
            db: Database session

        Returns:
            RFIResult database object
        """
        # Extract specification sections
        spec_sections = self._extract_spec_sections(specification)

        # Analyze RFI using AI
        analysis = await self.ai_service.analyze_rfi(
            rfi_content=rfi.content,
            specifications=spec_sections
        )

        # Create result record
        result_data = RFIResultCreate(
            rfi_id=rfi.id,
            spec_id=specification.id,
            status=analysis.status,
            consultant_type=analysis.consultant_type,
            reason=analysis.reason,
            spec_reference=analysis.spec_reference,
            spec_quote=analysis.spec_quote,
            confidence=analysis.confidence
        )

        # Save to database
        db_result = RFIResult(**result_data.model_dump())
        db.add(db_result)
        db.commit()
        db.refresh(db_result)

        return db_result

    async def process_all_rfis(
        self,
        rfi_ids: Optional[list[int]],
        spec_ids: Optional[list[int]],
        db: Session
    ) -> list[RFIResult]:
        """
        Process multiple RFIs against specifications

        Args:
            rfi_ids: Optional list of RFI IDs to process (None = all)
            spec_ids: Optional list of Spec IDs to use (None = all)
            db: Database session

        Returns:
            List of RFIResult objects
        """
        # Get RFIs to process
        if rfi_ids:
            rfis = db.query(RFI).filter(RFI.id.in_(rfi_ids)).all()
        else:
            rfis = db.query(RFI).all()

        # Get specifications to use
        if spec_ids:
            specs = db.query(Specification).filter(Specification.id.in_(spec_ids)).all()
        else:
            specs = db.query(Specification).all()

        if not rfis:
            raise ValueError("No RFIs found to process")

        if not specs:
            raise ValueError("No specifications found")

        results = []

        # Process each RFI against each specification
        # In a real system, you might want to match RFIs to relevant specs more intelligently
        for rfi in rfis:
            for spec in specs:
                # Check if already processed
                existing = db.query(RFIResult).filter(
                    RFIResult.rfi_id == rfi.id,
                    RFIResult.spec_id == spec.id
                ).first()

                if existing:
                    # Update existing result
                    results.append(existing)
                    continue

                # Process new RFI
                result = await self.process_rfi(rfi, spec, db)
                results.append(result)

        return results

    def _extract_spec_sections(self, specification: Specification) -> list[SpecSection]:
        """
        Extract sections from specification

        Args:
            specification: Specification database object

        Returns:
            List of SpecSection objects
        """
        sections = []

        # Use pre-parsed sections if available
        if specification.parsed_sections:
            for title, content in specification.parsed_sections.items():
                sections.append(SpecSection(title=title, content=content))
        else:
            # Parse sections on the fly
            parsed = DocumentParser.extract_sections(specification.content)
            for title, content in parsed.items():
                sections.append(SpecSection(title=title, content=content))

        # If no sections found, use entire content as single section
        if not sections:
            sections.append(SpecSection(
                title=specification.filename,
                content=specification.content
            ))

        return sections
