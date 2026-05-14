import hashlib
import json
from django.core.cache import cache
from api.services.llm_client import llm_client, BedrockInvocationError

CACHE_TTL = 60 * 30  # 30 minutes

DIFFERENTIAL_SYSTEM_PROMPT = """You are a clinical decision support assistant for a 
Ghanaian hospital EMR. You help doctors generate differential diagnoses.
Always respond with valid JSON matching the specified schema exactly."""

def build_differential_prompt(patient_context: dict, chief_complaint: str) -> str:
    """
    Build the prompt for Claude, ensuring context is focused to save tokens.
    """
    return f"""
Patient context (no identifiers):
- Age: {patient_context.get('age')}
- Sex: {patient_context.get('sex')}
- Chief complaint: {chief_complaint}
- Active allergies: {patient_context.get('allergies')}
- Current medications: {patient_context.get('medications')}
- Latest vitals: {patient_context.get('vitals')}
- Recent diagnoses: {patient_context.get('recent_diagnoses')}

Return a JSON object with this exact structure:
{{
  "differentials": [
    {{
      "rank": 1,
      "diagnosis": "string",
      "icd10_code": "string",
      "probability": "high|medium|low",
      "supporting_factors": ["string"],
      "suggested_investigations": ["string"],
      "red_flags": ["string"]
    }}
  ],
  "overall_assessment": "string",
  "suggested_next_steps": ["string"]
}}

Provide 3-5 differentials ranked by likelihood.
"""

def generate_differential(patient_context: dict, chief_complaint: str) -> dict:
    """
    Generate differential diagnosis with caching to save credits.
    """
    
    # Build a cache key from inputs to avoid redundant API calls
    cache_input = json.dumps(
        {"ctx": patient_context, "cc": chief_complaint},
        sort_keys=True
    )
    cache_key = "diff:" + hashlib.md5(cache_input.encode()).hexdigest()

    cached = cache.get(cache_key)
    if cached:
        return cached

    prompt = build_differential_prompt(patient_context, chief_complaint)

    try:
        result = llm_client.invoke_json(prompt=prompt, system=DIFFERENTIAL_SYSTEM_PROMPT)
        # Store in cache for 30 minutes
        cache.set(cache_key, result, CACHE_TTL)
        return result
    except BedrockInvocationError as e:
        raise
