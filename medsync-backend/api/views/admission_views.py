from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from patients.models import Patient, PatientAdmission
from core.models import Ward, Bed
from api.utils import get_patient_queryset, get_effective_hospital, get_request_hospital


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
