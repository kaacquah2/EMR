from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Count

from core.models import Department, User
from patients.models import Allergy, ClinicalAlert
from records.models import Encounter
from records.models import LabOrder, Prescription
from api.utils import get_patient_queryset, get_encounter_queryset, get_effective_hospital, get_request_hospital
from api.pagination import paginate_queryset


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def encounter_list(request, pk):
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        if request.user.role not in ("super_admin", "hospital_admin", "doctor", "nurse"):
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = (
            get_encounter_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request))
            .select_related("created_by", "assigned_department", "assigned_doctor")
            .order_by("-encounter_date")
        )
        page, next_cursor, has_more = paginate_queryset(qs, request, page_size=20, max_page_size=100)
        data = [
            {
                "id": str(e.id),
                "encounter_type": e.encounter_type,
                "encounter_date": e.encounter_date.isoformat(),
                "notes": e.notes,
                "created_by": e.created_by.full_name,
                "assigned_department_id": str(e.assigned_department_id) if e.assigned_department_id else None,
                "assigned_department_name": e.assigned_department.name if e.assigned_department else None,
                "assigned_doctor_id": str(e.assigned_doctor_id) if e.assigned_doctor_id else None,
                "assigned_doctor_name": e.assigned_doctor.full_name if e.assigned_doctor else None,
                "status": e.status,
                "visit_status": e.visit_status,
                "chief_complaint": e.chief_complaint,
                "hpi": e.hpi,
                "examination_findings": e.examination_findings,
                "assessment_plan": e.assessment_plan,
                "discharge_summary": e.discharge_summary,
            }
            for e in page
        ]
        return Response({"data": data, "next_cursor": next_cursor, "has_more": has_more})
    if request.method == "POST":
        if request.user.role not in ("super_admin", "hospital_admin", "doctor"):
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        hospital = get_request_hospital(request)
        if not hospital and request.user.role == "super_admin":
            hospital = patient.registered_at
        if not hospital:
            return Response(
                {"message": "No facility assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        data = request.data
        encounter_type = (data.get("encounter_type") or "outpatient").strip()
        if encounter_type not in ("outpatient", "inpatient", "emergency", "follow_up", "consultation", "other"):
            encounter_type = "outpatient"
        notes = (data.get("notes") or "").strip() or None
        status_val = (data.get("status") or "waiting").strip()
        if status_val not in ("waiting", "in_consultation", "completed"):
            status_val = "waiting"
        visit_status_val = (data.get("visit_status") or "registered").strip()
        if visit_status_val not in ("registered", "waiting_triage", "waiting_doctor", "in_consultation", "sent_to_lab", "admitted", "discharged"):
            visit_status_val = "registered"
        chief_complaint = (data.get("chief_complaint") or "").strip() or None
        hpi = (data.get("hpi") or "").strip() or None
        examination_findings = (data.get("examination_findings") or "").strip() or None
        assessment_plan = (data.get("assessment_plan") or "").strip() or None
        discharge_summary = (data.get("discharge_summary") or "").strip() or None
        assigned_department = None
        dep_id = data.get("assigned_department_id")
        if dep_id:
            assigned_department = Department.objects.filter(
                id=dep_id, hospital=hospital
            ).first()
        assigned_doctor = None
        doc_id = data.get("assigned_doctor_id")
        if doc_id:
            assigned_doctor = User.objects.filter(
                id=doc_id, hospital=hospital, role="doctor"
            ).first()
        encounter = Encounter.objects.create(
            patient=patient,
            hospital=hospital,
            encounter_type=encounter_type,
            notes=notes,
            created_by=request.user,
            assigned_department=assigned_department,
            assigned_doctor=assigned_doctor,
            status=status_val,
            visit_status=visit_status_val,
            chief_complaint=chief_complaint,
            hpi=hpi,
            examination_findings=examination_findings,
            assessment_plan=assessment_plan,
            discharge_summary=discharge_summary,
        )
        return Response(
            {
                "id": str(encounter.id),
                "encounter_type": encounter.encounter_type,
                "encounter_date": encounter.encounter_date.isoformat(),
                "notes": encounter.notes,
                "assigned_department_id": str(encounter.assigned_department_id) if encounter.assigned_department_id else None,
                "assigned_doctor_id": str(encounter.assigned_doctor_id) if encounter.assigned_doctor_id else None,
                "status": encounter.status,
                "visit_status": encounter.visit_status,
                "chief_complaint": encounter.chief_complaint,
                "hpi": encounter.hpi,
                "examination_findings": encounter.examination_findings,
                "assessment_plan": encounter.assessment_plan,
                "discharge_summary": encounter.discharge_summary,
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def worklist_encounters(request):
    """Doctor/nurse worklist: encounters waiting or in consultation for my department or assigned to me."""
    if request.user.role not in ("doctor", "nurse", "hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    if not get_request_hospital(request) and request.user.role != "super_admin":
        return Response({"data": []})
    from api.utils import get_worklist_encounter_queryset
    qs = get_worklist_encounter_queryset(request.user, get_effective_hospital(request))
    department_id = (request.GET.get("department_id") or "").strip()
    encounter_type = (request.GET.get("encounter_type") or "").strip()
    if department_id:
        qs = qs.filter(assigned_department_id=department_id)
    if encounter_type:
        qs = qs.filter(encounter_type=encounter_type)

    patient_ids = list(qs.values_list("patient_id", flat=True))
    allergy_patient_ids = set()
    pending_labs_by_patient: dict = {}
    pending_rx_by_patient: dict = {}
    active_alerts_by_patient: dict = {}
    allergy_patient_ids_str = set()
    if patient_ids:
        allergy_patient_ids = set(
            Allergy.objects.filter(patient_id__in=patient_ids, is_active=True).values_list("patient_id", flat=True)
        )
        allergy_patient_ids_str = {str(x) for x in allergy_patient_ids}
        pending_labs_by_patient = {
            str(row["record__patient_id"]): row["count"]
            for row in (
                LabOrder.objects.filter(
                    record__patient_id__in=patient_ids,
                    status__in=("ordered", "in_progress"),
                )
                .values("record__patient_id")
                .annotate(count=Count("id"))
            )
        }
        pending_rx_by_patient = {
            str(row["record__patient_id"]): row["count"]
            for row in (
                Prescription.objects.filter(
                    record__patient_id__in=patient_ids,
                    dispense_status="pending",
                )
                .values("record__patient_id")
                .annotate(count=Count("id"))
            )
        }
        active_alerts_by_patient = {
            str(row["patient_id"]): row["count"]
            for row in (
                ClinicalAlert.objects.filter(patient_id__in=patient_ids, status="active")
                .values("patient_id")
                .annotate(count=Count("id"))
            )
        }
    page, next_cursor, has_more = paginate_queryset(qs, request, page_size=50, max_page_size=200)
    data = [
        {
            "id": str(e.id),
            "patient_id": str(e.patient_id),
            "patient_name": e.patient.full_name,
            "ghana_health_id": e.patient.ghana_health_id,
            "encounter_type": e.encounter_type,
            "encounter_date": e.encounter_date.isoformat(),
            "status": e.status,
            "visit_status": e.visit_status,
            "assigned_department_id": str(e.assigned_department_id) if e.assigned_department_id else None,
            "assigned_department_name": e.assigned_department.name if e.assigned_department else None,
            "assigned_doctor_id": str(e.assigned_doctor_id) if e.assigned_doctor_id else None,
            "assigned_doctor_name": e.assigned_doctor.full_name if e.assigned_doctor else None,
            "created_by": e.created_by.full_name if e.created_by else None,
            "notes": e.notes,
            "has_active_allergy": str(e.patient_id) in allergy_patient_ids_str,
            "triage_badge": "consulting" if e.status == "in_consultation" else "waiting",
            "pending_labs": int(pending_labs_by_patient.get(str(e.patient_id), 0)),
            "pending_prescriptions": int(pending_rx_by_patient.get(str(e.patient_id), 0)),
            "active_alerts": int(active_alerts_by_patient.get(str(e.patient_id), 0)),
        }
        for e in page
    ]
    summary = {
        "queue_count": qs.count(),
        "pending_labs": sum(pending_labs_by_patient.values()) if pending_labs_by_patient else 0,
        "pending_prescriptions": sum(pending_rx_by_patient.values()) if pending_rx_by_patient else 0,
        "alerts": sum(active_alerts_by_patient.values()) if active_alerts_by_patient else 0,
        "referrals": 0,
    }
    return Response({"data": data, "summary": summary, "next_cursor": next_cursor, "has_more": has_more})


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def encounter_detail(request, patient_pk, encounter_id):
    """Get or update a single encounter (consultation note, visit status)."""
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.user.role not in ("super_admin", "hospital_admin", "doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    encounter = (
        get_encounter_queryset(request.user, patient=patient)
        .filter(id=encounter_id)
        .select_related("created_by", "assigned_department", "assigned_doctor")
        .first()
    )
    if not encounter:
        return Response(
            {"message": "Encounter not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if request.method == "GET":
        return Response(
            {
                "id": str(encounter.id),
                "encounter_type": encounter.encounter_type,
                "encounter_date": encounter.encounter_date.isoformat(),
                "notes": encounter.notes,
                "created_by": encounter.created_by.full_name,
                "assigned_department_id": str(encounter.assigned_department_id) if encounter.assigned_department_id else None,
                "assigned_department_name": encounter.assigned_department.name if encounter.assigned_department else None,
                "assigned_doctor_id": str(encounter.assigned_doctor_id) if encounter.assigned_doctor_id else None,
                "assigned_doctor_name": encounter.assigned_doctor.full_name if encounter.assigned_doctor else None,
                "status": encounter.status,
                "visit_status": encounter.visit_status,
                "chief_complaint": encounter.chief_complaint,
                "hpi": encounter.hpi,
                "examination_findings": encounter.examination_findings,
                "assessment_plan": encounter.assessment_plan,
                "discharge_summary": encounter.discharge_summary,
            }
        )
    if request.method == "PATCH":
        data = request.data
        update_fields = []
        if "status" in data:
            v = (data["status"] or "").strip()
            if v in ("waiting", "in_consultation", "completed"):
                encounter.status = v
                update_fields.append("status")
        if "visit_status" in data:
            v = (data["visit_status"] or "").strip()
            if v in ("registered", "waiting_triage", "waiting_doctor", "in_consultation", "sent_to_lab", "admitted", "discharged"):
                encounter.visit_status = v
                update_fields.append("visit_status")
        if "chief_complaint" in data:
            encounter.chief_complaint = (data["chief_complaint"] or "").strip() or None
            update_fields.append("chief_complaint")
        if "hpi" in data:
            encounter.hpi = (data["hpi"] or "").strip() or None
            update_fields.append("hpi")
        if "examination_findings" in data:
            encounter.examination_findings = (data["examination_findings"] or "").strip() or None
            update_fields.append("examination_findings")
        if "assessment_plan" in data:
            encounter.assessment_plan = (data["assessment_plan"] or "").strip() or None
            update_fields.append("assessment_plan")
        if "discharge_summary" in data:
            encounter.discharge_summary = (data["discharge_summary"] or "").strip() or None
            update_fields.append("discharge_summary")
        if "notes" in data:
            encounter.notes = (data["notes"] or "").strip() or None
            update_fields.append("notes")
        if "assigned_doctor_id" in data:
            doc_id = data.get("assigned_doctor_id")
            if encounter.hospital_id:
                from core.models import User
                new_doctor = User.objects.filter(id=doc_id, hospital=encounter.hospital, role="doctor").first() if doc_id else None
                encounter.assigned_doctor = new_doctor
                update_fields.append("assigned_doctor_id")
        if update_fields:
            encounter.save(update_fields=update_fields)
        return Response(
            {
                "id": str(encounter.id),
                "status": encounter.status,
                "visit_status": encounter.visit_status,
                "chief_complaint": encounter.chief_complaint,
                "hpi": encounter.hpi,
                "examination_findings": encounter.examination_findings,
                "assessment_plan": encounter.assessment_plan,
                "discharge_summary": encounter.discharge_summary,
            }
        )
    return Response(status=status.HTTP_405_METHOD_NOT_ALLOWED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def close_encounter(request, patient_pk, encounter_id):
    """Explicit close action with lightweight confirmation contract."""
    if request.user.role not in ("doctor", "hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_pk).first()
    if not patient:
        return Response({"message": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
    encounter = (
        get_encounter_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request))
        .filter(id=encounter_id)
        .first()
    )
    if not encounter:
        return Response({"message": "Encounter not found"}, status=status.HTTP_404_NOT_FOUND)
    if encounter.status == "completed":
        return Response(
            {"message": "Encounter already closed", "id": str(encounter.id), "status": encounter.status, "visit_status": encounter.visit_status}
        )
    confirmation = request.data.get("confirmation_items")
    if confirmation is not None and not isinstance(confirmation, list):
        return Response({"message": "confirmation_items must be a list"}, status=status.HTTP_400_BAD_REQUEST)
    encounter.status = "completed"
    if encounter.visit_status in ("registered", "waiting_triage", "waiting_doctor", "in_consultation"):
        encounter.visit_status = "discharged"
    encounter.save(update_fields=["status", "visit_status"])
    return Response(
        {
            "id": str(encounter.id),
            "status": encounter.status,
            "visit_status": encounter.visit_status,
            "closed": True,
            "confirmation_items": confirmation or [],
        }
    )
