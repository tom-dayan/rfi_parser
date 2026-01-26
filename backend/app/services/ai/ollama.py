import json
import ollama
from .base import AIService, RFIAnalysis, SpecSection


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
                format='json',
                options={
                    'temperature': 0.3,
                }
            )

            # Extract response content
            response_text = response['message']['content']

            # Parse JSON response
            analysis_data = self._parse_response(response_text)

            return RFIAnalysis(**analysis_data)

        except Exception as e:
            print(f"Ollama analysis failed: {e}")
            return RFIAnalysis(
                status="comment",
                reason=f"AI analysis failed: {str(e)}. Please review manually.",
                confidence=0.0
            )

    def _parse_response(self, response_text: str) -> dict:
        """Parse AI response and extract structured data"""
        try:
            data = json.loads(response_text)
            return {
                "status": data.get("status", "comment"),
                "consultant_type": data.get("consultant_type"),
                "reason": data.get("reason"),
                "spec_reference": data.get("spec_reference"),
                "spec_quote": data.get("spec_quote"),
                "confidence": float(data.get("confidence", 0.5))
            }
        except json.JSONDecodeError:
            return self._extract_from_text(response_text)

    def _extract_from_text(self, text: str) -> dict:
        """Fallback: Extract analysis data from unstructured text"""
        text_lower = text.lower()

        status = "comment"
        if "accepted" in text_lower:
            status = "accepted"
        elif "rejected" in text_lower or "reject" in text_lower:
            status = "rejected"
        elif "consultant" in text_lower or "refer" in text_lower:
            status = "refer_to_consultant"

        consultant_type = None
        for keyword in ["structural", "electrical", "mechanical", "plumbing", "hvac", "civil"]:
            if keyword in text_lower:
                consultant_type = keyword
                break

        return {
            "status": status,
            "consultant_type": consultant_type,
            "reason": text[:500] if len(text) > 500 else text,
            "spec_reference": None,
            "spec_quote": None,
            "confidence": 0.3
        }

    def check_availability(self) -> bool:
        """Check if Ollama service is available"""
        try:
            models = self.client.list()
            model_names = [m['name'] for m in models.get('models', [])]
            return any(self.model in name for name in model_names)
        except Exception as e:
            print(f"Ollama availability check failed: {e}")
            return False
