from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from patients.models import Appointment
from api.utils import get_patient_queryset, get_effective_hospital, get_request_hospital


def _appointment_queryset(user, effective_hospital=None):
    from api.utils import _scope_hospital
    hospital = _scope_hospital(user, effective_hospital)
    qs = Appointment.objects.select_related("patient", "hospital", "provider", "created_by")
    if user.role == "super_admin" and not user.hospital_id and not hospital:
        return qs
    if hospital:
        return qs.filter(hospital=hospital)
    return qs.none()


def _appointment_create_impl(request):
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
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
    if not hospital and request.user.role == "super_admin" and data.get("hospital_id"):
        from core.models import Hospital
        try:
            hospital = Hospital.objects.get(id=data["hospital_id"])
        except (Hospital.DoesNotExist, ValueError) as e:
            import logging
            logging.getLogger(__name__).warning(f"Hospital lookup failed for ID {data['hospital_id']}: {str(e)}")
    scheduled_at = data.get("appointment_date") or data.get("scheduled_at")
    if not scheduled_at:
        return Response(
            {"message": "appointment_date required (ISO datetime)"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    dt = parse_datetime(scheduled_at) if isinstance(scheduled_at, str) else scheduled_at
    if not dt:
        return Response(
            {"message": "Invalid appointment_date"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if dt <= timezone.now():
        return Response(
            {"message": "scheduled_at must be in the future"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    appointment_type = (data.get("appointment_type") or "outpatient").strip()
    if appointment_type not in ("outpatient", "follow_up", "consultation", "procedure", "other"):
        appointment_type = "outpatient"
    # Accept both legacy and receptionist-spec aliases.
    provider_id = data.get("doctor_id") or data.get("provider_id")
    provider = None
    if provider_id and hospital:
        from core.models import User
        provider = User.objects.filter(id=provider_id, hospital=hospital).first()
    if hospital and Appointment.objects.filter(
        hospital=hospital,
        patient=patient,
        scheduled_at=dt,
        status__in=("scheduled", "checked_in"),
    ).exists():
        return Response(
            {"message": "Patient already has an active appointment at this time"},
            status=status.HTTP_409_CONFLICT,
        )
    if hospital and provider and Appointment.objects.filter(
        hospital=hospital,
        provider=provider,
        status__in=("scheduled", "checked_in"),
        scheduled_at__range=[dt - timedelta(minutes=15), dt + timedelta(minutes=15)],
    ).exists():
        return Response(
            {"message": "Provider has conflicting appointment"},
            status=status.HTTP_409_CONFLICT,
        )

    apt = Appointment.objects.create(
        patient=patient,
        hospital=hospital,
        scheduled_at=dt,
        appointment_type=appointment_type,
        provider=provider,
        notes=(data.get("notes") or "").strip() or None,
        created_by=request.user,
    )
    return Response(
        {"data": {
            "id": str(apt.id),
            "patient_id": str(apt.patient_id),
            "appointment_date": apt.scheduled_at.isoformat(),
            "scheduled_at": apt.scheduled_at.isoformat(),
            "status": apt.status,
            "appointment_type": apt.appointment_type,
        }},
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def appointment_list(request):
    if request.method == "POST":
        return _appointment_create_impl(request)
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor", "nurse", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    qs = _appointment_queryset(request.user, get_effective_hospital(request))
    date_str = request.GET.get("date")
    if date_str:
        d = parse_date(date_str)
        if d:
            qs = qs.filter(scheduled_at__date=d)
    patient_id = request.GET.get("patient_id")
    if patient_id:
        patient_qs = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id)
        if not patient_qs.exists():
            return Response({"data": []})
        qs = qs.filter(patient_id=patient_id)
    status_filter = request.GET.get("status")
    if status_filter:
        qs = qs.filter(status=status_filter)
    department_id = request.GET.get("department_id")
    if department_id:
        qs = qs.filter(provider__department_link_id=department_id)
    qs = qs.order_by("scheduled_at")[:200]
    data = [
        {
            "id": str(a.id),
            "patient_id": str(a.patient_id),
            "patient_name": a.patient.full_name,
            "ghana_health_id": a.patient.ghana_health_id,
            "scheduled_at": a.scheduled_at.isoformat(),
            "status": a.status,
            "appointment_type": a.appointment_type,
            "provider_name": a.provider.full_name if a.provider else None,
            "notes": a.notes,
        }
        for a in qs
    ]
    return Response({"data": data})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def appointment_check_availability(request):
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response({"available": False, "message": "No facility assigned"}, status=status.HTTP_400_BAD_REQUEST)

    when_raw = request.GET.get("datetime") or request.GET.get("appointment_date")
    if not when_raw:
        return Response({"message": "datetime required"}, status=status.HTTP_400_BAD_REQUEST)
    when = parse_datetime(when_raw)
    if not when:
        return Response({"message": "Invalid datetime"}, status=status.HTTP_400_BAD_REQUEST)

    provider_id = request.GET.get("doctor_id") or request.GET.get("provider_id")
    department_id = request.GET.get("department_id")

    active_qs = Appointment.objects.filter(
        hospital=hospital,
        status__in=("scheduled", "checked_in"),
    )
    if provider_id:
        conflict = active_qs.filter(
            provider_id=provider_id,
            scheduled_at__range=[when - timedelta(minutes=15), when + timedelta(minutes=15)],
        ).first()
    elif department_id:
        conflict = active_qs.filter(
            provider__department_link_id=department_id,
            scheduled_at__range=[when - timedelta(minutes=15), when + timedelta(minutes=15)],
        ).first()
    else:
        conflict = active_qs.filter(
            scheduled_at__range=[when - timedelta(minutes=15), when + timedelta(minutes=15)],
        ).first()

    if not conflict:
        return Response({"data": {"available": True, "conflict": False, "available_slots": []}})

    provider_name = conflict.provider.full_name if conflict.provider else "Selected provider"
    slot_offsets = (-15, 15, 30)
    suggested = []
    for offset in slot_offsets:
        candidate = when + timedelta(minutes=offset)
        has_conflict = active_qs.filter(
            provider_id=conflict.provider_id if conflict.provider_id else None,
            scheduled_at__range=[candidate - timedelta(minutes=15), candidate + timedelta(minutes=15)],
        ).exists() if conflict.provider_id else active_qs.filter(
            scheduled_at__range=[candidate - timedelta(minutes=15), candidate + timedelta(minutes=15)]
        ).exists()
        if not has_conflict:
            suggested.append(candidate.strftime("%H:%M"))

    return Response(
        {"data": {
            "available": False,
            "conflict": True,
            "message": f"{provider_name} already has a patient at {conflict.scheduled_at.strftime('%H:%M')}.",
            "available_slots": suggested,
        }},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def appointment_create(request):
    return _appointment_create_impl(request)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def appointment_update(request, pk):
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    apt = _appointment_queryset(request.user).filter(id=pk).first()
    if not apt:
        return Response(
            {"message": "Appointment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    data = request.data
    if "status" in data and data["status"] in (
        "scheduled", "checked_in", "completed", "cancelled", "no_show"
    ):
        apt.status = data["status"]
    if "scheduled_at" in data and data["scheduled_at"]:
        dt = parse_datetime(data["scheduled_at"]) if isinstance(data["scheduled_at"], str) else data["scheduled_at"]
        if dt:
            apt.scheduled_at = dt
    if "notes" in data:
        apt.notes = (data["notes"] or "").strip() or None
    apt.save(update_fields=["status", "scheduled_at", "notes"])
    return Response({"data": {
        "id": str(apt.id),
        "status": apt.status,
        "scheduled_at": apt.scheduled_at.isoformat(),
    }})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def appointment_delete(request, pk):
    """Delete an appointment (receptionist, doctor, admin only).

    Cannot delete if appointment is already completed or marked no_show.
    """
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    apt = _appointment_queryset(request.user).filter(id=pk).first()
    if not apt:
        return Response(
            {"message": "Appointment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if apt.status in ("completed", "no_show"):
        return Response(
            {"message": "Cannot delete completed or no_show appointments"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    cancellation_reason = (request.data.get("cancellation_reason") or "").strip() if request.data else ""
    if not cancellation_reason:
        return Response(
            {"message": "cancellation_reason is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    apt.status = "cancelled"
    apt.notes = (apt.notes or "") + ("\n" if apt.notes else "") + f"[CANCELLED] {cancellation_reason}"
    apt.save(update_fields=["status", "notes"])
    from api.utils import audit_log
    audit_log(
        request.user,
        "DELETE_APPOINTMENT",
        "appointment",
        str(apt.id),
        apt.hospital,
        request,
    )
    return Response({"message": "Appointment cancelled"}, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def appointment_check_in(request, pk):
    """Mark appointment as checked-in with optional check-in notes."""
    if request.user.role not in (
        "super_admin", "hospital_admin", "nurse", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # ATOMICITY: Use select_for_update() within transaction to prevent double check-in race condition
    # This locks the appointment row during the transaction to ensure only one check-in can succeed
    with transaction.atomic():
        apt = _appointment_queryset(request.user).filter(id=pk).select_for_update().first()
        if not apt:
            return Response(
                {"message": "Appointment not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if apt.status != "scheduled":
            return Response(
                {"message": "Only scheduled appointments can be checked in"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Spec rule: allow check-in only for today's slot within +/- 2 hours.
        now = timezone.now()
        window_start = now - timezone.timedelta(hours=2)
        window_end = now + timezone.timedelta(hours=2)
        if not (window_start <= apt.scheduled_at <= window_end):
            return Response(
                {"message": "Check-in allowed only within +/- 2 hours of scheduled time"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        apt.status = "checked_in"
        verified_at = timezone.now()
        notes = request.data.get("notes", "").strip() if request.data else ""
        check_in_note = f"[CHECK-IN] Verified at {verified_at.isoformat()}"
        if notes:
            check_in_note = f"{check_in_note} | {notes}"
        apt.notes = (apt.notes or "") + ("\n" if apt.notes else "") + check_in_note
        apt.save(update_fields=["status", "notes"])

        from api.utils import audit_log
        audit_log(
            request.user,
            "APPOINTMENT_CHECKED_IN",
            "appointment",
            str(apt.id),
            apt.hospital,
            request,
        )

    return Response({"data": {
        "id": str(apt.id),
        "status": apt.status,
        "verified_at": verified_at.isoformat(),
        "checked_in_at": verified_at.isoformat(),
    }})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def appointment_reschedule(request, pk):
    """Reschedule appointment with conflict detection.

    Request body:
    {
        "scheduled_at": "2024-02-15T14:30:00Z",
        "reason": "Patient requested"  (optional)
    }

    Returns error 409 if provider already has conflicting appointment.
    """
    if request.user.role not in (
        "super_admin", "hospital_admin", "doctor", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    apt = _appointment_queryset(request.user).filter(id=pk).first()
    if not apt:
        return Response(
            {"message": "Appointment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    new_time_str = request.data.get("scheduled_at")
    if not new_time_str:
        return Response(
            {"message": "scheduled_at required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    new_time = parse_datetime(new_time_str) if isinstance(new_time_str, str) else new_time_str
    if not new_time:
        return Response(
            {"message": "Invalid scheduled_at datetime"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if new_time < timezone.now():
        return Response(
            {"message": "Cannot schedule appointment in the past"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check for conflicts if provider is set
    if apt.provider:
        from datetime import timedelta
        conflict = Appointment.objects.filter(
            provider=apt.provider,
            hospital=apt.hospital,
            status__in=("scheduled", "checked_in"),
            scheduled_at__range=[
                new_time - timedelta(minutes=30),
                new_time + timedelta(minutes=30)
            ],
        ).exclude(id=apt.id).first()

        if conflict:
            return Response(
                {
                    "message": "Provider has conflicting appointment",
                    "conflict": {
                        "provider": apt.provider.full_name,
                        "time": conflict.scheduled_at.isoformat(),
                        "patient": conflict.patient.full_name,
                    }
                },
                status=status.HTTP_409_CONFLICT,
            )

    apt.scheduled_at = new_time
    reason = request.data.get("reason", "").strip()
    if reason:
        apt.notes = (apt.notes or "") + ("\n" if apt.notes else "") + f"[RESCHEDULED] {reason}"
    apt.save(update_fields=["scheduled_at", "notes"])

    from api.utils import audit_log
    audit_log(
        request.user,
        "APPOINTMENT_RESCHEDULED",
        "appointment",
        str(apt.id),
        apt.hospital,
        request,
    )

    return Response({"data": {
        "id": str(apt.id),
        "scheduled_at": apt.scheduled_at.isoformat(),
        "status": apt.status,
    }})


# PHASE 6: Receptionist Advanced Features

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def appointment_mark_no_show(request, pk):
    """Mark appointment as no-show with optional reason.

    Request body:
    {
        "reason": "Patient did not arrive",  (optional)
        "notes": "Will need to reschedule",  (optional)
    }

    Returns:
    {
        "id": "uuid",
        "status": "no_show",
        "marked_at": "2024-01-15T10:30:00Z"
    }
    """
    if request.user.role not in (
        "super_admin", "hospital_admin", "receptionist", "nurse"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    apt = _appointment_queryset(request.user).filter(id=pk).first()
    if not apt:
        return Response(
            {"message": "Appointment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if apt.status == "no_show":
        return Response(
            {"message": "Appointment already marked as no-show"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if apt.status == "completed":
        return Response(
            {"message": "Cannot mark completed appointment as no-show"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if apt.status != "scheduled":
        return Response(
            {"message": "Only scheduled appointments can be marked as no-show"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if timezone.now() < apt.scheduled_at + timedelta(minutes=30):
        return Response(
            {"message": "No-show can be marked only 30 minutes after scheduled time"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    apt.status = "no_show"
    apt.no_show_marked_at = timezone.now()
    reason = (request.data.get("reason") or "").strip() if request.data else ""
    notes = (request.data.get("notes") or "").strip() if request.data else ""

    if reason or notes:
        note_text = ""
        if reason:
            note_text += f"[NO-SHOW] {reason}"
        if notes:
            note_text += ("\n" if note_text else "[NO-SHOW] ") + notes
        apt.notes = (apt.notes or "") + ("\n" if apt.notes else "") + note_text

    apt.save(update_fields=["status", "notes", "no_show_marked_at"])

    from api.utils import audit_log
    audit_log(
        request.user,
        "APPOINTMENT_NO_SHOW",
        "appointment",
        str(apt.id),
        apt.hospital,
        request,
    )

    return Response({"data": {
        "id": str(apt.id),
        "status": apt.status,
        "marked_at": timezone.now().isoformat(),
    }})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def appointment_no_show_statistics(request):
    """Get no-show statistics and trends for receptionist analysis.

    Query parameters:
    - days: Number of days to analyze (default 30, max 365)
    - provider_id: Filter by provider UUID (optional)
    - appointment_type: Filter by appointment type (optional)

    Returns:
    {
        "period_days": 30,
        "total_appointments": 240,
        "no_show_count": 18,
        "no_show_rate": 7.5,
        "by_provider": [
            {
                "provider_name": "Dr. Smith",
                "appointments": 50,
                "no_shows": 2,
                "no_show_rate": 4.0
            }
        ],
        "by_appointment_type": {
            "outpatient": {"total": 150, "no_shows": 12, "rate": 8.0},
            "follow_up": {"total": 60, "no_shows": 4, "rate": 6.7},
            "consultation": {"total": 30, "no_shows": 2, "rate": 6.7}
        },
        "daily_no_shows": [
            {"date": "2024-01-15", "scheduled": 8, "no_shows": 1, "rate": 12.5}
        ]
    }
    """
    if request.user.role not in (
        "super_admin", "hospital_admin", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    from datetime import timedelta
    from django.db.models import Count, Q

    hospital = get_effective_hospital(request)
    days = min(int(request.GET.get("days", "30") or "30"), 365)
    date_from = timezone.now() - timedelta(days=days)

    # Base queryset
    apts = _appointment_queryset(request.user, hospital).filter(
        scheduled_at__gte=date_from
    ).select_related("provider", "patient")

    provider_id = request.GET.get("provider_id")
    if provider_id:
        apts = apts.filter(provider_id=provider_id)

    apt_type = request.GET.get("appointment_type")
    if apt_type:
        apts = apts.filter(appointment_type=apt_type)

    # Overall stats
    total_apts = apts.count()
    no_show_count = apts.filter(status="no_show").count()
    no_show_rate = (no_show_count / total_apts * 100) if total_apts > 0 else 0

    # By provider
    by_provider = []
    for prov in apts.values("provider_id", "provider__full_name").annotate(
        prov_total=Count("id"),
        prov_no_show=Count("id", filter=Q(status="no_show"))
    ):
        if prov["provider_id"]:
            prov_rate = (prov["prov_no_show"] / prov["prov_total"] * 100) if prov["prov_total"] > 0 else 0
            by_provider.append({
                "provider_name": prov["provider__full_name"] or "Unknown",
                "appointments": prov["prov_total"],
                "no_shows": prov["prov_no_show"],
                "no_show_rate": round(prov_rate, 1)
            })

    # By appointment type
    by_apt_type = {}
    for atype in ["outpatient", "follow_up", "consultation", "procedure", "other"]:
        atype_apts = apts.filter(appointment_type=atype)
        atype_total = atype_apts.count()
        atype_no_show = atype_apts.filter(status="no_show").count()
        atype_rate = (atype_no_show / atype_total * 100) if atype_total > 0 else 0
        if atype_total > 0:
            by_apt_type[atype] = {
                "total": atype_total,
                "no_shows": atype_no_show,
                "rate": round(atype_rate, 1)
            }

    # Daily breakdown
    daily_no_shows = []
    for i in range(days):
        day = timezone.now().date() - timedelta(days=i)
        day_apts = apts.filter(scheduled_at__date=day)
        day_total = day_apts.count()
        day_no_show = day_apts.filter(status="no_show").count()
        day_rate = (day_no_show / day_total * 100) if day_total > 0 else 0

        if day_total > 0:
            daily_no_shows.append({
                "date": day.isoformat(),
                "scheduled": day_total,
                "no_shows": day_no_show,
                "rate": round(day_rate, 1)
            })

    daily_no_shows.sort(key=lambda x: x["date"])

    return Response({"data": {
        "period_days": days,
        "total_appointments": total_apts,
        "no_show_count": no_show_count,
        "no_show_rate": round(no_show_rate, 1),
        "by_provider": by_provider,
        "by_appointment_type": by_apt_type,
        "daily_no_shows": daily_no_shows,
    }})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def appointment_unmark_no_show(request, pk):
    """Override auto-marked no-show appointment (doctor/hospital_admin only).

    Allows a doctor or hospital admin to unmark an appointment that was
    auto-marked as no-show within the last 7 days.

    Request body:
    {
        "reason": "Doctor approved absence due to emergency"
    }

    Returns:
    {
        "id": "uuid",
        "status": "scheduled",
        "no_show_override_reason": "reason"
    }

    Error codes:
    - 403: Not a doctor/admin, or override window expired (>7 days)
    - 400: Appointment not currently no_show, or no_show_marked_at is null
    """
    if request.user.role not in ("super_admin", "hospital_admin", "doctor"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    apt = _appointment_queryset(request.user).filter(id=pk).first()
    if not apt:
        return Response(
            {"message": "Appointment not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if apt.status != "no_show":
        return Response(
            {"message": "Appointment is not marked as no-show"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not apt.no_show_marked_at:
        return Response(
            {"message": "Appointment was not auto-marked; cannot override"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from datetime import timedelta
    override_window_days = 7
    override_deadline = apt.no_show_marked_at + timedelta(days=override_window_days)

    if timezone.now() > override_deadline:
        return Response(
            {
                "message": "Override window expired",
                "details": f"Can only override within {override_window_days} days of no-show marking"
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    reason = (request.data.get("reason") or "").strip() if request.data else ""
    if not reason:
        return Response(
            {"message": "reason field is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    apt.status = "scheduled"
    apt.no_show_override_reason = reason
    apt.save(update_fields=["status", "no_show_override_reason"])

    from api.utils import audit_log
    audit_log(
        request.user,
        "NO_SHOW_OVERRIDE",
        "appointment",
        str(apt.id),
        apt.hospital,
        request,
        extra_data={"reason": reason},
    )

    return Response({"data": {
        "id": str(apt.id),
        "status": apt.status,
        "no_show_override_reason": apt.no_show_override_reason,
    }})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def appointment_bulk_import(request):
    """Bulk import appointments from CSV data.

    Request body:
    {
        "appointments": [
            {
                "patient_id": "uuid",
                "scheduled_at": "2024-04-15 09:00" or "2024-04-15T09:00:00Z",
                "department_id": "uuid" (optional),
                "doctor_id": "uuid" (optional),
                "appointment_type": "outpatient" (optional),
                "notes": "..." (optional)
            }
        ]
    }

    Returns:
    {
        "created": 10,
        "failed": 2,
        "details": [
            {"status": "success", "message": "Appointment created", "appointment_id": "uuid"},
            {"status": "error", "row_num": 5, "patient_id": "...", "message": "Patient not found"}
        ]
    }
    """
    if request.user.role not in (
        "super_admin", "hospital_admin", "receptionist"
    ):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    appointments_data = request.data.get("appointments", [])
    if not appointments_data:
        return Response(
            {"message": "appointments array required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    details = []
    created = 0
    failed = 0

    for idx, item in enumerate(appointments_data):
        patient_id = item.get("patient_id")
        scheduled_at = item.get("scheduled_at")

        # Validation
        if not patient_id:
            details.append({
                "row_num": idx + 1,
                "status": "error",
                "message": "patient_id required"
            })
            failed += 1
            continue

        if not scheduled_at:
            details.append({
                "row_num": idx + 1,
                "patient_id": patient_id,
                "status": "error",
                "message": "scheduled_at required"
            })
            failed += 1
            continue

        # Parse datetime - handle both formats
        if isinstance(scheduled_at, str):
            # Try ISO format first, then "YYYY-MM-DD HH:MM" format
            dt = parse_datetime(scheduled_at)
            if not dt:
                # Try parsing as "YYYY-MM-DD HH:MM"
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(scheduled_at.replace(" ", "T"))
                    dt = timezone.make_aware(dt) if timezone.is_naive(dt) else dt
                except BaseException:
                    pass
        else:
            dt = scheduled_at

        if not dt:
            details.append({
                "row_num": idx + 1,
                "patient_id": patient_id,
                "status": "error",
                "message": f"Invalid scheduled_at format: {scheduled_at}"
            })
            failed += 1
            continue

        if dt <= timezone.now():
            details.append({
                "row_num": idx + 1,
                "patient_id": patient_id,
                "status": "error",
                "message": "scheduled_at must be in the future"
            })
            failed += 1
            continue

        # Check if patient exists
        patient = get_patient_queryset(request.user, hospital).filter(id=patient_id).first()
        if not patient:
            details.append({
                "row_num": idx + 1,
                "patient_id": patient_id,
                "status": "error",
                "message": "Patient not found"
            })
            failed += 1
            continue

        try:
            # Create appointment
            appointment_type = (item.get("appointment_type") or "outpatient").strip()
            if appointment_type not in ("outpatient", "follow_up", "consultation", "procedure", "other"):
                appointment_type = "outpatient"

            doctor_id = item.get("doctor_id")
            doctor = None
            if doctor_id and hospital:
                from core.models import User
                doctor = User.objects.filter(
                    id=doctor_id,
                    role="doctor",
                    hospital=hospital
                ).first()

            apt = Appointment.objects.create(
                patient=patient,
                hospital=hospital or patient.registered_at,
                scheduled_at=dt,
                appointment_type=appointment_type,
                provider=doctor,
                notes=(item.get("notes") or "").strip() or None,
                status="scheduled",
                created_by=request.user,
            )

            details.append({
                "status": "success",
                "message": "Appointment created",
                "appointment_id": str(apt.id)
            })
            created += 1

            # Audit log
            from api.utils import audit_log
            audit_log(
                request.user,
                "APPOINTMENT_BULK_CREATE",
                "appointment",
                str(apt.id),
                hospital or patient.registered_at,
                request,
            )

        except Exception as e:
            details.append({
                "row_num": idx + 1,
                "patient_id": patient_id,
                "status": "error",
                "message": str(e)
            })
            failed += 1

    return Response({
        "created": created,
        "failed": failed,
        "details": details,
    }, status=status.HTTP_200_OK if created > 0 else status.HTTP_400_BAD_REQUEST)


# PHASE 7.4: Receptionist Walk-in Queue


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_walk_in(request):
    """
    POST /appointments/walk-in
    
    Create a walk-in appointment (same-day, no prior scheduling).
    
    Request body:
    {
        "patient_id": "uuid",
        "department_id": "uuid" (optional),
        "doctor_id": "uuid" (optional - can be unassigned),
        "reason": "string",
        "urgency": "routine" | "urgent" | "emergency"
    }
    
    Returns:
    {
        "id": "uuid",
        "patient_id": "uuid",
        "patient_name": "string",
        "queue_position": int,
        "status": "checked_in",
        "urgency": "routine|urgent|emergency",
        "department": "string or null",
        "doctor": "string",
        "created_at": "ISO datetime"
    }
    """
    if request.user.role not in ('receptionist', 'nurse', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'message': 'No hospital context'}, status=status.HTTP_400_BAD_REQUEST)
    
    patient_id = request.data.get('patient_id')
    department_id = request.data.get('department_id')
    doctor_id = request.data.get('doctor_id')
    reason = request.data.get('reason', '')
    urgency = request.data.get('urgency', 'routine')
    
    if not patient_id:
        return Response({'message': 'patient_id required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Validate patient
    from patients.models import Patient
    try:
        patient = Patient.objects.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response({'message': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Validate department if provided
    department = None
    if department_id:
        try:
            from core.models import Department
            department = Department.objects.get(id=department_id, hospital=hospital, is_active=True)
        except:
            return Response({'message': 'Department not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Validate doctor if provided
    doctor = None
    if doctor_id:
        try:
            from core.models import User
            doctor = User.objects.get(id=doctor_id, hospital=hospital, role='doctor', is_active=True)
        except:
            return Response({'message': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Get current queue position for walk-ins today
    today = timezone.now().date()
    
    queue_position = Appointment.objects.filter(
        hospital=hospital,
        scheduled_at__date=today,
        appointment_type='walk_in',
    ).count() + 1
    
    # Create the walk-in appointment
    appointment = Appointment.objects.create(
        patient=patient,
        hospital=hospital,
        provider=doctor,
        scheduled_at=timezone.now(),
        appointment_type='walk_in',
        status='checked_in',  # Walk-ins are auto checked-in
        reason=reason,
        urgency=urgency if urgency in ('routine', 'urgent', 'emergency') else 'routine',
        created_by=request.user,
        queue_position=queue_position,
    )
    
    # Audit
    from api.utils import audit_log
    audit_log(
        request.user,
        'CREATE_WALK_IN_APPOINTMENT',
        'appointment',
        str(appointment.id),
        hospital,
        request,
        extra_data={'queue_position': queue_position, 'urgency': urgency},
    )
    
    doctor_name = doctor.get_full_name() if doctor else 'Unassigned'
    
    return Response({
        'id': str(appointment.id),
        'patient_id': str(patient.id),
        'patient_name': patient.full_name,
        'queue_position': queue_position,
        'status': 'checked_in',
        'urgency': appointment.urgency,
        'department': department.name if department else None,
        'doctor': doctor_name,
        'created_at': appointment.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def walk_in_queue(request):
    """
    GET /appointments/walk-in-queue?date=YYYY-MM-DD
    
    Get current walk-in queue for today (or specified date).
    Ordered by urgency (emergency → urgent → routine), then by queue position.
    
    Query parameters:
    - date: Optional date in YYYY-MM-DD format (defaults to today)
    
    Returns:
    {
        "date": "YYYY-MM-DD",
        "total_waiting": int,
        "emergency_count": int,
        "urgent_count": int,
        "queue": [
            {
                "id": "uuid",
                "queue_number": int,
                "patient_id": "uuid",
                "patient_name": "string",
                "reason": "string",
                "urgency": "routine|urgent|emergency",
                "status": "checked_in|...",
                "department": "string or null",
                "doctor": "string",
                "checked_in_at": "ISO datetime",
                "wait_time_minutes": int
            }
        ]
    }
    """
    if request.user.role not in ('receptionist', 'nurse', 'doctor', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response({'message': 'No hospital context'}, status=status.HTTP_400_BAD_REQUEST)
    
    date_str = request.query_params.get('date')
    if date_str:
        try:
            from datetime import datetime
            queue_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'message': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        queue_date = timezone.now().date()
    
    # Get walk-ins ordered by urgency then queue position
    walk_ins = Appointment.objects.filter(
        hospital=hospital,
        scheduled_at__date=queue_date,
        appointment_type='walk_in',
    ).exclude(
        status__in=['completed', 'cancelled', 'no_show']
    ).select_related('patient', 'provider').order_by(
        'urgency',  # emergency first (lexicographic: 'emergency' < 'routine' < 'urgent')
        'queue_position',
    )
    
    queue = []
    for idx, appt in enumerate(walk_ins, 1):
        queue.append({
            'id': str(appt.id),
            'queue_number': idx,
            'patient_id': str(appt.patient.id),
            'patient_name': appt.patient.full_name,
            'reason': appt.reason or '',
            'urgency': appt.urgency,
            'status': appt.status,
            'department': appt.provider.department_link.department.name if appt.provider and hasattr(appt.provider, 'department_link') else None,
            'doctor': appt.provider.get_full_name() if appt.provider else 'Unassigned',
            'checked_in_at': appt.created_at.isoformat(),
            'wait_time_minutes': int((timezone.now() - appt.created_at).total_seconds() / 60),
        })
    
    return Response({
        'date': queue_date.isoformat(),
        'total_waiting': len(queue),
        'emergency_count': len([q for q in queue if q['urgency'] == 'emergency']),
        'urgent_count': len([q for q in queue if q['urgency'] == 'urgent']),
        'queue': queue,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def doctor_availability(request, doctor_id):
    """
    GET /doctors/:id/availability?date=YYYY-MM-DD&department_id=
    
    Get available appointment slots for a doctor on a given date.
    """
    if request.user.role not in ('receptionist', 'nurse', 'doctor', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    
    # Validate doctor
    from core.models import User
    try:
        doctor = User.objects.get(id=doctor_id, role='doctor', is_active=True)
    except User.DoesNotExist:
        return Response({'message': 'Doctor not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Hospital scoping
    if hospital and doctor.hospital_id != hospital.id:
        return Response({'message': 'Doctor not in your hospital'}, status=status.HTTP_403_FORBIDDEN)
    
    # Parse date
    from datetime import datetime, time as dt_time
    
    date_str = request.query_params.get('date')
    if date_str:
        try:
            query_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response({'message': 'Invalid date format. Use YYYY-MM-DD'}, status=status.HTTP_400_BAD_REQUEST)
    else:
        query_date = timezone.now().date()
    
    # Don't allow booking too far in advance
    max_date = timezone.now().date() + timedelta(days=30)
    if query_date > max_date:
        return Response({'message': 'Cannot check availability more than 30 days ahead'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get doctor's working hours (default 8am-5pm, 30min slots)
    # In production, this would come from a DoctorSchedule model
    work_start = dt_time(8, 0)
    work_end = dt_time(17, 0)
    slot_duration_minutes = 30
    
    # Generate all possible slots
    slots = []
    current = datetime.combine(query_date, work_start)
    end = datetime.combine(query_date, work_end)
    
    while current < end:
        slots.append({
            'start': current.time().strftime('%H:%M'),
            'end': (current + timedelta(minutes=slot_duration_minutes)).time().strftime('%H:%M'),
            'datetime': current.isoformat(),
            'available': True,
        })
        current += timedelta(minutes=slot_duration_minutes)
    
    # Get existing appointments for this doctor on this date
    existing = Appointment.objects.filter(
        doctor=doctor,
        appointment_date=query_date,
    ).exclude(
        status__in=['cancelled', 'no_show']
    ).values_list('appointment_time', flat=True)
    
    existing_times = set(t.strftime('%H:%M') for t in existing if t)
    
    # Mark booked slots as unavailable
    for slot in slots:
        if slot['start'] in existing_times:
            slot['available'] = False
    
    # If date is today, mark past slots as unavailable
    if query_date == timezone.now().date():
        now_time = timezone.now().time().strftime('%H:%M')
        for slot in slots:
            if slot['start'] < now_time:
                slot['available'] = False
    
    available_count = len([s for s in slots if s['available']])
    
    return Response({
        'doctor_id': str(doctor.id),
        'doctor_name': doctor.get_full_name(),
        'date': query_date.isoformat(),
        'work_hours': {
            'start': work_start.strftime('%H:%M'),
            'end': work_end.strftime('%H:%M'),
        },
        'slot_duration_minutes': slot_duration_minutes,
        'total_slots': len(slots),
        'available_slots': available_count,
        'booked_slots': len(slots) - available_count,
        'slots': slots,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def department_doctors(request, department_id):
    """
    GET /departments/:id/doctors
    
    Get all doctors in a department with their current availability status.
    """
    if request.user.role not in ('receptionist', 'nurse', 'hospital_admin', 'super_admin'):
        return Response({'message': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
    
    hospital = get_effective_hospital(request)
    
    from core.models import Department, User
    
    try:
        department = Department.objects.get(id=department_id)
    except Department.DoesNotExist:
        return Response({'message': 'Department not found'}, status=status.HTTP_404_NOT_FOUND)
    
    if hospital and department.hospital_id != hospital.id:
        return Response({'message': 'Department not in your hospital'}, status=status.HTTP_403_FORBIDDEN)
    
    today = timezone.now().date()
    
    doctors = User.objects.filter(
        hospital=department.hospital,
        role='doctor',
        department=department,
        is_active=True,
    )
    
    doctor_data = []
    for doc in doctors:
        # Count today's appointments
        today_appointments = Appointment.objects.filter(
            doctor=doc,
            appointment_date=today,
        ).exclude(status__in=['cancelled', 'no_show']).count()
        
        # Assuming 18 slots per day (8am-5pm, 30min each)
        total_slots = 18
        
        doctor_data.append({
            'id': str(doc.id),
            'name': doc.get_full_name(),
            'email': doc.email,
            'specialization': getattr(doc, 'specialization', None),
            'today_booked': today_appointments,
            'today_available': max(0, total_slots - today_appointments),
            'availability_percent': round((total_slots - today_appointments) / total_slots * 100, 1),
        })
    
    return Response({
        'department_id': str(department.id),
        'department_name': department.name,
        'doctors': doctor_data,
        'total_doctors': len(doctor_data),
    })
