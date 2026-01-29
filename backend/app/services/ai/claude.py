"""Claude API AI service implementation."""
import json
import logging
import anthropic
from .base import AIService, DocumentResponse, DocumentType, RFIAnalysis, SpecSection

logger = logging.getLogger(__name__)


class ClaudeService(AIService):
    """Claude API implementation of AI service with vision support."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        enable_vision: bool = False
    ):
        self.api_key = api_key
        self.model = model
        self.enable_vision = enable_vision
        self.client = anthropic.Anthropic(api_key=api_key)

    async def process_document(
        self,
        document_content: str,
        document_type: DocumentType,
        spec_context: list[dict]
    ) -> DocumentResponse:
        """
        Process a document (RFI or Submittal) using Claude API.

        Args:
            document_content: The text content of the document
            document_type: Either "rfi" or "submittal"
            spec_context: List of relevant spec sections from RAG retrieval

        Returns:
            DocumentResponse with response text and status (for submittals)
        """
        # Build appropriate prompt based on document type
        if document_type == "rfi":
            prompt = self._build_rfi_prompt(document_content, spec_context)
        else:
            prompt = self._build_submittal_prompt(document_content, spec_context)

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Extract response content
            response_text = message.content[0].text

            # Parse JSON response
            data = self._parse_document_response(response_text, document_type)

            return DocumentResponse(
                response_text=data.get("response_text", ""),
                status=data.get("status") if document_type == "submittal" else None,
                consultant_type=data.get("consultant_type"),
                confidence=float(data.get("confidence", 0.5))
            )

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return DocumentResponse(
                response_text=f"Claude API error: {str(e)}. Please check your API key and try again.",
                status="see_comments" if document_type == "submittal" else None,
                confidence=0.0
            )
        except Exception as e:
            logger.error(f"Claude processing failed: {e}")
            return DocumentResponse(
                response_text=f"AI processing failed: {str(e)}. Please review manually.",
                status="see_comments" if document_type == "submittal" else None,
                confidence=0.0
            )

    def _parse_document_response(self, response_text: str, document_type: DocumentType) -> dict:
        """Parse AI response for document processing."""
        try:
            # Handle case where response might have markdown code blocks
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.index("```") + 3
                end = response_text.index("```", start)
                response_text = response_text[start:end].strip()

            data = json.loads(response_text)

            result = {
                "response_text": data.get("response_text", ""),
                "consultant_type": data.get("consultant_type"),
                "confidence": float(data.get("confidence", 0.5))
            }

            if document_type == "submittal":
                status = data.get("status", "see_comments")
                valid_statuses = ["no_exceptions", "approved_as_noted", "revise_and_resubmit", "rejected", "see_comments"]
                if status not in valid_statuses:
                    status = "see_comments"
                result["status"] = status

            return result

        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse JSON response, extracting from text")
            return self._extract_from_text_document(response_text, document_type)

    def _extract_from_text_document(self, text: str, document_type: DocumentType) -> dict:
        """Fallback: Extract data from unstructured text for document processing."""
        text_lower = text.lower()

        result = {
            "response_text": text[:2000] if len(text) > 2000 else text,
            "consultant_type": None,
            "confidence": 0.4
        }

        # Try to detect consultant type
        for keyword in ["structural", "electrical", "mechanical", "plumbing", "hvac", "civil", "fire"]:
            if keyword in text_lower:
                result["consultant_type"] = keyword
                break

        if document_type == "submittal":
            status = "see_comments"
            if "no exception" in text_lower or ("approved" in text_lower and "noted" not in text_lower):
                status = "no_exceptions"
            elif "approved as noted" in text_lower:
                status = "approved_as_noted"
            elif "revise" in text_lower or "resubmit" in text_lower:
                status = "revise_and_resubmit"
            elif "reject" in text_lower:
                status = "rejected"
            result["status"] = status

        return result

    # Keep legacy method for backwards compatibility
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

    async def analyze_rfi_with_images(
        self,
        rfi_content: str,
        specifications: list[SpecSection],
        images: list[tuple[bytes, str]]
    ) -> RFIAnalysis:
        """
        Analyze RFI with image support (for drawings).

        Args:
            rfi_content: The full text content of the RFI
            specifications: List of relevant specification sections
            images: List of (image_bytes, media_type) tuples

        Returns:
            RFIAnalysis with status, reason, and references
        """
        if not self.enable_vision or not images:
            return await self.analyze_rfi(rfi_content, specifications)

        # Build legacy prompt
        spec_text = "\n\n".join([
            f"--- {spec.title} ---\n{spec.content}"
            for spec in specifications
        ])

        prompt = f"""You are an expert architectural consultant analyzing a Request for Information (RFI).

## RFI Content:
{rfi_content}

## Project Specifications:
{spec_text}

Please analyze the RFI and attached drawings/images. Provide a response in JSON format."""

        # Build content with images
        content = []

        # Add images first
        for image_bytes, media_type in images:
            import base64
            image_data = base64.standard_b64encode(image_bytes).decode('utf-8')
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data
                }
            })

        content.append({
            "type": "text",
            "text": prompt
        })

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )

            response_text = message.content[0].text
            analysis_data = self._parse_legacy_response(response_text)

            return RFIAnalysis(**analysis_data)

        except Exception as e:
            logger.error(f"Claude vision analysis failed: {e}")
            return await self.analyze_rfi(rfi_content, specifications)

    def _parse_legacy_response(self, response_text: str) -> dict:
        """Parse legacy AI response format."""
        try:
            if "```json" in response_text:
                start = response_text.index("```json") + 7
                end = response_text.index("```", start)
                response_text = response_text[start:end].strip()
            elif "```" in response_text:
                start = response_text.index("```") + 3
                end = response_text.index("```", start)
                response_text = response_text[start:end].strip()

            data = json.loads(response_text)
            return {
                "status": data.get("status", "comment"),
                "consultant_type": data.get("consultant_type"),
                "reason": data.get("reason"),
                "spec_reference": data.get("spec_reference"),
                "spec_quote": data.get("spec_quote"),
                "confidence": float(data.get("confidence", 0.5))
            }
        except (json.JSONDecodeError, ValueError):
            return {
                "status": "comment",
                "consultant_type": None,
                "reason": response_text[:500],
                "spec_reference": None,
                "spec_quote": None,
                "confidence": 0.3
            }
