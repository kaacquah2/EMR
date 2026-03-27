from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital
from interop.models import GlobalPatient, Referral, Consent
from api.utils import get_global_patient_queryset, audit_log, get_request_hospital
from api.serializers import ReferralSerializer


def _interop_role_ok(user):
    return user.role in ("doctor", "hospital_admin", "super_admin")


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def referral_create(request):
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    global_patient_id = request.data.get("global_patient_id")
    to_facility_id = request.data.get("to_facility_id")
    reason = (request.data.get("reason") or "").strip()
    if not global_patient_id or not to_facility_id:
        return Response(
            {"message": "global_patient_id and to_facility_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not reason:
        return Response(
            {"message": "reason required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except (GlobalPatient.DoesNotExist, ValueError):
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        to_facility = Hospital.objects.get(id=to_facility_id)
    except (Hospital.DoesNotExist, ValueError):
        return Response(
            {"message": "Target facility not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if to_facility_id == str(hospital.id):
        return Response(
            {"message": "Cannot refer to own facility"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    consent = None
    consent_id = request.data.get("consent_id")
    if consent_id:
        try:
            consent = Consent.objects.get(
                id=consent_id,
                global_patient=gp,
                granted_to_facility=to_facility,
                is_active=True,
            )
        except (Consent.DoesNotExist, ValueError):
            pass  # optional; create referral without consent

    record_ids_to_share = request.data.get("record_ids_to_share")
    if isinstance(record_ids_to_share, list):
        record_ids_to_share = [str(x) for x in record_ids_to_share[:500]]
    else:
        record_ids_to_share = []

    ref = Referral.objects.create(
        global_patient=gp,
        from_facility=hospital,
        to_facility=to_facility,
        reason=reason,
        status=Referral.STATUS_PENDING,
        consent=consent,
        record_ids_to_share=record_ids_to_share,
    )
    audit_log(
        request.user,
        "CREATE",
        resource_type="referral",
        resource_id=ref.id,
        hospital=hospital,
        request=request,
        extra_data={"global_patient_id": str(gp.id), "to_facility_id": str(to_facility.id)},
    )
    return Response(ReferralSerializer(ref).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def referral_incoming(request):
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response({"data": []})

    qs = (
        Referral.objects.filter(to_facility=hospital)
        .select_related("global_patient", "from_facility", "to_facility")
        .order_by("-created_at")
    )
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs[:100]
    return Response({"data": ReferralSerializer(qs, many=True).data})


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def referral_update(request, pk):
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    ref = Referral.objects.filter(
        id=pk, to_facility=hospital
    ).select_related("global_patient", "from_facility", "to_facility").first()
    if not ref:
        return Response(
            {"message": "Referral not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_status = request.data.get("status")
    if new_status not in (
        Referral.STATUS_ACCEPTED,
        Referral.STATUS_REJECTED,
        Referral.STATUS_COMPLETED,
    ):
        return Response(
            {"message": "status must be ACCEPTED, REJECTED, or COMPLETED"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ref.status = new_status
    ref.save(update_fields=["status", "updated_at"])
    audit_log(
        request.user,
        "UPDATE",
        resource_type="referral",
        resource_id=ref.id,
        hospital=hospital,
        request=request,
        extra_data={"new_status": new_status, "global_patient_id": str(ref.global_patient_id)},
    )
    return Response(ReferralSerializer(ref).data)
