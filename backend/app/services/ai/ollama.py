"""Ollama AI service implementation."""
import json
import logging
import ollama
from .base import AIService, DocumentResponse, DocumentType, RFIAnalysis, SpecSection

logger = logging.getLogger(__name__)


class OllamaService(AIService):
    """Ollama implementation of AI service for local LLM processing."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.client = ollama.Client(host=base_url)

    async def process_document(
        self,
        document_content: str,
        document_type: DocumentType,
        spec_context: list[dict]
    ) -> DocumentResponse:
        """
        Process a document (RFI or Submittal) using Ollama.

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
            # Call Ollama API
            response = self.client.chat(
                model=self.model,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                format='json',
                options={
                    'temperature': 0.3,
                }
            )

            # Extract response content
            response_text = response['message']['content']

            # Parse JSON response
            data = self._parse_response(response_text, document_type)

            return DocumentResponse(
                response_text=data.get("response_text", ""),
                status=data.get("status") if document_type == "submittal" else None,
                consultant_type=data.get("consultant_type"),
                confidence=float(data.get("confidence", 0.5))
            )

        except Exception as e:
            logger.error(f"Ollama processing failed: {e}")
            return DocumentResponse(
                response_text=f"AI processing failed: {str(e)}. Please review manually.",
                status="see_comments" if document_type == "submittal" else None,
                confidence=0.0
            )

    def _parse_response(self, response_text: str, document_type: DocumentType) -> dict:
        """Parse AI response and extract structured data."""
        try:
            data = json.loads(response_text)

            result = {
                "response_text": data.get("response_text", ""),
                "consultant_type": data.get("consultant_type"),
                "confidence": float(data.get("confidence", 0.5))
            }

            if document_type == "submittal":
                status = data.get("status", "see_comments")
                # Validate status
                valid_statuses = ["no_exceptions", "approved_as_noted", "revise_and_resubmit", "rejected", "see_comments"]
                if status not in valid_statuses:
                    status = "see_comments"
                result["status"] = status

            return result

        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response, extracting from text")
            return self._extract_from_text(response_text, document_type)

    def _extract_from_text(self, text: str, document_type: DocumentType) -> dict:
        """Fallback: Extract data from unstructured text."""
        text_lower = text.lower()

        result = {
            "response_text": text[:2000] if len(text) > 2000 else text,
            "consultant_type": None,
            "confidence": 0.3
        }

        # Try to detect consultant type
        for keyword in ["structural", "electrical", "mechanical", "plumbing", "hvac", "civil", "fire"]:
            if keyword in text_lower:
                result["consultant_type"] = keyword
                break

        if document_type == "submittal":
            # Try to detect status
            status = "see_comments"
            if "no exception" in text_lower or "approved" in text_lower and "noted" not in text_lower:
                status = "no_exceptions"
            elif "approved as noted" in text_lower:
                status = "approved_as_noted"
            elif "revise" in text_lower or "resubmit" in text_lower:
                status = "revise_and_resubmit"
            elif "reject" in text_lower:
                status = "rejected"
            result["status"] = status

        return result

    # Keep legacy method
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

    def check_availability(self) -> bool:
        """Check if Ollama service is available."""
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            return any(self.model in name for name in model_names)
        except Exception as e:
            logger.error(f"Ollama availability check failed: {e}")
            return False
