from datetime import timedelta
from django.db.models import Max
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from patients.models import ClinicalAlert, PatientAdmission
from records.models import MedicalRecord, NurseShift, Prescription, NursingNote
from api.utils import get_effective_hospital, get_request_hospital, audit_log


def _nurse_context_or_403(request):
    if request.user.role != "nurse":
        return None, Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    hospital = get_request_hospital(request)
    if not hospital:
        return None, Response({"message": "No facility assigned"}, status=status.HTTP_400_BAD_REQUEST)
    ward = request.user.ward
    if not ward:
        return None, Response({"message": "Nurse has no ward assignment"}, status=status.HTTP_403_FORBIDDEN)
    return {"hospital": hospital, "ward": ward}, None


def _active_shift(request, hospital, ward):
    return (
        NurseShift.objects.filter(
            nurse=request.user,
            hospital=hospital,
            ward=ward,
            status__in=("active", "on_break"),
        )
        .order_by("-shift_start")
        .first()
    )


def _build_shift_payload(shift):
    if not shift:
        return {"status": "not_started"}
    now = timezone.now()
    shift_end_target = (shift.shift_start + timedelta(hours=8))
    remaining_secs = max(0, int((shift_end_target - now).total_seconds()))
    return {
        "shift_id": str(shift.id),
        "status": shift.status,
        "started_at": shift.shift_start.isoformat(),
        "break_start": shift.break_start.isoformat() if shift.break_start else None,
        "break_end": shift.break_end.isoformat() if shift.break_end else None,
        "remaining_seconds": remaining_secs,
    }


# PHASE 6: Nurse Advanced Features

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nurse_shift_start(request):
    """Start a nursing shift.
    
    Request body:
    {
        "ward_id": "uuid",
        "bed_assignments": ["patient_id1", "patient_id2", ...] (optional)
    }
    
    Returns:
    {
        "shift_id": "uuid",
        "status": "active",
        "started_at": "2024-01-15T08:00:00Z",
        "ward_id": "uuid",
        "ward_name": "ICU",
        "assigned_patients": 12,
        "pending_vitals": 5,
        "pending_medications": 3
    }
    """
    ctx, err = _nurse_context_or_403(request)
    if err:
        return err
    hospital = ctx["hospital"]
    ward = ctx["ward"]
    shift = NurseShift.objects.filter(
        nurse=request.user,
        ward=ward,
        hospital=hospital,
        shift_start__date=timezone.now().date(),
    ).first()
    created = shift is None
    if created:
        shift = NurseShift.objects.create(
            nurse=request.user,
            ward=ward,
            hospital=hospital,
            shift_start=timezone.now(),
            status="active",
        )
    
    if not created:
        shift.status = "active"
        shift.shift_start = timezone.now()
        shift.save(update_fields=["status", "shift_start"])
    
    # Get assigned patients and pending tasks
    admissions = PatientAdmission.objects.filter(
        ward=ward,
        hospital=hospital,
        discharged_at__isnull=True,
    ).select_related("patient")
    
    assigned_patients = admissions.count()
    
    # Count pending vitals (vitals not recorded in last 4 hours)
    pending_vitals = 0
    for admission in admissions:
        recent_vital = MedicalRecord.objects.filter(
            patient=admission.patient,
            record_type="vital_signs",
            created_at__gte=timezone.now() - timedelta(hours=4)
        ).exists()
        if not recent_vital:
            pending_vitals += 1
    
    # Count pending medications (not dispensed)
    pending_meds = 0
    for admission in admissions:
        pending_meds += MedicalRecord.objects.filter(
            patient=admission.patient,
            record_type="prescription",
        ).filter(
            prescription__dispense_status="pending"
        ).count()
    
    audit_log(
        request.user,
        "NURSE_SHIFT_START",
        "shift",
        str(shift.id),
        hospital,
        request,
    )
    
    return Response({
        "shift_id": str(shift.id),
        "status": shift.status,
        "started_at": shift.shift_start.isoformat(),
        "ward_id": str(ward.id),
        "ward_name": ward.ward_name,
        "assigned_patients": assigned_patients,
        "pending_vitals": pending_vitals,
        "pending_medications": pending_meds,
    }, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def nurse_dashboard(request):
    """Nurse dashboard payload with ward-scoped stats and priority rows."""
    ctx, err = _nurse_context_or_403(request)
    if err:
        return err
    hospital = ctx["hospital"]
    ward = ctx["ward"]

    admissions = (
        PatientAdmission.objects.filter(
            hospital=hospital,
            ward=ward,
            discharged_at__isnull=True,
        )
        .select_related("patient", "bed")
    )
    admitted_count = admissions.count()
    patient_ids = list(admissions.values_list("patient_id", flat=True))
    cutoff = timezone.now() - timedelta(hours=4)

    latest_vitals = {
        row["patient_id"]: row["last"]
        for row in (
            MedicalRecord.objects.filter(
                patient_id__in=patient_ids,
                record_type="vital_signs",
            )
            .values("patient_id")
            .annotate(last=Max("created_at"))
        )
    } if patient_ids else {}

    vitals_due = []
    for admission in admissions:
        last_ts = latest_vitals.get(admission.patient_id)
        if not last_ts or last_ts < cutoff:
            vitals_due.append(admission)

    pending_rx = (
        Prescription.objects.filter(
            record__patient_id__in=patient_ids,
            dispense_status="pending",
        )
        .select_related("record__patient")
        .order_by("record__created_at")
    ) if patient_ids else Prescription.objects.none()

    active_critical = set(
        ClinicalAlert.objects.filter(
            patient_id__in=patient_ids,
            status="active",
            severity="critical",
        ).values_list("patient_id", flat=True)
    ) if patient_ids else set()

    priority_rows = []
    for admission in vitals_due[:6]:
        bed_code = admission.bed.bed_code if admission.bed else "Unassigned"
        priority_rows.append({
            "type": "VITALS_DUE",
            "patient_id": str(admission.patient_id),
            "patient_name": admission.patient.full_name,
            "bed_code": bed_code,
            "last_recorded": latest_vitals.get(admission.patient_id).isoformat() if latest_vitals.get(admission.patient_id) else None,
        })
    for rx in list(pending_rx[:6]):
        patient = rx.record.patient
        admission = next((a for a in vitals_due + list(admissions) if a.patient_id == patient.id), None)
        bed_code = admission.bed.bed_code if admission and admission.bed else "Unassigned"
        priority_rows.append({
            "type": "DISPENSE",
            "record_id": str(rx.record_id),
            "patient_id": str(patient.id),
            "patient_name": patient.full_name,
            "bed_code": bed_code,
            "drug_name": rx.drug_name,
            "allergy_conflict": bool(rx.allergy_conflict),
            "allergy_override_reason": rx.allergy_override_reason,
            "written_at": rx.record.created_at.isoformat(),
        })

    shift = _active_shift(request, hospital, ward)
    current_shift = "Morning"
    now_h = timezone.localtime().hour
    if now_h >= 15 and now_h < 23:
        current_shift = "Evening"
    elif now_h >= 23 or now_h < 7:
        current_shift = "Night"

    return Response({
        "ward_id": str(ward.id),
        "ward_name": ward.ward_name,
        "admitted_count": admitted_count,
        "vitals_overdue_count": len(vitals_due),
        "pending_dispense_count": pending_rx.count(),
        "current_shift": current_shift,
        "shift": _build_shift_payload(shift),
        "priority_worklist": priority_rows[:10],
        "critical_patients_count": len(active_critical),
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def nurse_worklist(request):
    """Ward bed-grid plus dispense and handover data."""
    ctx, err = _nurse_context_or_403(request)
    if err:
        return err
    hospital = ctx["hospital"]
    ward = ctx["ward"]
    from core.models import Bed, User

    admissions = list(
        PatientAdmission.objects.filter(
            hospital=hospital,
            ward=ward,
            discharged_at__isnull=True,
        ).select_related("patient", "bed")
    )
    patient_ids = [a.patient_id for a in admissions]
    cutoff = timezone.now() - timedelta(hours=4)
    latest_vitals = {
        row["patient_id"]: row["last"]
        for row in (
            MedicalRecord.objects.filter(
                patient_id__in=patient_ids,
                record_type="vital_signs",
            )
            .values("patient_id")
            .annotate(last=Max("created_at"))
        )
    } if patient_ids else {}
    critical_ids = set(
        ClinicalAlert.objects.filter(
            patient_id__in=patient_ids,
            status="active",
            severity="critical",
        ).values_list("patient_id", flat=True)
    ) if patient_ids else set()

    admission_by_bed = {a.bed_id: a for a in admissions if a.bed_id}
    beds = Bed.objects.filter(ward=ward, is_active=True).order_by("bed_code")
    bed_cards = []
    for bed in beds:
        admission = admission_by_bed.get(bed.id)
        if not admission:
            bed_cards.append({"bed_id": str(bed.id), "bed_code": bed.bed_code, "status": "available"})
            continue
        last_ts = latest_vitals.get(admission.patient_id)
        status_key = "stable"
        if admission.patient_id in critical_ids:
            status_key = "critical"
        elif not last_ts or last_ts < cutoff:
            status_key = "watch"
        bed_cards.append({
            "bed_id": str(bed.id),
            "bed_code": bed.bed_code,
            "status": status_key,
            "patient_id": str(admission.patient_id),
            "patient_name": admission.patient.full_name,
            "admitted_at": admission.admitted_at.isoformat(),
            "admitted_for": "General Medicine",
            "last_vitals_at": last_ts.isoformat() if last_ts else None,
            "vitals_due": (not last_ts or last_ts < cutoff),
        })

    dispense_items = []
    pending_rx = (
        Prescription.objects.filter(
            record__patient_id__in=patient_ids,
            dispense_status="pending",
        )
        .select_related("record__patient", "record__created_by")
        .order_by("record__created_at")
    ) if patient_ids else []
    for rx in pending_rx:
        admission = next((a for a in admissions if a.patient_id == rx.record.patient_id), None)
        dispense_items.append({
            "record_id": str(rx.record_id),
            "patient_id": str(rx.record.patient_id),
            "patient_name": rx.record.patient.full_name,
            "bed_code": admission.bed.bed_code if admission and admission.bed else None,
            "drug_name": rx.drug_name,
            "dosage": rx.dosage,
            "frequency": rx.frequency,
            "route": rx.route,
            "written_by": rx.record.created_by.full_name if rx.record.created_by else None,
            "written_at": rx.record.created_at.isoformat(),
            "allergy_conflict": bool(rx.allergy_conflict),
            "allergy_override_reason": rx.allergy_override_reason,
        })

    incoming_candidates = list(
        User.objects.filter(hospital=hospital, role="nurse", account_status="active")
        .exclude(id=request.user.id)
        .values("id", "full_name")
    )
    handovers_pending_ack = list(
        NursingNote.objects.filter(
            record__hospital=hospital,
            note_type="handover",
            incoming_nurse=request.user,
            acknowledged_at__isnull=True,
        )
        .select_related("record__patient", "record__created_by")
        .order_by("-outgoing_signed_at")[:20]
    )
    handover_queue = [
        {
            "note_id": str(note.id),
            "record_id": str(note.record_id),
            "patient_id": str(note.record.patient_id),
            "patient_name": note.record.patient.full_name,
            "outgoing_nurse_name": note.record.created_by.full_name if note.record.created_by else None,
            "content": note.content,
            "signed_at": note.outgoing_signed_at.isoformat() if note.outgoing_signed_at else None,
        }
        for note in handovers_pending_ack
    ]

    return Response({
        "ward_id": str(ward.id),
        "ward_name": ward.ward_name,
        "beds": bed_cards,
        "dispense_items": dispense_items,
        "incoming_nurse_candidates": [
            {"user_id": str(item["id"]), "full_name": item["full_name"]} for item in incoming_candidates
        ],
        "handover_pending_ack": handover_queue,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nurse_shift_break_toggle(request):
    ctx, err = _nurse_context_or_403(request)
    if err:
        return err
    shift = _active_shift(request, ctx["hospital"], ctx["ward"])
    if not shift:
        return Response({"message": "No active shift"}, status=status.HTTP_400_BAD_REQUEST)
    if shift.status == "on_break":
        shift.status = "active"
        shift.break_end = timezone.now()
        shift.save(update_fields=["status", "break_end"])
    else:
        shift.status = "on_break"
        shift.break_start = timezone.now()
        shift.save(update_fields=["status", "break_start"])
    return Response(_build_shift_payload(shift))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nurse_shift_end(request):
    ctx, err = _nurse_context_or_403(request)
    if err:
        return err
    shift = _active_shift(request, ctx["hospital"], ctx["ward"])
    if not shift:
        return Response({"message": "No active shift"}, status=status.HTTP_400_BAD_REQUEST)
    shift.status = "completed"
    shift.shift_end = timezone.now()
    shift.save(update_fields=["status", "shift_end"])
    return Response({"shift_id": str(shift.id), "status": shift.status, "ended_at": shift.shift_end.isoformat()})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nurse_shift_handover(request, shift_id):
    """Submit shift handover notes with summary of activities.
    
    Request body:
    {
        "handover_notes": "All vitals recorded. 2 patients admitted, 1 discharged...",
        "critical_alerts": ["patient_id1", "patient_id2"],  (optional)
        "pending_orders": [{"patient_id": "uuid", "order_type": "lab", "details": "..."}],  (optional)
        "medications_given": [
            {"patient_id": "uuid", "medication": "Paracetamol", "dosage": "500mg", "route": "PO"}
        ]  (optional)
    }
    
    Returns:
    {
        "handover_id": "uuid",
        "status": "submitted",
        "submitted_at": "2024-01-15T16:00:00Z",
        "shift_id": "uuid",
        "summary": {...}
    }
    """
    ctx, err = _nurse_context_or_403(request)
    if err:
        return err
    hospital = ctx["hospital"]
    from records.models import ShiftHandover
    shift = NurseShift.objects.filter(
        id=shift_id,
        nurse=request.user,
        hospital=hospital
    ).first()
    
    if not shift:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    data = request.data
    handover_notes = (data.get("handover_notes") or "").strip()
    
    if not handover_notes:
        return Response(
            {"message": "handover_notes required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Create handover record
    handover = ShiftHandover.objects.create(
        shift=shift,
        nurse=request.user,
        hospital=hospital,
        handover_notes=handover_notes,
        submitted_at=timezone.now(),
    )
    
    # Store critical alerts
    critical_alerts = data.get("critical_alerts", [])
    if critical_alerts:
        from patients.models import Patient
        for patient_id in critical_alerts:
            try:
                patient = Patient.objects.get(id=patient_id, hospital=hospital)
                handover.critical_patients.add(patient)
            except Patient.DoesNotExist:
                pass
    
    # Close shift
    shift.status = "completed"
    shift.shift_end = timezone.now()
    shift.save(update_fields=["status", "shift_end"])
    
    audit_log(
        request.user,
        "NURSE_SHIFT_HANDOVER",
        "shift_handover",
        str(handover.id),
        hospital,
        request,
    )
    
    return Response({
        "handover_id": str(handover.id),
        "status": "submitted",
        "submitted_at": handover.submitted_at.isoformat(),
        "shift_id": str(shift.id),
        "summary": {
            "notes_length": len(handover_notes),
            "critical_patients": handover.critical_patients.count(),
        }
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def nurse_overdue_vitals(request):
    """Get list of patients with overdue vital signs.
    
    Query parameters:
    - ward_id: Filter by ward UUID (optional)
    - hours_threshold: Hours since last vital (default 4)
    - limit: Max results (default 50)
    
    Returns:
    {
        "count": 12,
        "overdue": [
            {
                "patient_id": "uuid",
                "patient_name": "John Doe",
                "ghana_health_id": "GHC-001",
                "last_vital_at": "2024-01-15T12:00:00Z",
                "hours_overdue": 3.5,
                "vital_types_needed": ["temperature", "blood_pressure", "heart_rate"],
                "ward": "ICU",
                "admission_id": "uuid",
                "priority": "high"
            },
            ...
        ]
    }
    """
    if request.user.role not in ("nurse", "hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    hours_threshold = int(request.GET.get("hours_threshold", "4") or "4")
    limit = min(int(request.GET.get("limit", "50") or "50"), 200)
    
    # Get active admissions
    admissions = PatientAdmission.objects.filter(
        hospital=hospital,
        discharged_at__isnull=True
    ).select_related("patient", "ward")
    
    if request.user.role == "nurse":
        admissions = admissions.filter(ward=request.user.ward)
    else:
        ward_id = request.GET.get("ward_id")
        if ward_id:
            admissions = admissions.filter(ward_id=ward_id)
    
    # Find overdue vitals
    cutoff_time = timezone.now() - timedelta(hours=hours_threshold)
    overdue_list = []
    
    for admission in admissions:
        # Check for recent vitals
        recent_vital = MedicalRecord.objects.filter(
            patient=admission.patient,
            record_type="vital_signs",
            created_at__gte=cutoff_time
        ).order_by("-created_at").first()
        
        if not recent_vital:
            # No vitals in threshold window
            last_vital = MedicalRecord.objects.filter(
                patient=admission.patient,
                record_type="vital_signs"
            ).order_by("-created_at").first()
            
            base_ts = last_vital.created_at if last_vital else admission.admitted_at
            hours_overdue = (timezone.now() - base_ts).total_seconds() / 3600
            
            overdue_list.append({
                "patient_id": str(admission.patient.id),
                "patient_name": admission.patient.full_name,
                "ghana_health_id": admission.patient.ghana_health_id,
                "last_vital_at": last_vital.created_at.isoformat() if last_vital else None,
                "hours_overdue": round(hours_overdue, 1),
                "vital_types_needed": ["temperature", "blood_pressure", "heart_rate", "respiratory_rate", "oxygen_saturation"],
                "ward": admission.ward.ward_name if admission.ward else "Unknown",
                "admission_id": str(admission.id),
                "priority": "critical" if hours_overdue > 8 else "high" if hours_overdue > 4 else "medium",
            })
    
    # Sort by hours_overdue (most overdue first)
    overdue_list.sort(key=lambda x: x["hours_overdue"], reverse=True)
    overdue_list = overdue_list[:limit]
    
    return Response({
        "count": len(overdue_list),
        "hours_threshold": hours_threshold,
        "overdue": overdue_list,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def nurse_handover_acknowledge(request, note_id):
    """Incoming nurse acknowledges a handover note."""
    if request.user.role != "nurse":
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    note = (
        NursingNote.objects.filter(
            id=note_id,
            note_type="handover",
            incoming_nurse=request.user,
        )
        .select_related("record__hospital", "record__patient")
        .first()
    )
    if not note:
        return Response({"message": "Handover note not found"}, status=status.HTTP_404_NOT_FOUND)
    if note.acknowledged_at:
        return Response({"status": "already_acknowledged", "acknowledged_at": note.acknowledged_at.isoformat()})
    note.acknowledged_by = request.user
    note.acknowledged_at = timezone.now()
    note.save(update_fields=["acknowledged_by", "acknowledged_at"])
    audit_log(
        request.user,
        "NURSE_HANDOVER_ACKNOWLEDGED",
        "nursing_note",
        str(note.record_id),
        note.record.hospital,
        request,
        extra_data={"note_id": str(note.id), "patient_id": str(note.record.patient_id)},
    )
    return Response({
        "status": "acknowledged",
        "note_id": str(note.id),
        "acknowledged_at": note.acknowledged_at.isoformat(),
    })
