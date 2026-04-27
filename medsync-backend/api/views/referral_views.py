from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q, Count

from core.models import Hospital
from interop.models import GlobalPatient, Referral, Consent
from api.utils import audit_log, get_request_hospital
from api.serializers import ReferralSerializer
from api.state_machines import validate_referral_transition, StateMachineError


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
            logger.debug(f"No active consent from {hospital.id} to {to_facility.id}; referral will proceed without shared records")

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
    
    # Validate state transition
    try:
        validate_referral_transition(ref.status, new_status)
    except StateMachineError as e:
        return Response(
            {"message": str(e)},
            status=status.HTTP_400_BAD_REQUEST
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


# ============================================================================
# PHASE 7.1: Doctor Referral Tracking Panel
# ============================================================================


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_referrals(request):
    """
    GET /referrals/mine?direction=outgoing|incoming|both&status=PENDING|ACCEPTED|COMPLETED|REJECTED
    
    Get referrals created from or received by the requesting doctor's hospital.
    Returns a summary with counts and a list of referrals.
    """
    if not _interop_role_ok(request.user):
        return Response(
            {'message': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    hospital = get_request_hospital(request)
    direction = request.query_params.get('direction', 'both')
    status_filter = request.query_params.get('status')
    
    # Build query based on direction
    if direction == 'outgoing':
        # Referrals sent by my hospital
        qs = Referral.objects.filter(from_facility=hospital)
    elif direction == 'incoming':
        # Referrals received by my hospital
        if not hospital:
            return Response(
                {'message': 'No facility context'},
                status=status.HTTP_400_BAD_REQUEST
            )
        qs = Referral.objects.filter(to_facility=hospital)
    else:
        # Both directions
        if hospital:
            qs = Referral.objects.filter(
                Q(from_facility=hospital) | Q(to_facility=hospital)
            )
        else:
            qs = Referral.objects.filter(from_facility=hospital)
    
    # Status filter
    if status_filter and status_filter in ('PENDING', 'ACCEPTED', 'REJECTED', 'COMPLETED'):
        qs = qs.filter(status=status_filter)
    
    # Select related for efficiency
    qs = qs.select_related(
        'global_patient', 'from_facility', 'to_facility', 'consent'
    ).order_by('-created_at')[:100]
    
    # Format referrals data
    referrals_data = []
    for ref in qs:
        is_outgoing = ref.from_facility_id == hospital.id if hospital else False
        referrals_data.append({
            'id': str(ref.id),
            'direction': 'outgoing' if is_outgoing else 'incoming',
            'patient': {
                'id': str(ref.global_patient.id),
                'name': ref.global_patient.full_name,
                'ghana_health_id': ref.global_patient.ghana_health_id,
                'date_of_birth': ref.global_patient.date_of_birth.isoformat() if ref.global_patient.date_of_birth else None,
            },
            'from_facility': {
                'id': str(ref.from_facility.id),
                'name': ref.from_facility.name,
            },
            'to_facility': {
                'id': str(ref.to_facility.id),
                'name': ref.to_facility.name,
            },
            'reason': ref.reason,
            'status': ref.status,
            'consent_granted': ref.consent is not None and ref.consent.is_active,
            'created_at': ref.created_at.isoformat(),
            'updated_at': ref.updated_at.isoformat() if ref.updated_at else None,
            'record_ids_to_share': ref.record_ids_to_share or [],
        })
    
    # Summary counts
    all_referrals = qs.values('status').annotate(count=Count('id'))
    pending_count = next((item['count'] for item in all_referrals if item['status'] == 'PENDING'), 0)
    accepted_count = next((item['count'] for item in all_referrals if item['status'] == 'ACCEPTED'), 0)
    completed_count = next((item['count'] for item in all_referrals if item['status'] == 'COMPLETED'), 0)
    rejected_count = next((item['count'] for item in all_referrals if item['status'] == 'REJECTED'), 0)
    
    return Response({
        'summary': {
            'total': len(referrals_data),
            'outgoing': len([r for r in referrals_data if r['direction'] == 'outgoing']),
            'incoming': len([r for r in referrals_data if r['direction'] == 'incoming']),
            'pending': pending_count,
            'accepted': accepted_count,
            'completed': completed_count,
            'rejected': rejected_count,
        },
        'referrals': referrals_data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def accept_referral(request, pk):
    """
    POST /referrals/:id/accept
    
    Accept an incoming referral by the receiving hospital.
    Validates that the referral is directed to the requesting user's hospital.
    """
    if not _interop_role_ok(request.user):
        return Response(
            {'message': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    hospital = get_request_hospital(request)
    
    try:
        referral = Referral.objects.select_related(
            'global_patient', 'from_facility', 'to_facility'
        ).get(id=pk)
    except (Referral.DoesNotExist, ValueError):
        return Response(
            {'message': 'Referral not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Validate referral is directed to requesting hospital
    if hospital and referral.to_facility_id != hospital.id:
        return Response(
            {'message': 'Referral not directed to your hospital'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Validate status transition
    if referral.status != Referral.STATUS_PENDING:
        return Response(
            {'message': f'Cannot accept referral in status: {referral.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        validate_referral_transition(referral.status, Referral.STATUS_ACCEPTED)
    except StateMachineError as e:
        return Response(
            {'message': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update referral
    referral.status = Referral.STATUS_ACCEPTED
    referral.save(update_fields=['status', 'updated_at'])
    
    # Audit
    audit_log(
        request.user,
        'UPDATE',
        resource_type='referral',
        resource_id=referral.id,
        hospital=hospital,
        request=request,
        extra_data={
            'action': 'accepted',
            'patient_id': str(referral.global_patient.id),
            'from_facility': referral.from_facility.name
        },
    )
    
    return Response({
        'id': str(referral.id),
        'status': referral.status,
        'message': 'Referral accepted successfully',
        'referral': ReferralSerializer(referral).data,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def complete_referral(request, pk):
    """
    POST /referrals/:id/complete
    
    Mark a referral as completed after the patient has been seen at the 
    receiving hospital.
    """
    if not _interop_role_ok(request.user):
        return Response(
            {'message': 'Permission denied'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    hospital = get_request_hospital(request)
    
    try:
        referral = Referral.objects.select_related(
            'global_patient', 'from_facility', 'to_facility'
        ).get(id=pk)
    except (Referral.DoesNotExist, ValueError):
        return Response(
            {'message': 'Referral not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Validate authorization
    if hospital and referral.to_facility_id != hospital.id:
        return Response(
            {'message': 'Not authorized to complete this referral'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Validate status transition
    if referral.status != Referral.STATUS_ACCEPTED:
        return Response(
            {'message': f'Cannot complete referral in status: {referral.status}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        validate_referral_transition(referral.status, Referral.STATUS_COMPLETED)
    except StateMachineError as e:
        return Response(
            {'message': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Update referral
    referral.status = Referral.STATUS_COMPLETED
    referral.save(update_fields=['status', 'updated_at'])
    
    # Audit
    audit_log(
        request.user,
        'UPDATE',
        resource_type='referral',
        resource_id=referral.id,
        hospital=hospital,
        request=request,
        extra_data={
            'action': 'completed',
            'patient_id': str(referral.global_patient.id),
        },
    )
    
    return Response({
        'id': str(referral.id),
        'status': referral.status,
        'message': 'Referral marked as completed',
        'referral': ReferralSerializer(referral).data,
    })
