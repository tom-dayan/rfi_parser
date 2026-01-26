from anthropic import Anthropic
import json
from .ai_service import AIService, RFIAnalysis, SpecSection


class ClaudeService(AIService):
    """Claude API implementation of AI service (future integration)"""

    def __init__(self, api_key: str):
        self.client = Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

    async def analyze_rfi(
        self,
        rfi_content: str,
        specifications: list[SpecSection]
    ) -> RFIAnalysis:
        """
        Analyze RFI using Claude API

        Args:
            rfi_content: The full text content of the RFI
            specifications: List of relevant specification sections

        Returns:
            RFIAnalysis with status, reason, and references
        """
        prompt = self._build_prompt(rfi_content, specifications)

        try:
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=0.3,
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
            analysis_data = self._parse_response(response_text)

            # Create RFIAnalysis object
            return RFIAnalysis(**analysis_data)

        except Exception as e:
            # Fallback analysis if AI fails
            print(f"Claude analysis failed: {e}")
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
            # Try to extract JSON from response (Claude may wrap it in markdown)
            # Remove markdown code blocks if present
            text = response_text.strip()
            if text.startswith("```json"):
                text = text[7:]  # Remove ```json
            if text.startswith("```"):
                text = text[3:]  # Remove ```
            if text.endswith("```"):
                text = text[:-3]  # Remove ending ```

            text = text.strip()

            # Parse JSON
            data = json.loads(text)

            # Validate and normalize fields
            return {
                "status": data.get("status", "comment"),
                "consultant_type": data.get("consultant_type"),
                "reason": data.get("reason"),
                "spec_reference": data.get("spec_reference"),
                "spec_quote": data.get("spec_quote"),
                "confidence": float(data.get("confidence", 0.5))
            }

        except Exception as e:
            print(f"Failed to parse Claude response: {e}")
            # Fallback: use the raw text as reason
            return {
                "status": "comment",
                "consultant_type": None,
                "reason": response_text[:500],
                "spec_reference": None,
                "spec_quote": None,
                "confidence": 0.3
            }
