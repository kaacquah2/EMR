from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from django.db.models import Count

from core.models import Department, User
from patients.models import Allergy, ClinicalAlert
from records.models import Encounter
from records.models import LabOrder, Prescription
from interop.models import Referral
from api.utils import get_patient_queryset, get_encounter_queryset, get_effective_hospital, get_request_hospital
from api.pagination import paginate_queryset
from api.state_machines import validate_visit_status_transition, StateMachineError
from api.serializers import EncounterSerializer, EncounterWorklistSerializer


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
        page, next_cursor, has_more = paginate_queryset(qs, request, page_size=20, max_page_size=100, use_cursor=True)
        data = EncounterSerializer(page, many=True).data
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
        if visit_status_val not in (
            "registered",
            "waiting_triage",
            "waiting_doctor",
            "in_consultation",
            "sent_to_lab",
            "admitted",
                "discharged"):
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
            {"data": EncounterSerializer(encounter).data},
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
    
    # Inject dynamic fields for EncounterWorklistSerializer
    for e in page:
        e.has_active_allergy = str(e.patient_id) in allergy_patient_ids_str
        e.pending_labs = int(pending_labs_by_patient.get(str(e.patient_id), 0))
        e.pending_prescriptions = int(pending_rx_by_patient.get(str(e.patient_id), 0))
        e.active_alerts = int(active_alerts_by_patient.get(str(e.patient_id), 0))

    data = EncounterWorklistSerializer(page, many=True).data
    # Query actual referral count for the requesting doctor's facility
    hospital = get_effective_hospital(request)
    referral_count = 0
    if hospital:
        referral_count = Referral.objects.filter(
            to_facility=hospital,
            status__in=[Referral.STATUS_PENDING, Referral.STATUS_ACCEPTED]
        ).count()
    
    summary = {
        "queue_count": qs.count(),
        "pending_labs": sum(pending_labs_by_patient.values()) if pending_labs_by_patient else 0,
        "pending_prescriptions": sum(pending_rx_by_patient.values()) if pending_rx_by_patient else 0,
        "alerts": sum(active_alerts_by_patient.values()) if active_alerts_by_patient else 0,
        "referrals": referral_count,
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
        return Response({"data": EncounterSerializer(encounter).data})
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
            if v in (
                "registered",
                "waiting_triage",
                "waiting_doctor",
                "in_consultation",
                "sent_to_lab",
                "admitted",
                    "discharged"):
                # Validate state transition
                try:
                    validate_visit_status_transition(encounter.visit_status, v)
                except StateMachineError as e:
                    return Response(
                        {"message": str(e)},
                        status=status.HTTP_400_BAD_REQUEST
                    )
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
                new_doctor = User.objects.filter(id=doc_id, hospital=encounter.hospital,
                                                 role="doctor").first() if doc_id else None
                encounter.assigned_doctor = new_doctor
                update_fields.append("assigned_doctor_id")
        if update_fields:
            encounter.save(update_fields=update_fields)
        return Response({"data": EncounterSerializer(encounter).data})
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
        return Response({"message": "Encounter already closed", "id": str(encounter.id),
                         "status": encounter.status, "visit_status": encounter.visit_status})
    confirmation = request.data.get("confirmation_items")
    if confirmation is not None and not isinstance(confirmation, list):
        return Response({"message": "confirmation_items must be a list"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate visit_status transition to discharged
    if encounter.visit_status in ("registered", "waiting_triage", "waiting_doctor", "in_consultation"):
        try:
            validate_visit_status_transition(encounter.visit_status, "discharged")
        except StateMachineError as e:
            return Response(
                {"message": str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
        encounter.visit_status = "discharged"
    
    encounter.status = "completed"
    encounter.save()
    return Response(
        {
            "data": EncounterSerializer(encounter).data,
            "confirmation_items": confirmation or [],
        }
    )


@api_view(["PATCH", "GET", "DELETE"])
@permission_classes([IsAuthenticated])
def encounter_draft_handler(request, pk, encounter_id=None):
    """
    Handle SOAP encounter draft auto-save.

    PATCH: Save/update draft (called every 30s from frontend)
    GET: Retrieve current draft
    DELETE: Clear draft (called on encounter close)
    """
    from api.serializers import EncounterDraftCreateUpdateSerializer, EncounterDraftSerializer
    from records.models import EncounterDraft

    # Permission: Only doctor, hospital_admin, super_admin can work with encounters
    if request.user.role not in ("doctor", "hospital_admin", "super_admin"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    effective_hospital = get_effective_hospital(request)
    patient_pk = pk  # Rename for clarity

    # Verify patient access
    patient = get_patient_queryset(request.user, effective_hospital).filter(id=patient_pk).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Use patient's hospital for draft (patient has definitive hospital affiliation)
    hospital = patient.registered_at

    # For encounter-scoped operations, verify encounter access
    encounter = None
    if encounter_id:
        encounter = (
            get_encounter_queryset(request.user, patient=patient, effective_hospital=effective_hospital)
            .filter(id=encounter_id)
            .first()
        )
        if not encounter:
            return Response(
                {"message": "Encounter not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Get or create draft
    if encounter:
        draft, created = EncounterDraft.objects.get_or_create(
            encounter=encounter,
            defaults={
                "patient": patient,
                "hospital": hospital,
                "created_by": request.user,
            },
        )
    else:
        # Patient-scoped draft (no specific encounter yet)
        draft = EncounterDraft.objects.filter(
            patient=patient,
            hospital=hospital,
            encounter__isnull=True,
        ).first()
        if not draft and request.method in ["PATCH"]:
            draft = EncounterDraft.objects.create(
                patient=patient,
                hospital=hospital,
                created_by=request.user,
            )

    if request.method == "PATCH":
        if not draft:
            return Response(
                {"message": "Cannot create draft for this patient"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = EncounterDraftCreateUpdateSerializer(draft, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        serializer.save()
        return Response(
            EncounterDraftSerializer(draft).data,
            status=status.HTTP_200_OK,
        )

    elif request.method == "GET":
        if not draft:
            return Response(
                {"message": "No draft found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            EncounterDraftSerializer(draft).data,
            status=status.HTTP_200_OK,
        )

    elif request.method == "DELETE":
        if not draft:
            return Response(
                {"message": "No draft to delete"},
                status=status.HTTP_404_NOT_FOUND,
            )
        draft.delete()
        return Response(
            {"message": "Draft deleted successfully"},
            status=status.HTTP_204_NO_CONTENT,
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def encounter_template_list(request):
    """
    GET: List templates (personal + shared for user's hospital)
    POST: Create new template
    """
    from records.models import EncounterTemplate
    from django.db import models as dj_models
    from api.utils import audit_log
    
    if request.user.role not in ('doctor', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'message': 'No hospital assigned'}, status=status.HTTP_400_BAD_REQUEST)
    
    if request.method == 'GET':
        template_type = request.query_params.get('type')  # 'personal' or 'shared'
        
        qs = EncounterTemplate.objects.filter(
            hospital=hospital,
            is_active=True,
        )
        
        if template_type == 'personal':
            qs = qs.filter(created_by=request.user, template_type='personal')
        elif template_type == 'shared':
            qs = qs.filter(template_type='shared')
        else:
            # Return both personal and shared
            qs = qs.filter(
                dj_models.Q(created_by=request.user, template_type='personal') |
                dj_models.Q(template_type='shared')
            )
        
        data = [{
            'id': str(t.id),
            'name': t.name,
            'description': t.description,
            'template_type': t.template_type,
            'specialty': t.specialty,
            'encounter_type': t.encounter_type,
            'usage_count': t.usage_count,
            'created_by': t.created_by.full_name,
            'created_at': t.created_at.isoformat(),
        } for t in qs]
        
        return Response({'data': data})
    
    elif request.method == 'POST':
        data = request.data
        
        template = EncounterTemplate.objects.create(
            name=data.get('name', 'Untitled Template'),
            description=data.get('description', ''),
            template_type=data.get('template_type', 'personal'),
            created_by=request.user,
            hospital=hospital,
            chief_complaint_template=data.get('chief_complaint_template', ''),
            hpi_template=data.get('hpi_template', ''),
            examination_template=data.get('examination_template', ''),
            assessment_template=data.get('assessment_template', ''),
            default_diagnoses=data.get('default_diagnoses', []),
            default_prescriptions=data.get('default_prescriptions', []),
            specialty=data.get('specialty', ''),
            encounter_type=data.get('encounter_type', ''),
        )
        
        audit_log(request.user, 'CREATE', 'EncounterTemplate', str(template.id), hospital, request)
        
        return Response({
            'id': str(template.id),
            'message': 'Template created successfully',
        }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
@permission_classes([IsAuthenticated])
def encounter_template_detail(request, template_id):
    """
    GET: Get template details
    PUT: Update template
    DELETE: Delete template
    """
    from records.models import EncounterTemplate
    from api.utils import audit_log
    
    if request.user.role not in ('doctor', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'message': 'No hospital assigned'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        template = EncounterTemplate.objects.get(id=template_id, hospital=hospital, is_active=True)
    except EncounterTemplate.DoesNotExist:
        return Response({'message': 'Template not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Only owner can modify personal templates; admins can modify shared
    if template.template_type == 'personal' and template.created_by != request.user and request.user.role != 'super_admin':
        return Response({'message': 'Cannot modify another user\'s personal template'}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        return Response({
            'id': str(template.id),
            'name': template.name,
            'description': template.description,
            'template_type': template.template_type,
            'chief_complaint_template': template.chief_complaint_template,
            'hpi_template': template.hpi_template,
            'examination_template': template.examination_template,
            'assessment_template': template.assessment_template,
            'default_diagnoses': template.default_diagnoses,
            'default_prescriptions': template.default_prescriptions,
            'specialty': template.specialty,
            'encounter_type': template.encounter_type,
            'usage_count': template.usage_count,
            'created_by': template.created_by.full_name,
            'created_at': template.created_at.isoformat(),
        })
    
    elif request.method == 'PUT':
        data = request.data
        for field in ['name', 'description', 'chief_complaint_template', 'hpi_template',
                      'examination_template', 'assessment_template', 'specialty', 'encounter_type']:
            if field in data:
                setattr(template, field, data[field])
        
        if 'default_diagnoses' in data:
            template.default_diagnoses = data['default_diagnoses']
        if 'default_prescriptions' in data:
            template.default_prescriptions = data['default_prescriptions']
        
        template.save()
        audit_log(request.user, 'UPDATE', 'EncounterTemplate', str(template.id), hospital, request)
        
        return Response({'message': 'Template updated'})
    
    elif request.method == 'DELETE':
        template.is_active = False
        template.save()
        audit_log(request.user, 'DELETE', 'EncounterTemplate', str(template.id), hospital, request)
        
        return Response({'message': 'Template deleted'})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def apply_encounter_template(request, patient_pk, encounter_id, template_id):
    """
    Apply a template to an encounter.
    Populates SOAP fields from template.
    """
    from records.models import EncounterTemplate
    from api.utils import audit_log
    
    if request.user.role not in ('doctor', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'message': 'No hospital assigned'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get patient
    patient = get_patient_queryset(request.user, hospital).filter(id=patient_pk).first()
    if not patient:
        return Response({'message': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get encounter
    encounter = (
        get_encounter_queryset(request.user, patient=patient, effective_hospital=hospital)
        .filter(id=encounter_id)
        .first()
    )
    if not encounter:
        return Response({'message': 'Encounter not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get template
    try:
        template = EncounterTemplate.objects.get(id=template_id, hospital=hospital, is_active=True)
    except EncounterTemplate.DoesNotExist:
        return Response({'message': 'Template not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Apply template content (only if encounter fields are empty)
    if not encounter.chief_complaint and template.chief_complaint_template:
        encounter.chief_complaint = template.chief_complaint_template
    if not encounter.hpi and template.hpi_template:
        encounter.hpi = template.hpi_template
    if not encounter.examination_findings and template.examination_template:
        encounter.examination_findings = template.examination_template
    if not encounter.assessment_plan and template.assessment_template:
        encounter.assessment_plan = template.assessment_template
    
    encounter.save()
    
    # Increment usage count
    template.usage_count += 1
    template.save(update_fields=['usage_count'])
    
    audit_log(request.user, 'TEMPLATE_APPLIED', 'Encounter', str(encounter.id), hospital, request, extra_data={'template_id': str(template_id)})
    
    return Response({
        'message': 'Template applied successfully',
        'encounter': {
            'chief_complaint': encounter.chief_complaint,
            'hpi': encounter.hpi,
            'examination_findings': encounter.examination_findings,
            'assessment_plan': encounter.assessment_plan,
        }
    })
