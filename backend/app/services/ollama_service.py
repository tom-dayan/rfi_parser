import json
import ollama
from typing import Optional
from .ai_service import AIService, RFIAnalysis, SpecSection


class OllamaService(AIService):
    """Ollama implementation of AI service for local LLM processing"""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3.2"):
        self.base_url = base_url
        self.model = model
        self.client = ollama.Client(host=base_url)

    async def analyze_rfi(
        self,
        rfi_content: str,
        specifications: list[SpecSection]
    ) -> RFIAnalysis:
        """
        Analyze RFI using Ollama local LLM

        Args:
            rfi_content: The full text content of the RFI
            specifications: List of relevant specification sections

        Returns:
            RFIAnalysis with status, reason, and references
        """
        prompt = self._build_prompt(rfi_content, specifications)

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
                format='json',  # Request JSON response
                options={
                    'temperature': 0.3,  # Lower temperature for more consistent results
                }
            )

            # Extract response content
            response_text = response['message']['content']

            # Parse JSON response
            analysis_data = self._parse_response(response_text)

            # Create RFIAnalysis object
            return RFIAnalysis(**analysis_data)

        except Exception as e:
            # Fallback analysis if AI fails
            print(f"Ollama analysis failed: {e}")
            return RFIAnalysis(
                status="comment",
                reason=f"AI analysis failed: {str(e)}. Please review manually.",
                confidence=0.0
            )

    def _parse_response(self, response_text: str) -> dict:
        """
        Parse AI response and extract structured data

        Args:
            response_text: Raw response from AI

        Returns:
            Dictionary of analysis data
        """
        try:
            # Try to parse as JSON
            data = json.loads(response_text)

            # Validate and normalize fields
            return {
                "status": data.get("status", "comment"),
                "consultant_type": data.get("consultant_type"),
                "reason": data.get("reason"),
                "spec_reference": data.get("spec_reference"),
                "spec_quote": data.get("spec_quote"),
                "confidence": float(data.get("confidence", 0.5))
            }

        except json.JSONDecodeError:
            # If JSON parsing fails, try to extract info from text
            return self._extract_from_text(response_text)

    def _extract_from_text(self, text: str) -> dict:
        """
        Fallback: Extract analysis data from unstructured text

        Args:
            text: Raw text response

        Returns:
            Dictionary of analysis data
        """
        text_lower = text.lower()

        # Determine status from keywords
        status = "comment"
        if "accepted" in text_lower:
            status = "accepted"
        elif "rejected" in text_lower or "reject" in text_lower:
            status = "rejected"
        elif "consultant" in text_lower or "refer" in text_lower:
            status = "refer_to_consultant"

        # Try to extract consultant type
        consultant_type = None
        consultant_keywords = ["structural", "electrical", "mechanical", "plumbing", "hvac"]
        for keyword in consultant_keywords:
            if keyword in text_lower:
                consultant_type = keyword
                break

        return {
            "status": status,
            "consultant_type": consultant_type,
            "reason": text[:500] if len(text) > 500 else text,  # First 500 chars as reason
            "spec_reference": None,
            "spec_quote": None,
            "confidence": 0.3  # Low confidence for fallback parsing
        }

    def check_availability(self) -> bool:
        """
        Check if Ollama service is available

        Returns:
            True if Ollama is running and model is available
        """
        try:
            # Try to list models
            models = self.client.list()
            # Check if our model is available
            model_names = [m['name'] for m in models.get('models', [])]
            return any(self.model in name for name in model_names)
        except Exception as e:
            print(f"Ollama availability check failed: {e}")
            return False
