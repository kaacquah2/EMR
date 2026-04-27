from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from api.serializers import ConsentSerializer
from api.services import consent_service


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def consent_grant(request):
    consent, err = consent_service.grant_consent(request, request.data)
    if err:
        msg, code = err
        return Response({"message": msg}, status=code)
    return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consent_list(request):
    """List consents for a global patient (for audit trail)."""
    global_patient_id = request.GET.get("global_patient_id")
    consents, err = consent_service.consents_for_global_patient(request, global_patient_id)
    if err:
        msg, code = err
        return Response({"message": msg}, status=code)
    return Response({
        "data": ConsentSerializer(consents, many=True).data,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def consent_revoke(request, pk):
    """Revoke consent (set is_active=False). Only grantor facility or super_admin."""
    consent, err = consent_service.revoke_consent(request, str(pk))
    if err:
        msg, code = err
        return Response({"message": msg}, status=code)
    return Response(ConsentSerializer(consent).data)
