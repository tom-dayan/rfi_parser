"""Google Gemini AI service implementation."""
import asyncio
import json
import logging
import re
from google import genai
from google.genai import types
from .base import AIService, DocumentResponse, DocumentType, RFIAnalysis, SpecSection

logger = logging.getLogger(__name__)


class GeminiService(AIService):
    """Google Gemini implementation of AI service."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash-lite"):
        self.client = genai.Client(api_key=api_key)
        # Ensure model name has the "models/" prefix required by the API
        self.model_name = model if model.startswith("models/") else f"models/{model}"
        self.max_retries = 3
        self.base_delay = 15  # seconds

    async def process_document(
        self,
        document_content: str,
        document_type: DocumentType,
        spec_context: list[dict]
    ) -> DocumentResponse:
        """
        Process a document (RFI or Submittal) using Google Gemini.

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

        last_error = None
        for attempt in range(self.max_retries):
            try:
                # Call Gemini API using the new google-genai package
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.3,
                        top_p=0.95,
                        response_mime_type="application/json",
                    )
                )
                response_text = response.text

                # Parse JSON response
                data = self._parse_response(response_text, document_type)

                return DocumentResponse(
                    response_text=data.get("response_text", ""),
                    status=data.get("status") if document_type == "submittal" else None,
                    consultant_type=data.get("consultant_type"),
                    confidence=float(data.get("confidence", 0.5))
                )

            except Exception as e:
                last_error = e
                error_str = str(e)
                
                # Check if it's a rate limit error (429)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    # Extract retry delay from error if available
                    retry_match = re.search(r'retry in (\d+)', error_str.lower())
                    delay = int(retry_match.group(1)) + 2 if retry_match else self.base_delay * (attempt + 1)
                    
                    logger.warning(f"Rate limited, waiting {delay}s before retry {attempt + 1}/{self.max_retries}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    # Non-rate-limit error, don't retry
                    logger.error(f"Gemini processing failed: {e}")
                    break

        return DocumentResponse(
            response_text=f"AI processing failed after {self.max_retries} attempts: {str(last_error)}. Please review manually.",
            status="see_comments" if document_type == "submittal" else None,
            confidence=0.0
        )

    def _parse_response(self, response_text: str, document_type: DocumentType) -> dict:
        """Parse AI response and extract structured data."""
        try:
            # Clean up response if needed (remove markdown code blocks)
            cleaned = response_text.strip()
            if cleaned.startswith("```json"):
                cleaned = cleaned[7:]
            if cleaned.startswith("```"):
                cleaned = cleaned[3:]
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

            data = json.loads(cleaned)

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

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON response: {e}")
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
        """Check if Gemini service is available."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents="Say 'ok'",
            )
            return bool(response.text)
        except Exception as e:
            logger.error(f"Gemini availability check failed: {e}")
            return False
