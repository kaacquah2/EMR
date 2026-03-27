from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital
from interop.models import GlobalPatient, Consent, FacilityPatient
from api.utils import get_global_patient_queryset, audit_log, get_effective_hospital, get_request_hospital
from api.serializers import ConsentSerializer


def _interop_role_ok(user):
    return user.role in ("doctor", "hospital_admin", "super_admin")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def consent_grant(request):
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    global_patient_id = request.data.get("global_patient_id")
    granted_to_facility_id = request.data.get("granted_to_facility_id")
    scope = request.data.get("scope")
    expires_at = request.data.get("expires_at")

    if not global_patient_id or not granted_to_facility_id or not scope:
        return Response(
            {"message": "global_patient_id, granted_to_facility_id, and scope required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if scope not in (Consent.SCOPE_SUMMARY, Consent.SCOPE_FULL_RECORD):
        return Response(
            {"message": "scope must be SUMMARY or FULL_RECORD"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except (GlobalPatient.DoesNotExist, ValueError):
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    # Only a facility that has this patient linked (or super_admin) may grant consent to another facility.
    if request.user.role != "super_admin":
        if not get_request_hospital(request):
            return Response(
                {"message": "No facility assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not FacilityPatient.objects.filter(
            global_patient=gp,
            facility=get_request_hospital(request),
            deleted_at__isnull=True,
        ).exists():
            return Response(
                {"message": "Only the facility that has this patient linked can grant consent"},
                status=status.HTTP_403_FORBIDDEN,
            )
    try:
        to_facility = Hospital.objects.get(id=granted_to_facility_id)
    except (Hospital.DoesNotExist, ValueError):
        return Response(
            {"message": "Facility not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    exp = None
    if expires_at:
        try:
            from django.utils.dateparse import parse_datetime
            exp = parse_datetime(expires_at)
            if not exp:
                exp = None
        except Exception:
            pass

    consent = Consent.objects.create(
        global_patient=gp,
        granted_to_facility=to_facility,
        granted_by=request.user,
        scope=scope,
        expires_at=exp,
        is_active=True,
    )
    audit_log(
        request.user,
        "CREATE",
        resource_type="consent",
        resource_id=consent.id,
        hospital=get_request_hospital(request),
        request=request,
        extra_data={"global_patient_id": str(gp.id), "granted_to_facility_id": str(to_facility.id), "scope": scope},
    )
    return Response(ConsentSerializer(consent).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def consent_list(request):
    """List consents for a global patient (for audit trail)."""
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    global_patient_id = request.GET.get("global_patient_id")
    if not global_patient_id:
        return Response(
            {"message": "global_patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    qs = get_global_patient_queryset(request.user, get_effective_hospital(request)).filter(id=global_patient_id)
    if not qs.exists():
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    gp = qs.first()
    consents = (
        Consent.objects.filter(global_patient=gp)
        .select_related("granted_to_facility", "granted_by")
        .order_by("-created_at")
    )
    return Response({
        "data": ConsentSerializer(consents, many=True).data,
    })


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def consent_revoke(request, pk):
    """Revoke consent (set is_active=False). Only grantor facility or super_admin."""
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        consent = Consent.objects.select_related(
            "global_patient", "granted_to_facility", "granted_by"
        ).get(id=pk)
    except (Consent.DoesNotExist, ValueError):
        return Response(
            {"message": "Consent not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    # Only the facility that granted (granted_by.hospital) or super_admin can revoke
    if request.user.role != "super_admin":
        req_h = get_request_hospital(request)
        if not req_h or consent.granted_by.hospital_id != req_h.id:
            return Response(
                {"message": "Only the facility that granted this consent can revoke it"},
                status=status.HTTP_403_FORBIDDEN,
            )
    if not consent.is_active:
        return Response(ConsentSerializer(consent).data)
    consent.is_active = False
    consent.save(update_fields=["is_active"])
    audit_log(
        request.user,
        "CROSS_FACILITY_ACCESS_REVOKED",
        resource_type="consent",
        resource_id=consent.id,
        hospital=get_request_hospital(request),
        request=request,
        extra_data={
            "global_patient_id": str(consent.global_patient_id),
            "granted_to_facility_id": str(consent.granted_to_facility_id),
        },
    )
    return Response(ConsentSerializer(consent).data)
