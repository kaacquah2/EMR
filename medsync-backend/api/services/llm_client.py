import json
import logging
from decouple import config

logger = logging.getLogger(__name__)

# Switch this in .env:
# LLM_MODE=mock       ← development (free)
# LLM_MODE=bedrock    ← demo / production (costs money)
LLM_MODE = config("LLM_MODE", default="mock")


class MockLLMClient:
    """
    Zero-cost mock for development.
    Returns realistic fake responses so UI works perfectly.
    """

    def invoke(self, prompt: str, system: str = None, **kwargs) -> str:
        return "Mock response: LLM_MODE=mock is active. Switch to bedrock for real responses."

    def invoke_json(self, prompt: str, system: str = None, **kwargs) -> dict:
        """
        Return realistic fake data matching clinical schemas.
        """
        # Lowercase for easier matching
        prompt_lower = prompt.lower()
        
        if "differential" in prompt_lower:
            return {
                "differentials": [
                    {
                        "rank": 1,
                        "diagnosis": "Community-acquired pneumonia",
                        "icd10_code": "J18.9",
                        "probability": "high",
                        "supporting_factors": [
                            "Fever > 38.5°C",
                            "Productive cough",
                            "Elevated respiratory rate"
                        ],
                        "suggested_investigations": [
                            "Chest X-ray",
                            "Full blood count",
                            "Blood cultures x2"
                        ],
                        "red_flags": ["SpO2 < 92%", "Confusion"]
                    },
                    {
                        "rank": 2,
                        "diagnosis": "Pulmonary tuberculosis",
                        "icd10_code": "A15.0",
                        "probability": "medium",
                        "supporting_factors": [
                            "Endemic region",
                            "Weight loss history"
                        ],
                        "suggested_investigations": [
                            "Sputum AFB x3",
                            "Mantoux test",
                            "GeneXpert"
                        ],
                        "red_flags": ["Haemoptysis", "Night sweats > 2 weeks"]
                    }
                ],
                "overall_assessment": "Mock: Likely lower respiratory tract infection.",
                "suggested_next_steps": [
                    "Obtain chest X-ray urgently",
                    "Start empirical antibiotics if septic"
                ]
            }

        if "discharge" in prompt_lower:
            return {
                "admission_summary": "Mock: Patient admitted with acute presentation.",
                "clinical_course": "Mock: Stable progression throughout admission.",
                "investigations_summary": "Mock: Investigations within normal limits.",
                "diagnoses_list": ["J18.9 - Community-acquired pneumonia"],
                "treatment_given": "Mock: IV Amoxicillin 1g TDS for 5 days.",
                "discharge_medications": [
                    "Amoxicillin 500mg TDS x 5 days",
                    "Paracetamol 1g QDS PRN"
                ],
                "follow_up_instructions": "Mock: Review in OPD in 2 weeks.",
                "condition_at_discharge": "Improved"
            }

        return {"mock": True, "message": "Mock LLM response - set LLM_MODE=bedrock for real calls"}


class BedrockLLMClient:
    """
    Wrapper around AWS Bedrock Converse API for Claude inference.
    Only instantiated when LLM_MODE=bedrock to save on overhead and verify credentials.
    """

    def __init__(self):
        import boto3
        self.client = boto3.client(
            service_name="bedrock-runtime",
            region_name=config("AWS_REGION", default="eu-north-1"),
            aws_access_key_id=config("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=config("AWS_SECRET_ACCESS_KEY"),
        )
        self.model_id = config(
            "BEDROCK_MODEL_ID",
            default="eu.anthropic.claude-sonnet-4-6",
        )

    def invoke(
        self,
        prompt: str,
        system: str = None,
        max_tokens: int = 1500,
        temperature: float = 0.3,
    ) -> str:
        """
        Send a prompt via the Bedrock Converse API.
        Returns the text response string.
        """
        from botocore.exceptions import ClientError
        
        messages = [
            {"role": "user", "content": [{"text": prompt}]}
        ]

        kwargs = {
            "modelId": self.model_id,
            "messages": messages,
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            },
        }

        if system:
            kwargs["system"] = [{"text": system}]

        try:
            response = self.client.converse(**kwargs)
            return response["output"]["message"]["content"][0]["text"]

        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error(
                "Bedrock Converse failed: %s | model: %s",
                error_code,
                self.model_id,
            )
            if error_code == "AccessDeniedException":
                raise BedrockInvocationError(
                    "Access denied. Complete the Anthropic FTU form in "
                    "AWS Console → Bedrock → Model catalog."
                )
            elif error_code == "ThrottlingException":
                raise BedrockInvocationError(
                    "Rate limit hit. Retry after a short delay."
                )
            elif error_code == "ValidationException":
                raise BedrockInvocationError(
                    f"Invalid request: {e}"
                )
            raise BedrockInvocationError(f"AWS Bedrock error: {e}")

        except (KeyError, IndexError) as e:
            raise BedrockInvocationError(
                f"Unexpected response structure: {e}"
            )

    def invoke_json(
        self,
        prompt: str,
        system: str = None,
        max_tokens: int = 1500,
    ) -> dict:
        """
        Like invoke() but parses a structured JSON response.
        """
        json_system = (system or "").strip() + (
            "\n\nRespond with valid JSON only. "
            "No preamble, no explanation, no markdown fences. "
            "Raw JSON object only."
        )

        raw = self.invoke(
            prompt=prompt,
            system=json_system.strip(),
            max_tokens=max_tokens,
            temperature=0.1,
        )

        # Strip markdown fences defensively
        clean = raw.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[-1]
            clean = clean.rsplit("```", 1)[0].strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError as e:
            logger.error(
                "JSON parse failed. Raw response (first 500 chars): %s",
                raw[:500],
            )
            raise BedrockInvocationError(
                f"Model returned invalid JSON: {e}"
            )


class BedrockInvocationError(Exception):
    """Raised when Bedrock invocation fails for any reason."""
    pass


# Single entry point for all AI services
def get_llm_client():
    if LLM_MODE == "bedrock":
        return BedrockLLMClient()
    return MockLLMClient()


llm_client = get_llm_client()
