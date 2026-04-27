from datetime import timedelta
from uuid import UUID
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from patients.models import PatientAdmission, ClinicalAlert
from core.models import Ward, Bed
from records.models import Prescription, Vital
from api.utils import get_patient_queryset, get_effective_hospital, get_request_hospital, audit_log


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admissions_list(request):
    if request.user.role not in ("doctor", "hospital_admin", "nurse", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if request.user.role == "super_admin" and not hospital:
        qs = PatientAdmission.objects.filter(
            discharged_at__isnull=True,
        ).select_related("patient", "ward", "bed", "admitted_by", "hospital")
    elif hospital:
        qs = PatientAdmission.objects.filter(
            hospital=hospital,
            discharged_at__isnull=True,
        ).select_related("patient", "ward", "bed", "admitted_by")
    else:
        qs = PatientAdmission.objects.none()
    if request.user.role == "nurse" and request.user.ward_id:
        qs = qs.filter(ward=request.user.ward)
    data = [
        {
            "admission_id": str(a.id),
            "patient_id": str(a.patient_id),
            "patient_name": a.patient.full_name,
            "ghana_health_id": a.patient.ghana_health_id,
            "ward_id": str(a.ward_id),
            "ward_name": a.ward.ward_name,
            "bed_id": str(a.bed_id) if a.bed_id else None,
            "bed_code": a.bed.bed_code if a.bed_id else None,
            "admitted_at": a.admitted_at.isoformat(),
            "admitted_by": a.admitted_by.full_name,
        }
        for a in qs
    ]
    return Response({"data": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admissions_by_ward(request, ward_id):
    if request.user.role not in ("nurse", "doctor", "hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        req_h = get_request_hospital(request)
        if req_h:
            ward = Ward.objects.get(id=ward_id, hospital=req_h)
        else:
            ward = Ward.objects.get(id=ward_id)
    except Ward.DoesNotExist:
        return Response(
            {"message": "Ward not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.user.role == "nurse" and request.user.ward_id != ward.id:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    admissions = PatientAdmission.objects.filter(
        ward=ward,
        discharged_at__isnull=True,
    ).select_related("patient", "admitted_by", "bed")
    data = [
        {
            "admission_id": str(a.id),
            "patient_id": str(a.patient_id),
            "patient_name": a.patient.full_name,
            "ghana_health_id": a.patient.ghana_health_id,
            "bed_id": str(a.bed_id) if a.bed_id else None,
            "bed_code": a.bed.bed_code if a.bed_id else None,
            "admitted_at": a.admitted_at.isoformat(),
            "admitted_by": a.admitted_by.full_name,
        }
        for a in admissions
    ]
    return Response({"data": data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admission_create(request):
    if request.user.role not in ("doctor", "hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
    ward_id = data.get("ward_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not ward_id:
        return Response(
            {"message": "ward_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        ward = Ward.objects.get(id=ward_id, hospital=hospital)
    except Ward.DoesNotExist:
        return Response(
            {"message": "Ward not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if PatientAdmission.objects.filter(patient=patient, discharged_at__isnull=True).exists():
        return Response(
            {"message": "Patient is already admitted"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    bed = None
    bed_id = data.get("bed_id")
    if bed_id:
        bed_qs = Bed.objects.filter(id=bed_id, ward=ward, is_active=True)
        bed = bed_qs.first()
        if bed and bed.status != "available":
            return Response(
                {"message": "Bed is not available"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    admission = PatientAdmission.objects.create(
        patient=patient,
        ward=ward,
        bed=bed,
        hospital=hospital,
        admitted_by=request.user,
    )
    if bed:
        bed.status = "occupied"
        bed.save(update_fields=["status"])
    return Response(
        {"admission_id": str(admission.id), "message": "Patient admitted"},
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def admission_discharge(request, admission_id):
    if request.user.role not in ("doctor", "hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    req_h = get_request_hospital(request)
    if request.user.role != "super_admin" and not req_h:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    qs = PatientAdmission.objects.filter(id=admission_id)
    if req_h:
        qs = qs.filter(hospital=req_h)
    admission = qs.first()
    if not admission:
        return Response(
            {"message": "Admission not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if admission.discharged_at:
        return Response(
            {"message": "Patient already discharged"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    admission.discharged_at = timezone.now()
    admission.discharge_reason = request.data.get("discharge_reason", "")
    admission.save()
    if admission.bed_id:
        admission.bed.status = "available"
        admission.bed.save(update_fields=["status"])
    return Response({"message": "Patient discharged"})


# NURSE DASHBOARD: Enhanced ward endpoint with vitals, dispense, and alert counts
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admissions_by_ward_dashboard(request, ward_id):
    """
    Enhanced GET /admissions/ward/<ward_id>/dashboard endpoint for nurse dashboard.
    Returns detailed bed information including vitals overdue status, pending dispense count,
    and active clinical alerts per bed. Only accessible to nurses assigned to the ward.

    Returns:
    {
        "data": [{
            "bed_code": "3B-01",
            "patient_id": "uuid",
            "patient_name": "Ama Owusu",
            "age": 35,
            "gender": "female",
            "admission_date": "2024-01-15",
            "status": "stable|watch|critical|vacant",
            "last_vitals_at": "2024-01-15T18:30:00Z" or null,
            "vitals_overdue": true|false,
            "vitals_overdue_hours": 5 or null,
            "active_alerts_count": 0,
            "pending_dispense_count": 0
        }, ...]
    }
    """
    # Only nurses can access dashboard data for their own ward
    if request.user.role != "nurse":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    if request.user.ward_id != UUID(ward_id):
        return Response(
            {"message": "Permission denied - not assigned to this ward"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        ward = Ward.objects.get(id=ward_id, hospital=request.user.hospital)
    except Ward.DoesNotExist:
        return Response(
            {"message": "Ward not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get all beds in the ward (with or without patients)
    beds = Bed.objects.filter(ward=ward).select_related("admissions__patient").order_by("bed_code")

    data = []
    now = timezone.now()
    vitals_overdue_threshold = now - timedelta(hours=4)

    for bed in beds:
        # Get active admission for this bed
        admission = PatientAdmission.objects.filter(
            bed=bed,
            discharged_at__isnull=True
        ).select_related("patient").first()

        if not admission:
            # Vacant bed
            data.append({
                "bed_code": bed.bed_code,
                "patient_id": None,
                "patient_name": None,
                "age": None,
                "gender": None,
                "admission_date": None,
                "status": "vacant",
                "last_vitals_at": None,
                "vitals_overdue": False,
                "vitals_overdue_hours": None,
                "active_alerts_count": 0,
                "pending_dispense_count": 0,
            })
            continue

        patient = admission.patient

        # Calculate age
        today = timezone.now().date()
        age = today.year - patient.date_of_birth.year - (
            (today.month, today.day) < (patient.date_of_birth.month, patient.date_of_birth.day)
        )

        # Get last vitals reading
        last_vital = Vital.objects.filter(
            record__patient=patient,
            record__hospital=request.user.hospital
        ).order_by("-record__created_at").first()

        last_vitals_at = last_vital.record.created_at if last_vital else None
        vitals_overdue = last_vitals_at is None or last_vitals_at < vitals_overdue_threshold
        vitals_overdue_hours = None
        if vitals_overdue and last_vitals_at:
            hours_diff = (now - last_vitals_at).total_seconds() / 3600
            vitals_overdue_hours = int(round(hours_diff))

        # Count pending prescriptions (dispense_status = "pending")
        pending_dispense_count = Prescription.objects.filter(
            record__patient=patient,
            record__hospital=request.user.hospital,
            dispense_status="pending"
        ).count()

        # Count active clinical alerts
        active_alerts_count = ClinicalAlert.objects.filter(
            patient=patient,
            hospital=request.user.hospital,
            status="active"
        ).count()

        # Determine bed status based on alerts, vitals, and clinical severity
        # Critical: active ClinicalAlert with severity=critical OR SpO2<88% OR BP systolic>180
        critical_alert = ClinicalAlert.objects.filter(
            patient=patient,
            hospital=request.user.hospital,
            status="active",
            severity="critical"
        ).exists()

        critical_vital = False
        if last_vital:
            if (last_vital.spo2_percent and last_vital.spo2_percent < 88) or \
               (last_vital.bp_systolic and last_vital.bp_systolic > 180):
                critical_vital = True

        bed_status = "stable"
        if critical_alert or critical_vital:
            bed_status = "critical"
        elif vitals_overdue or active_alerts_count > 0:
            bed_status = "watch"

        data.append({
            "bed_code": bed.bed_code,
            "patient_id": str(patient.id),
            "patient_name": patient.full_name,
            "age": age,
            "gender": patient.gender,
            "admission_date": admission.admitted_at.date().isoformat(),
            "status": bed_status,
            "last_vitals_at": last_vitals_at.isoformat() if last_vitals_at else None,
            "vitals_overdue": vitals_overdue,
            "vitals_overdue_hours": vitals_overdue_hours,
            "active_alerts_count": active_alerts_count,
            "pending_dispense_count": pending_dispense_count,
        })

    audit_log(
        request.user,
        "VIEW_WARD_DASHBOARD",
        "ward",
        ward_id,
        request.user.hospital,
        request,
    )

    return Response({"data": data})
