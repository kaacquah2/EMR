from io import BytesIO
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.http import HttpResponse
from django.db.models import Q
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as pdf_canvas

from patients.models import Patient, Allergy
from records.models import MedicalRecord, Diagnosis, Prescription, LabResult, Vital
from api.utils import get_patient_queryset, get_medical_record_queryset, get_effective_hospital, get_request_hospital, audit_log, sanitize_audit_resource_id
from api.serializers import (
    PatientSerializer,
    PatientDemographicsOnlySerializer,
    AllergySerializer,
    DiagnosisSerializer,
    PrescriptionSerializer,
    LabResultSerializer,
    VitalSerializer,
    MedicalRecordSerializer,
)


def _paginated(data, request):
    return {"data": data, "next_cursor": None, "has_more": False}


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_search(request):
    q = (request.GET.get("q") or request.GET.get("name") or "").strip()
    ghana_id = request.GET.get("ghana_health_id", "").strip()
    dob = request.GET.get("dob", "").strip()
    user = request.user
    qs = get_patient_queryset(user, get_effective_hospital(request))
    if ghana_id:
        qs = qs.filter(ghana_health_id__icontains=ghana_id)
    elif dob:
        qs = qs.filter(date_of_birth=dob)
    elif q:
        qs = qs.filter(
            Q(full_name__icontains=q)
            | Q(ghana_health_id__icontains=q)
            | Q(phone__icontains=q)
            | Q(nhis_number__icontains=q)
        )
    else:
        return Response({"data": [], "next_cursor": None, "has_more": False})
    qs = qs[:50]
    if user.role == "receptionist":
        return Response(_paginated(PatientDemographicsOnlySerializer(qs, many=True).data, request))
    return Response(_paginated(PatientSerializer(qs, many=True).data, request))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def patient_duplicate_check(request):
    """Lightweight duplicate pre-check by Ghana Health ID for registration flow."""
    if request.user.role not in ("receptionist", "ward_clerk", "hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    ghana_id = (request.GET.get("ghana_health_id") or request.data.get("ghana_health_id") or "").strip()
    if not ghana_id:
        return Response({"duplicate": False, "message": "ghana_health_id required"}, status=status.HTTP_400_BAD_REQUEST)
    qs = get_patient_queryset(request.user, get_effective_hospital(request))
    existing = qs.filter(ghana_health_id__iexact=ghana_id).first()
    if not existing:
        return Response({"duplicate": False})
    return Response(
        {
            "duplicate": True,
            "existing": {
                "patient_id": str(existing.id),
                "ghana_health_id": existing.ghana_health_id,
                "full_name": existing.full_name,
                "date_of_birth": str(existing.date_of_birth) if existing.date_of_birth else None,
            },
        }
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def patient_create(request):
    if request.user.role not in ("receptionist", "ward_clerk", "hospital_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital and request.user.role == "super_admin" and request.data.get("hospital_id"):
        from core.models import Hospital
        hospital = Hospital.objects.filter(id=request.data.get("hospital_id")).first()
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    ghana_id = (data.get("ghana_health_id") or "").strip()
    if not ghana_id:
        return Response(
            {"message": "Ghana Health ID required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if Patient.objects.filter(ghana_health_id=ghana_id).exists():
        return Response(
            {"message": "Patient with this Ghana Health ID already exists"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = Patient.objects.create(
        ghana_health_id=ghana_id,
        full_name=(data.get("full_name") or "").strip(),
        date_of_birth=data.get("date_of_birth"),
        gender=data.get("gender", "unknown"),
        phone=data.get("phone") or None,
        national_id=data.get("national_id") or None,
        nhis_number=data.get("nhis_number") or None,
        passport_number=data.get("passport_number") or None,
        blood_group=data.get("blood_group") or "unknown",
        registered_at=hospital,
        created_by=request.user,
    )
    for a in data.get("allergies", []) or []:
        if a.get("allergen"):
            Allergy.objects.create(
                patient=patient,
                allergen=a["allergen"],
                reaction_type=a.get("reaction_type", ""),
                severity=a.get("severity", "moderate"),
                recorded_by=request.user,
            )
    return Response(PatientSerializer(patient).data, status=status.HTTP_201_CREATED)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def patient_detail(request, pk):
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        audit_log(
            request.user,
            "VIEW_PATIENT_RECORD",
            resource_type="patient",
            resource_id=patient.id,
            hospital=patient.registered_at,
            request=request,
        )
    if request.method == "GET" and request.user.role in (
        "receptionist",
        "lab_technician",
        "radiology_technician",
        "billing_staff",
        "ward_clerk",
        "pharmacist",
    ):
        return Response(PatientDemographicsOnlySerializer(patient).data)
    if request.method == "PATCH":
        if request.user.role not in ("doctor", "hospital_admin", "super_admin"):
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        data = request.data
        if "full_name" in data and data["full_name"] is not None:
            patient.full_name = (data["full_name"] or "").strip()
        if "date_of_birth" in data and data["date_of_birth"] is not None:
            patient.date_of_birth = data["date_of_birth"]
        if "gender" in data and data["gender"] is not None:
            patient.gender = data["gender"]
        if "phone" in data:
            patient.phone = data["phone"] or None
        if "national_id" in data:
            patient.national_id = data["national_id"] or None
        if "nhis_number" in data:
            patient.nhis_number = data["nhis_number"] or None
        if "passport_number" in data:
            patient.passport_number = data["passport_number"] or None
        if "blood_group" in data and data["blood_group"] is not None:
            patient.blood_group = data["blood_group"]
        patient.save(update_fields=["full_name", "date_of_birth", "gender", "phone", "national_id", "nhis_number", "passport_number", "blood_group"])
    return Response(PatientSerializer(patient).data)


def _block_non_clinical_roles(request):
    """Hospital admin and receptionist cannot view clinical data per MedSync Role Specs."""
    if request.user.role in ("hospital_admin", "receptionist"):
        return True
    return False


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_records(request, pk):
    if _block_non_clinical_roles(request):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    audit_log(
        request.user,
        "VIEW_PATIENT_RECORD",
        resource_type="patient_records",
        resource_id=patient.id,
        hospital=patient.registered_at,
        request=request,
        extra_data={"scope": "FULL_RECORD"},
    )
    records = get_medical_record_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request)).select_related(
        "diagnosis", "prescription", "labresult", "vital"
    ).order_by("-created_at")[:100]
    if request.user.role == "nurse":
        records = [r for r in records if r.record_type != "diagnosis"]
    return Response({
        "data": MedicalRecordSerializer(records, many=True).data,
        "next_cursor": None,
        "has_more": False,
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_diagnoses(request, pk):
    if _block_non_clinical_roles(request):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    record_ids = get_medical_record_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request)).values_list("id", flat=True)
    diagnoses = Diagnosis.objects.filter(
        record_id__in=record_ids
    ).select_related("record").order_by("-record__created_at")
    return Response({"data": DiagnosisSerializer(diagnoses, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_prescriptions(request, pk):
    if _block_non_clinical_roles(request):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    record_ids = get_medical_record_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request)).values_list("id", flat=True)
    prescriptions = Prescription.objects.filter(
        record_id__in=record_ids
    ).select_related("record").order_by("-record__created_at")
    return Response({"data": PrescriptionSerializer(prescriptions, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_labs(request, pk):
    if _block_non_clinical_roles(request):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    record_ids = get_medical_record_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request)).values_list("id", flat=True)
    results = LabResult.objects.filter(
        record_id__in=record_ids
    ).select_related("record").order_by("-result_date")
    return Response({"data": LabResultSerializer(results, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_vitals(request, pk):
    if _block_non_clinical_roles(request):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    record_ids = get_medical_record_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request)).values_list("id", flat=True)
    vitals = Vital.objects.filter(
        record_id__in=record_ids
    ).select_related("record").order_by("-record__created_at")
    return Response({"data": VitalSerializer(vitals, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_allergies(request, pk):
    if _block_non_clinical_roles(request):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    allergies = patient.allergy_set.all().order_by("-created_at")
    return Response({"data": AllergySerializer(allergies, many=True).data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_export_pdf(request, pk):
    """Export patient record as PDF: Doctor and super_admin only (super_admin view-only; spec blocks create)."""
    if request.user.role not in ("doctor", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    records = (
        get_medical_record_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request))
        .select_related("diagnosis", "prescription", "labresult", "vital")
        .order_by("-created_at")[:100]
    )
    allergies = patient.allergy_set.filter(is_active=True).order_by("-created_at")

    buf = BytesIO()
    c = pdf_canvas.Canvas(buf, pagesize=letter)
    width, height = letter
    y = height - inch

    c.setFont("Helvetica-Bold", 14)
    c.drawString(inch, y, "Patient Record Export")
    y -= 0.4 * inch

    c.setFont("Helvetica", 10)
    c.drawString(inch, y, f"Patient: {patient.full_name or ''}")
    y -= 0.25 * inch
    c.drawString(inch, y, f"Ghana Health ID: {patient.ghana_health_id or ''}")
    y -= 0.25 * inch
    c.drawString(inch, y, f"DOB: {patient.date_of_birth}")
    y -= 0.25 * inch
    c.drawString(inch, y, f"Gender: {patient.gender}  Blood group: {patient.blood_group}")
    y -= 0.4 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Allergies")
    y -= 0.3 * inch
    c.setFont("Helvetica", 9)
    if allergies:
        for a in allergies:
            line = f"- {a.allergen} ({a.reaction_type or ''}, {a.severity})"
            if y < inch * 1.5:
                c.showPage()
                y = height - inch
            c.drawString(inch + 0.2 * inch, y, line[:80])
            y -= 0.22 * inch
    else:
        c.drawString(inch, y, "None recorded")
        y -= 0.3 * inch
    y -= 0.3 * inch

    c.setFont("Helvetica-Bold", 11)
    c.drawString(inch, y, "Record timeline")
    y -= 0.3 * inch
    c.setFont("Helvetica", 8)
    for rec in records:
        if y < inch * 1.2:
            c.showPage()
            y = height - inch
        created = rec.created_at.strftime("%Y-%m-%d %H:%M") if rec.created_at else ""
        c.drawString(inch, y, f"{created}  [{rec.record_type}]")
        y -= 0.2 * inch
        if rec.record_type == "diagnosis" and hasattr(rec, "diagnosis") and rec.diagnosis:
            d = rec.diagnosis
            c.drawString(inch + 0.2 * inch, y, f"  {d.icd10_code} - {d.icd10_description}")
            y -= 0.2 * inch
        elif rec.record_type == "prescription" and hasattr(rec, "prescription") and rec.prescription:
            p = rec.prescription
            c.drawString(inch + 0.2 * inch, y, f"  {p.drug_name} {p.dosage} {p.frequency}")
            y -= 0.2 * inch
        elif rec.record_type == "vital_signs":
            c.drawString(inch + 0.2 * inch, y, "  Vitals recorded")
            y -= 0.2 * inch
        elif rec.record_type == "allergy":
            c.drawString(inch + 0.2 * inch, y, "  Allergy recorded")
            y -= 0.2 * inch
        elif rec.record_type == "nursing_note":
            c.drawString(inch + 0.2 * inch, y, "  Nursing note")
            y -= 0.2 * inch
        elif rec.record_type == "lab_result":
            c.drawString(inch + 0.2 * inch, y, "  Lab result")
            y -= 0.2 * inch
        y -= 0.15 * inch

    c.save()
    buf.seek(0)
    audit_log(
        request.user,
        "EXPORT",
        resource_type="patient",
        resource_id=sanitize_audit_resource_id(str(patient.id)),
        hospital=get_request_hospital(request),
        request=request,
    )
    resp = HttpResponse(buf.getvalue(), content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="patient_{patient.ghana_health_id or patient.id}_record.pdf"'
    return resp
