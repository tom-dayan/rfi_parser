import json
from typing import Optional
import anthropic
from .base import AIService, RFIAnalysis, SpecSection


class ClaudeService(AIService):
    """Claude API implementation of AI service with vision support"""

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
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
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

            return RFIAnalysis(**analysis_data)

        except anthropic.APIError as e:
            print(f"Claude API error: {e}")
            return RFIAnalysis(
                status="comment",
                reason=f"Claude API error: {str(e)}. Please check your API key and try again.",
                confidence=0.0
            )
        except Exception as e:
            print(f"Claude analysis failed: {e}")
            return RFIAnalysis(
                status="comment",
                reason=f"AI analysis failed: {str(e)}. Please review manually.",
                confidence=0.0
            )

    async def analyze_rfi_with_images(
        self,
        rfi_content: str,
        specifications: list[SpecSection],
        images: list[tuple[bytes, str]]  # List of (image_bytes, media_type)
    ) -> RFIAnalysis:
        """
        Analyze RFI with image support (for drawings)

        Args:
            rfi_content: The full text content of the RFI
            specifications: List of relevant specification sections
            images: List of (image_bytes, media_type) tuples

        Returns:
            RFIAnalysis with status, reason, and references
        """
        if not self.enable_vision or not images:
            return await self.analyze_rfi(rfi_content, specifications)

        prompt = self._build_prompt(rfi_content, specifications)

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

        # Add text prompt
        content.append({
            "type": "text",
            "text": prompt + "\n\nPlease also consider the attached drawings/images in your analysis."
        })

        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": content
                    }
                ]
            )

            response_text = message.content[0].text
            analysis_data = self._parse_response(response_text)

            return RFIAnalysis(**analysis_data)

        except Exception as e:
            print(f"Claude vision analysis failed: {e}")
            # Fall back to text-only analysis
            return await self.analyze_rfi(rfi_content, specifications)

    def _parse_response(self, response_text: str) -> dict:
        """Parse AI response and extract structured data"""
        # Try to extract JSON from response
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
            return {
                "status": data.get("status", "comment"),
                "consultant_type": data.get("consultant_type"),
                "reason": data.get("reason"),
                "spec_reference": data.get("spec_reference"),
                "spec_quote": data.get("spec_quote"),
                "confidence": float(data.get("confidence", 0.5))
            }
        except (json.JSONDecodeError, ValueError):
            return self._extract_from_text(response_text)

    def _extract_from_text(self, text: str) -> dict:
        """Fallback: Extract analysis data from unstructured text"""
        text_lower = text.lower()

        status = "comment"
        if "accepted" in text_lower and "not accepted" not in text_lower:
            status = "accepted"
        elif "rejected" in text_lower or "reject" in text_lower:
            status = "rejected"
        elif "consultant" in text_lower or "refer" in text_lower:
            status = "refer_to_consultant"

        consultant_type = None
        for keyword in ["structural", "electrical", "mechanical", "plumbing", "hvac", "civil", "fire"]:
            if keyword in text_lower:
                consultant_type = keyword
                break

        return {
            "status": status,
            "consultant_type": consultant_type,
            "reason": text[:500] if len(text) > 500 else text,
            "spec_reference": None,
            "spec_quote": None,
            "confidence": 0.4
        }
