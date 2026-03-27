from datetime import timedelta
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
        except (Hospital.DoesNotExist, ValueError):
            pass
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
        {
            "id": str(apt.id),
            "patient_id": str(apt.patient_id),
            "appointment_date": apt.scheduled_at.isoformat(),
            "scheduled_at": apt.scheduled_at.isoformat(),
            "status": apt.status,
            "appointment_type": apt.appointment_type,
        },
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
        return Response({"available": True, "conflict": False, "available_slots": []})

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
        {
            "available": False,
            "conflict": True,
            "message": f"{provider_name} already has a patient at {conflict.scheduled_at.strftime('%H:%M')}.",
            "available_slots": suggested,
        },
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
    return Response({
        "id": str(apt.id),
        "status": apt.status,
        "scheduled_at": apt.scheduled_at.isoformat(),
    })


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
    apt = _appointment_queryset(request.user).filter(id=pk).first()
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
    
    return Response({
        "id": str(apt.id),
        "status": apt.status,
        "verified_at": verified_at.isoformat(),
        "checked_in_at": verified_at.isoformat(),
    })


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
    
    return Response({
        "id": str(apt.id),
        "scheduled_at": apt.scheduled_at.isoformat(),
        "status": apt.status,
    })


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
    
    return Response({
        "id": str(apt.id),
        "status": apt.status,
        "marked_at": timezone.now().isoformat(),
    })


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
    
    from datetime import timedelta, date as date_type
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
    
    return Response({
        "period_days": days,
        "total_appointments": total_apts,
        "no_show_count": no_show_count,
        "no_show_rate": round(no_show_rate, 1),
        "by_provider": by_provider,
        "by_appointment_type": by_apt_type,
        "daily_no_shows": daily_no_shows,
    })


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
    
    return Response({
        "id": str(apt.id),
        "status": apt.status,
        "no_show_override_reason": apt.no_show_override_reason,
    })
