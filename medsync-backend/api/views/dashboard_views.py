from django.utils import timezone
from django.utils.dateparse import parse_date
from django.db.models import Count, Q, Case, When, OuterRef, Subquery, DateTimeField
from django.db import connection
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from patients.models import Patient, PatientAdmission, ClinicalAlert, Appointment
from patients.models import Allergy
from records.models import Prescription, LabOrder, LabResult, Encounter, MedicalRecord
from interop.models import Referral
from core.models import User, Hospital, AuditLog, Bed
from api.utils import get_lab_order_queryset, get_lab_result_queryset, get_effective_hospital, get_request_hospital


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_metrics(request):
    user = request.user
    hospital = get_request_hospital(request)
    today = timezone.now().date()

    if user.role == "doctor":
        patients_today = Patient.objects.filter(
            registered_at=hospital,
            created_by=user,
            created_at__date=today,
        ).count()
        active_rx = Prescription.objects.filter(
            record__hospital=hospital,
            record__created_by=user,
            dispense_status="pending",
        ).count()
        pending_labs = LabOrder.objects.filter(
            record__hospital=hospital,
            record__created_by=user,
        ).count()
        new_results = LabResult.objects.filter(
            record__patient__registered_at=hospital,
            result_date__date=today,
            status="resulted",
        ).count()
        active_alerts = ClinicalAlert.objects.filter(hospital=hospital, status="active").count()
        encounters_today = Encounter.objects.filter(hospital=hospital, encounter_date__date=today).count()
        seven_days_ago = timezone.now() - timezone.timedelta(days=7)
        patients_with_life_threatening = set(
            Allergy.objects.filter(severity="life_threatening", is_active=True).values_list("patient_id", flat=True)
        )
        recent_record_patient_ids = set(
            MedicalRecord.objects.filter(
                hospital=hospital,
                created_at__gte=seven_days_ago,
            ).values_list("patient_id", flat=True)
        )
        allergy_alert_patient_ids = list(patients_with_life_threatening & recent_record_patient_ids)[:50]
        allergy_alert_patients = list(
            Patient.objects.filter(id__in=allergy_alert_patient_ids).values("id", "full_name", "ghana_health_id")
        ) if allergy_alert_patient_ids else []
        seen = []
        seen_set = set()
        for pid in (
            MedicalRecord.objects.filter(hospital=hospital, created_by=user)
            .order_by("-created_at")
            .values_list("patient_id", flat=True)
            .iterator(chunk_size=500)
        ):
            if pid not in seen_set:
                seen_set.add(pid)
                seen.append(pid)
            if len(seen) >= 10:
                break
        recent_patients = list(
            Patient.objects.filter(id__in=seen).values("id", "full_name", "ghana_health_id")
        ) if seen else []
        dashboard_payload = {
            "patients_today": patients_today,
            "active_prescriptions": active_rx,
            "pending_lab_orders": pending_labs,
            "new_results": new_results,
            "active_alerts": active_alerts,
            "encounters_today": encounters_today,
            "allergy_alert_patients": allergy_alert_patients,
            "recent_patients": recent_patients,
            # Spec-compatible aliases
            "queue_count": encounters_today,
            "new_lab_results": new_results,
            "critical_alerts": active_alerts,
            "pending_prescriptions": active_rx,
            "referrals_awaiting": (
                Referral.objects.filter(
                    to_facility=hospital,
                    status=Referral.STATUS_PENDING
                ).count()
                if hospital
                else 0
            ),
        }
        return Response(dashboard_payload)

    if user.role == "nurse":
        ward = user.ward
        if not ward:
            return Response({
                "ward_name": None,
                "admission_count": 0,
                "vitals_overdue": 0,
                "ward_patients": [],
                "active_alerts": (
                    ClinicalAlert.objects.filter(
                        hospital=hospital,
                        status="active"
                    ).count()
                    if hospital
                    else 0
                ),
            })
        latest_vital_sub = (
            MedicalRecord.objects.filter(
                patient_id=OuterRef("patient_id"),
                record_type="vital_signs",
            )
            .order_by("-created_at")
            .values("created_at")[:1]
        )
        admissions = (
            PatientAdmission.objects.filter(ward=ward, discharged_at__isnull=True)
            .select_related("patient")
            .annotate(last_vitals_at=Subquery(latest_vital_sub, output_field=DateTimeField()))
        )
        admission_list = list(admissions)
        count = len(admission_list)
        cutoff = timezone.now() - timezone.timedelta(hours=4)
        pat_ids = [a.patient_id for a in admission_list]
        allergy_active = set()
        if pat_ids:
            allergy_active = set(
                Allergy.objects.filter(patient_id__in=pat_ids, is_active=True).values_list(
                    "patient_id", flat=True
                )
            )
        vitals_overdue_ids = []
        ward_patients = []
        for adm in admission_list:
            last_ts = adm.last_vitals_at
            if last_ts is None or last_ts < cutoff:
                vitals_overdue_ids.append(str(adm.patient_id))
            has_allergy = adm.patient_id in allergy_active
            ward_patients.append({
                "patient_id": str(adm.patient_id),
                "patient_name": adm.patient.full_name,
                "ghana_health_id": adm.patient.ghana_health_id,
                "admitted_at": adm.admitted_at.isoformat(),
                "last_vitals_at": last_ts.isoformat() if last_ts else None,
                "vitals_overdue": last_ts is None or last_ts < cutoff,
                "has_allergy": has_allergy,
            })
        active_alerts = ClinicalAlert.objects.filter(hospital=hospital, status="active").count()
        now_h = timezone.localtime().hour
        current_shift = "Morning"
        if now_h >= 15 and now_h < 23:
            current_shift = "Evening"
        elif now_h >= 23 or now_h < 7:
            current_shift = "Night"
        pending_dispense_count = Prescription.objects.filter(
            record__patient_id__in=pat_ids,
            dispense_status="pending",
        ).count() if pat_ids else 0
        return Response({
            "ward_name": ward.ward_name,
            "admission_count": count,
            "vitals_overdue": len(vitals_overdue_ids),
            "vitals_overdue_patient_ids": vitals_overdue_ids,
            "ward_patients": ward_patients,
            "active_alerts": active_alerts,
            # Spec-compatible nurse dashboard keys
            "admitted_count": count,
            "vitals_overdue_count": len(vitals_overdue_ids),
            "pending_dispense_count": pending_dispense_count,
            "current_shift": current_shift,
        })

    if user.role == "hospital_admin":
        if not hospital:
            return Response({})
        staff_active_qs = User.objects.filter(hospital=hospital, account_status="active").exclude(
            role="hospital_admin"
        )
        total_users = staff_active_qs.count()
        total_patients = Patient.objects.filter(registered_at=hospital).count()
        pending = User.objects.filter(hospital=hospital, account_status="pending").count()
        inactive = User.objects.filter(hospital=hospital, account_status="inactive").count()
        locked_accounts_count = User.objects.filter(hospital=hospital, account_status="locked").count()
        active_alerts = ClinicalAlert.objects.filter(hospital=hospital, status="active").count()
        encounters_today = Encounter.objects.filter(
            hospital=hospital,
            encounter_date__date=today,
        ).count()
        encounters_in_consultation = Encounter.objects.filter(
            hospital=hospital,
            encounter_date__date=today,
            status="in_consultation",
        ).count()
        admission_count = PatientAdmission.objects.filter(
            hospital=hospital,
            discharged_at__isnull=True,
        ).count()
        total_beds = Bed.objects.filter(ward__hospital=hospital, is_active=True).count()
        occupied_admissions = PatientAdmission.objects.filter(
            hospital=hospital,
            discharged_at__isnull=True,
        ).count()
        beds_available = max(0, total_beds - occupied_admissions)
        recent_audit = []
        for log in AuditLog.objects.filter(hospital=hospital).select_related("user").order_by("-timestamp")[:10]:
            recent_audit.append({
                "log_id": str(log.id),
                "action": log.action,
                "resource_type": log.resource_type or "",
                "timestamp": log.timestamp.isoformat(),
                "user_name": log.user.full_name if log.user else "",
            })
        pending_invitations_list = []
        for u in User.objects.filter(hospital=hospital, account_status="pending").order_by(
            "invitation_expires_at", "created_at"
        )[:50]:
            pending_invitations_list.append({
                "user_id": str(u.id),
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "invitation_expires_at": u.invitation_expires_at.isoformat() if u.invitation_expires_at else None,
                "created_at": u.created_at.isoformat() if u.created_at else None,
            })
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        apt_today = Appointment.objects.filter(
            hospital=hospital,
            scheduled_at__gte=today_start,
            scheduled_at__lt=today_end,
        )
        apt_agg = apt_today.aggregate(
            scheduled=Count(Case(When(status="scheduled", then=1))),
            checked_in=Count(Case(When(status="checked_in", then=1))),
            completed=Count(Case(When(status="completed", then=1))),
            cancelled=Count(Case(When(status="cancelled", then=1))),
            no_show=Count(Case(When(status="no_show", then=1))),
        )
        appointment_summary = {
            "scheduled": apt_agg["scheduled"] or 0,
            "checked_in": apt_agg["checked_in"] or 0,
            "completed": apt_agg["completed"] or 0,
            "cancelled": apt_agg["cancelled"] or 0,
            "no_show": apt_agg["no_show"] or 0,
        }
        return Response({
            "total_patients": total_patients,
            "total_users": total_users,
            "total_active": total_users,
            "pending_invitations": pending,
            "pending_invite_count": pending,
            "inactive": inactive,
            "active_alerts": active_alerts,
            "encounters_today": encounters_today,
            "encounters_in_consultation": encounters_in_consultation,
            "admission_count": admission_count,
            "total_beds": total_beds,
            "beds_available": beds_available,
            "locked_accounts_count": locked_accounts_count,
            "recent_audit_events": recent_audit,
            "pending_invitations_list": pending_invitations_list,
            "appointment_summary": appointment_summary,
        })

    if user.role == "lab_technician":
        pending_qs = get_lab_order_queryset(user, get_effective_hospital(request)).filter(
            Q(labresult__isnull=True) | Q(labresult__status="pending")
        ).select_related("record", "record__patient")
        pending_stat = pending_qs.filter(urgency="stat").count()
        pending_urgent = pending_qs.filter(urgency="urgent").count()
        pending_routine = pending_qs.filter(urgency="routine").count()
        pending_total = pending_stat + pending_urgent + pending_routine
        cutoff_24h = timezone.now() - timezone.timedelta(hours=24)
        orders_over_24h_qs = pending_qs.filter(record__created_at__lt=cutoff_24h).order_by("record__created_at")[:20]
        orders_over_24h = []
        for o in orders_over_24h_qs:
            full_name = o.record.patient.full_name if o.record and o.record.patient else ""
            orders_over_24h.append({
                "order_id": str(o.id),
                "test_name": o.test_name,
                "urgency": o.urgency,
                "ordered_at": o.record.created_at.isoformat() if o.record else None,
                "patient_first_name": full_name.split()[0] if full_name else "",
            })
        completed_today = get_lab_result_queryset(user).filter(
            lab_tech=user,
            result_date__date=today,
        ).exclude(status="pending").count()
        return Response({
            "pending_orders": pending_total,
            "pending_stat": pending_stat,
            "pending_urgent": pending_urgent,
            "pending_routine": pending_routine,
            "completed_today": completed_today,
            "orders_over_24hr": orders_over_24h,
        })

    if user.role == "super_admin":
        active_alerts = ClinicalAlert.objects.filter(status="active").count()
        total_patients = Patient.objects.count()
        db_ok = "ok"
        try:
            connection.ensure_connection()
        except Exception:
            db_ok = "error"
        return Response({
            "hospitals_count": Hospital.objects.count(),
            "total_users": User.objects.count(),
            "total_patients": total_patients,
            "active_alerts": active_alerts,
            "db_status": db_ok,
        })

    if user.role == "receptionist" and hospital:
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timezone.timedelta(days=1)
        apt_today = Appointment.objects.filter(
            hospital=hospital,
            scheduled_at__gte=today_start,
            scheduled_at__lt=today_end,
        ).select_related("provider", "patient")
        apt_agg = apt_today.aggregate(
            total=Count("id"),
            checked_in=Count(Case(When(status="checked_in", then=1))),
            cancelled=Count(Case(When(status="cancelled", then=1))),
            no_show=Count(Case(When(status="no_show", then=1))),
        )
        appointments_today = apt_agg["total"] or 0
        checked_in_count = apt_agg["checked_in"] or 0
        no_show_count = apt_agg["no_show"] or 0
        cancelled_count = apt_agg["cancelled"] or 0
        remaining_count = max(0, appointments_today - checked_in_count - no_show_count - cancelled_count)
        appointment_rows = [
            {
                "id": str(a.id),
                "patient_id": str(a.patient_id),
                "patient_name": a.patient.full_name,
                "scheduled_at": a.scheduled_at.isoformat(),
                "status": a.status,
                "appointment_with_department": f"Appointment with {a.appointment_type.replace('_', ' ').title()}",
                "appointment_with_doctor": f"Appointment with {a.provider.full_name}" if a.provider else None,
                "provider_name": a.provider.full_name if a.provider else None,
            }
            for a in apt_today.order_by("scheduled_at")[:200]
        ]
        return Response({
            "appointments_today": appointments_today,
            "checked_in_count": checked_in_count,
            "no_show_count": no_show_count,
            "remaining_count": remaining_count,
            "appointments": appointment_rows,
            # Backwards-compatible aliases
            "appointments_today_total": appointments_today,
            "appointments_today_confirmed": checked_in_count,
            "appointments_today_cancelled": cancelled_count,
            "appointments_today_no_show": no_show_count,
        })

    return Response({})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def dashboard_analytics(request):
    """Cohort-style analytics: counts by date range, optional group_by day/facility. Admin, Doctor."""
    if request.user.role not in ("super_admin", "hospital_admin", "doctor"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    from django.db.models.functions import TruncDate
    from datetime import timedelta

    user = request.user
    hospital = get_request_hospital(request)
    today = timezone.now().date()
    date_from = request.GET.get("from") or (today - timedelta(days=30)).isoformat()
    date_to = request.GET.get("to") or today.isoformat()
    group_by = request.GET.get("group_by", "day")  # day | facility

    try:
        from_date = parse_date(date_from) or today - timedelta(days=30)
        to_date = parse_date(date_to) or today
    except Exception:
        from_date = today - timedelta(days=30)
        to_date = today

    if from_date > to_date:
        from_date, to_date = to_date, from_date

    out = {"from": from_date.isoformat(), "to": to_date.isoformat()}

    # Patients registered in range (facility-scoped for non-super_admin)
    qs_patients = Patient.objects.filter(created_at__date__gte=from_date, created_at__date__lte=to_date)
    if user.role != "super_admin" and hospital:
        qs_patients = qs_patients.filter(registered_at=hospital)
    if group_by == "day":
        by_day = (
            qs_patients.annotate(day=TruncDate("created_at"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        out["patients_by_day"] = [{"date": d["day"].isoformat(), "count": d["count"]} for d in by_day]
    out["patients_total"] = qs_patients.count()

    # Encounters in range
    qs_enc = Encounter.objects.filter(encounter_date__date__gte=from_date, encounter_date__date__lte=to_date)
    if user.role != "super_admin" and hospital:
        qs_enc = qs_enc.filter(hospital=hospital)
    if group_by == "day":
        by_day_enc = (
            qs_enc.annotate(day=TruncDate("encounter_date"))
            .values("day")
            .annotate(count=Count("id"))
            .order_by("day")
        )
        out["encounters_by_day"] = [{"date": d["day"].isoformat(), "count": d["count"]} for d in by_day_enc]
    out["encounters_total"] = qs_enc.count()

    return Response(out)
