"""
AI-powered clinical endpoints.

POST /encounters/<id>/generate-discharge-summary
  — Generate a structured discharge summary using the LLM service.
    Saves the formatted text to Encounter.discharge_summary.
    Roles: doctor only.
"""

import logging

from decouple import config
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from records.models import Encounter
from api.audit_logging import audit_log_extended
from api.services.discharge_service import (
    generate_discharge_summary,
    format_discharge_summary,
)
from api.services.llm_client import BedrockInvocationError

# In non-debug (production) deployments the LLM must be a real provider.
# Mock mode is allowed in local dev (DEBUG=True) to avoid incurring costs.
_LLM_MODE = config("LLM_MODE", default="mock")
_DEBUG = config("DEBUG", default=False, cast=bool)

logger = logging.getLogger(__name__)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_encounter_discharge_summary(request, encounter_id):
    """
    Generate an AI discharge summary for an encounter.

    Reads diagnoses, prescriptions, vitals, and nursing notes for the
    patient, calls the LLM service, saves the result to
    Encounter.discharge_summary, and returns both the structured JSON
    and the formatted plain-text version.
    """
    if request.user.role != "doctor":
        return Response(
            {"error": "Only doctors can generate discharge summaries"},
            status=status.HTTP_403_FORBIDDEN,
        )

    # Guard: refuse to persist mock text in a production deployment.
    # Set LLM_MODE=bedrock in production. Mock mode is fine for local dev (DEBUG=True).
    if _LLM_MODE == "mock" and not _DEBUG:
        return Response(
            {
                "error": "ai_not_configured",
                "message": (
                    "AI discharge summary is not available: LLM_MODE is set to 'mock' "
                    "but DEBUG is False. Set LLM_MODE=bedrock and configure AWS credentials "
                    "in the environment to enable this feature."
                ),
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    hospital = getattr(request.user, "hospital", None)

    try:
        qs = Encounter.objects.all()
        if hospital:
            qs = qs.filter(hospital=hospital)
        encounter = qs.get(id=encounter_id)
    except Encounter.DoesNotExist:
        return Response({"error": "Encounter not found"}, status=status.HTTP_404_NOT_FOUND)

    try:
        result = generate_discharge_summary(encounter, encounter.patient)
    except BedrockInvocationError as e:
        return Response(
            {"error": f"AI service unavailable: {e}"},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    except Exception as e:
        logger.error("Discharge summary generation failed for encounter %s: %s", encounter_id, e, exc_info=True)
        return Response(
            {"error": "Failed to generate discharge summary"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    formatted = format_discharge_summary(result)
    encounter.discharge_summary = formatted
    encounter.save(update_fields=["discharge_summary", "updated_at"])

    audit_log_extended(
        user=request.user,
        action="GENERATE_DISCHARGE_SUMMARY",
        resource_type="Encounter",
        resource_id=str(encounter_id),
        hospital=encounter.hospital,
        extra_data={"ai_generated": True},
    )

    return Response(
        {"data": result, "formatted_text": formatted},
        status=status.HTTP_200_OK,
    )
