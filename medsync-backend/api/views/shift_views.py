"""
Shift management endpoints for all clinical roles.
Supports start/end shift, break management, handover, and roster scheduling.
"""

from datetime import timedelta
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import User
from records.models import NurseShift, ShiftHandover
from api.utils import get_request_hospital, audit_log


# ============================================================================
# HELPERS
# ============================================================================

def _can_use_shifts(role):
    """Check if role is allowed to start/end shifts."""
    return role in ["nurse", "lab_technician", "doctor", "hospital_admin", "super_admin"]


def _active_shift(request, hospital):
    """Get the current active shift for a user in a given hospital."""
    return (
        NurseShift.objects.filter(
            nurse=request.user,
            hospital=hospital,
            status__in=("active", "on_break"),
        )
        .order_by("-shift_start")
        .first()
    )


def _build_shift_response(shift):
    """Convert shift model to API response."""
    if not shift:
        return {"status": "not_started"}

    now = timezone.now()
    duration = (now - shift.shift_start).total_seconds() / 60  # in minutes
    break_duration = 0
    if shift.break_start and shift.break_end:
        break_duration = (shift.break_end - shift.break_start).total_seconds() / 60
    elif shift.break_start and not shift.break_end:
        break_duration = (now - shift.break_start).total_seconds() / 60

    return {
        "shift_id": str(shift.id),
        "status": shift.status,
        "started_at": shift.shift_start.isoformat(),
        "duration_minutes": int(duration),
        "break_duration_minutes": int(break_duration),
        "break_start": shift.break_start.isoformat() if shift.break_start else None,
        "break_end": shift.break_end.isoformat() if shift.break_end else None,
        "ward_id": str(shift.ward.id) if shift.ward else None,
        "ward_name": shift.ward.name if shift.ward else None,
    }


# ============================================================================
# SHIFT LIFECYCLE (all clinical roles)
# ============================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_start(request):
    """Start a shift for the current user.

    Request body:
    {
        "ward_id": "uuid" (required for nurses, optional for others)
    }

    Returns:
    {
        "shift_id": "uuid",
        "status": "active",
        "started_at": "2026-03-30T09:00:00Z",
        "ward_id": "uuid or null"
    }
    """
    if not _can_use_shifts(request.user.role):
        return Response(
            {"message": "Your role cannot start shifts"},
            status=status.HTTP_403_FORBIDDEN,
        )

    hospital = get_request_hospital(request)
    if not hospital:
        if request.user.role == "super_admin":
            hospital = None
        else:
            return Response(
                {"message": "No facility assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    # Check if user already has an active shift today
    existing = _active_shift(request, hospital)
    if existing:
        return Response(
            {"message": "Shift already in progress", **_build_shift_response(existing)},
            status=status.HTTP_200_OK,
        )

    # Get ward if provided
    ward = None
    ward_id = request.data.get("ward_id")
    if ward_id:
        from core.models import Ward
        try:
            ward = Ward.objects.get(id=ward_id)
        except Ward.DoesNotExist:
            return Response(
                {"message": "Ward not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Create shift
    shift = NurseShift.objects.create(
        nurse=request.user,
        hospital=hospital or request.user.hospital,
        ward=ward,
        shift_start=timezone.now(),
        status="active",
    )

    audit_log(
        request.user,
        "SHIFT_START",
        "shift",
        str(shift.id),
        hospital or request.user.hospital,
        request,
    )

    return Response(_build_shift_response(shift), status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_end(request, shift_id):
    """End an active shift.

    Validates shift belongs to user and is in progress.

    Request body (optional):
    {
        "end_notes": "...",
        "patients_seen": 5
    }

    Returns:
    {
        "shift_id": "uuid",
        "status": "completed",
        "ended_at": "2026-03-30T17:00:00Z",
        "duration_minutes": 480
    }
    """
    if not _can_use_shifts(request.user.role):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    hospital = get_request_hospital(request)
    if not hospital:
        if request.user.role == "super_admin":
            hospital = None
        else:
            return Response(
                {"message": "No facility assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    try:
        shift = NurseShift.objects.get(id=shift_id, nurse=request.user)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found or does not belong to you"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if shift.status not in ("active", "on_break"):
        return Response(
            {"message": "Shift is not active"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # End the shift
    shift.shift_end = timezone.now()
    shift.status = "completed"
    shift.save(update_fields=["shift_end", "status"])

    duration = (shift.shift_end - shift.shift_start).total_seconds() / 60

    audit_log(
        request.user,
        "SHIFT_END",
        "shift",
        str(shift.id),
        hospital or shift.hospital,
        request,
    )

    return Response({
        "shift_id": str(shift.id),
        "status": "completed",
        "ended_at": shift.shift_end.isoformat(),
        "duration_minutes": int(duration),
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shift_current(request):
    """Get current active shift for the user.

    Returns:
    {
        "shift_id": "uuid",
        "started_at": "2026-03-30T09:00:00Z",
        "status": "active",
        "ward_id": "uuid or null",
        "ward_name": "Ward A or null",
        "duration_minutes": 120,
        "break_time_minutes": 15
    }
    or 404 if no active shift.
    """
    hospital = get_request_hospital(request)
    if not hospital:
        if request.user.role != "super_admin":
            return Response(
                {"message": "No facility assigned"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        hospital = request.user.hospital

    shift = _active_shift(request, hospital)
    if not shift:
        return Response(
            {"message": "No active shift"},
            status=status.HTTP_404_NOT_FOUND,
        )

    return Response(_build_shift_response(shift), status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_break_start(request, shift_id):
    """Start a break for the current shift."""
    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        shift = NurseShift.objects.get(id=shift_id, nurse=request.user)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if shift.status != "active":
        return Response(
            {"message": "Shift is not active"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    shift.break_start = timezone.now()
    shift.status = "on_break"
    shift.save(update_fields=["break_start", "status"])

    return Response({
        "break_started_at": shift.break_start.isoformat(),
        "status": "on_break",
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_break_end(request, shift_id):
    """End current break for the shift."""
    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        shift = NurseShift.objects.get(id=shift_id, nurse=request.user)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    if shift.status != "on_break":
        return Response(
            {"message": "Shift is not on break"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    shift.break_end = timezone.now()
    shift.status = "active"
    shift.save(update_fields=["break_end", "status"])

    return Response({
        "break_ended_at": shift.break_end.isoformat(),
        "status": "active",
    }, status=status.HTTP_200_OK)


# ============================================================================
# SHIFT HANDOVER (all roles)

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_handover_submit(request, shift_id):
    """Submit shift handover notes.

    Request body:
    {
        "handover_notes": "...",
        "critical_alerts": ["pending_tests", "medication_follow_up"],
        "next_nurse_id": "uuid or null"
    }

    Returns:
    {
        "handover_id": "uuid",
        "shift_id": "uuid",
        "created_at": "2026-03-30T17:05:00Z"
    }
    """
    if not _can_use_shifts(request.user.role):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    try:
        shift = NurseShift.objects.get(id=shift_id, nurse=request.user)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    handover_notes = request.data.get("handover_notes", "").strip()
    if not handover_notes:
        return Response(
            {"message": "handover_notes required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Create handover record
    next_nurse_id = request.data.get("next_nurse_id")
    next_nurse = None
    if next_nurse_id:
        try:
            next_nurse = User.objects.get(id=next_nurse_id, role="nurse")
        except User.DoesNotExist:
            return Response(
                {"message": "Next nurse not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

    handover = ShiftHandover.objects.create(
        shift=shift,
        nurse=request.user,
        hospital=shift.hospital,
        handover_notes=handover_notes,
        critical_alerts=request.data.get("critical_alerts", []),
        next_nurse=next_nurse,
    )

    hospital = get_request_hospital(request) or shift.hospital
    audit_log(
        request.user,
        "SHIFT_HANDOVER",
        "shift_handover",
        str(handover.id),
        hospital,
        request,
        extra_data={"alerts": request.data.get("critical_alerts", [])},
    )

    return Response({
        "handover_id": str(handover.id),
        "shift_id": str(shift.id),
        "created_at": handover.created_at.isoformat(),
    }, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shift_handover_history(request):
    """Get shift handover history for a ward or user.

    Query params:
    - ward_id: Filter by ward
    - limit: Results per page (default 20)
    - offset: Pagination offset (default 0)
    - days: Look back N days (default 30)

    Returns:
    {
        "count": 10,
        "data": [
            {
                "handover_id": "uuid",
                "shift_id": "uuid",
                "nurse_name": "John Doe",
                "ward_name": "Ward A",
                "handover_notes": "...",
                "critical_alerts": ["..."],
                "created_at": "2026-03-30T17:05:00Z"
            }
        ]
    }
    """
    if not _can_use_shifts(request.user.role):
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

    # Query handovers
    qs = ShiftHandover.objects.filter(
        hospital=hospital or request.user.hospital
    ).select_related("shift", "nurse", "shift__ward").order_by("-created_at")

    # Filter by ward if provided
    ward_id = request.query_params.get("ward_id")
    if ward_id:
        qs = qs.filter(shift__ward_id=ward_id)

    # Filter by days (default 30)
    days = int(request.query_params.get("days", 30))
    if days:
        from django.utils import timezone
        cutoff = timezone.now() - timedelta(days=days)
        qs = qs.filter(created_at__gte=cutoff)

    # Pagination
    limit = int(request.query_params.get("limit", 20))
    offset = int(request.query_params.get("offset", 0))
    count = qs.count()
    data = qs[offset: offset + limit]

    return Response({
        "count": count,
        "data": [
            {
                "handover_id": str(h.id),
                "shift_id": str(h.shift.id),
                "nurse_name": h.nurse.get_full_name() or h.nurse.username,
                "ward_name": h.shift.ward.name if h.shift.ward else None,
                "handover_notes": h.handover_notes,
                "critical_alerts": h.critical_alerts,
                "created_at": h.created_at.isoformat(),
            }
            for h in data
        ],
    }, status=status.HTTP_200_OK)


# ============================================================================
# SHIFT SCHEDULING & ROSTER (hospital admin only)
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shift_roster_list(request):
    """Get shift roster (scheduled shifts) for the hospital.

    Query params:
    - staff_id: Filter by staff member
    - ward_id: Filter by ward
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)
    - limit: Results per page (default 50)

    Returns:
    {
        "count": 20,
        "data": [
            {
                "shift_id": "uuid",
                "staff_name": "John Doe",
                "staff_id": "uuid",
                "ward_name": "Ward A",
                "shift_start": "2026-04-01T09:00:00Z",
                "shift_end": "2026-04-01T17:00:00Z",
                "status": "scheduled|active|completed|cancelled"
            }
        ]
    }
    """
    if request.user.role not in ["hospital_admin", "super_admin"]:
        return Response(
            {"message": "Only hospital admins can view roster"},
            status=status.HTTP_403_FORBIDDEN,
        )

    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Query shifts
    qs = NurseShift.objects.filter(hospital=hospital).select_related("nurse", "ward").order_by("-shift_start")

    # Filter by staff if provided
    staff_id = request.query_params.get("staff_id")
    if staff_id:
        qs = qs.filter(nurse_id=staff_id)

    # Filter by ward if provided
    ward_id = request.query_params.get("ward_id")
    if ward_id:
        qs = qs.filter(ward_id=ward_id)

    # Filter by date range if provided
    date_from = request.query_params.get("date_from")
    date_to = request.query_params.get("date_to")
    if date_from:
        from django.utils.dateparse import parse_date
        start_date = parse_date(date_from)
        if start_date:
            qs = qs.filter(shift_start__date__gte=start_date)
    if date_to:
        end_date = parse_date(date_to)
        if end_date:
            qs = qs.filter(shift_start__date__lte=end_date)

    # Pagination
    limit = int(request.query_params.get("limit", 50))
    offset = int(request.query_params.get("offset", 0))
    count = qs.count()
    data = qs[offset: offset + limit]

    return Response({
        "count": count,
        "data": [
            {
                "shift_id": str(s.id),
                "staff_name": s.nurse.get_full_name() or s.nurse.username,
                "staff_id": str(s.nurse.id),
                "ward_name": s.ward.name if s.ward else None,
                "shift_start": s.shift_start.isoformat(),
                "shift_end": s.shift_end.isoformat() if s.shift_end else None,
                "status": s.status,
            }
            for s in data
        ],
    }, status=status.HTTP_200_OK)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_schedule_create(request):
    """Create a scheduled shift (shift before it happens).

    Request body:
    {
        "staff_id": "uuid",
        "ward_id": "uuid or null",
        "scheduled_start": "2026-04-01T09:00:00Z",
        "scheduled_end": "2026-04-01T17:00:00Z"
    }

    Returns:
    {
        "shift_id": "uuid",
        "staff_id": "uuid",
        "status": "active"
    }
    """
    if request.user.role not in ["hospital_admin", "super_admin"]:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )

    staff_id = request.data.get("staff_id")
    if not staff_id:
        return Response(
            {"message": "staff_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No facility assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Verify staff member exists and belongs to hospital
    staff = User.objects.filter(id=staff_id, hospital=hospital).first()
    if not staff:
        return Response(
            {"message": "Staff member not found in this facility"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Get ward if provided
    ward = None
    ward_id = request.data.get("ward_id")
    if ward_id:
        from core.models import Ward
        try:
            ward = Ward.objects.get(id=ward_id, hospital=hospital)
        except Ward.DoesNotExist:
            return Response(
                {"message": "Ward not found in this facility"},
                status=status.HTTP_404_NOT_FOUND,
            )

    # Create shift (using NurseShift model for all roles)
    scheduled_start = request.data.get("scheduled_start")
    scheduled_end = request.data.get("scheduled_end")

    if not scheduled_start or not scheduled_end:
        return Response(
            {"message": "scheduled_start and scheduled_end required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.utils.dateparse import parse_datetime
    start_dt = parse_datetime(scheduled_start)
    end_dt = parse_datetime(scheduled_end)

    if not start_dt or not end_dt:
        return Response(
            {"message": "Invalid datetime format"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    shift = NurseShift.objects.create(
        nurse=staff,
        hospital=hospital,
        ward=ward,
        shift_start=start_dt,
        shift_end=end_dt,
        status="active",
    )

    audit_log(
        request.user,
        "SHIFT_SCHEDULE_CREATE",
        "shift_schedule",
        str(shift.id),
        hospital,
        request,
        extra_data={"staff_id": str(staff_id)},
    )

    return Response({
        "shift_id": str(shift.id),
        "staff_id": str(staff_id),
        "status": "active",
    }, status=status.HTTP_201_CREATED)


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def shift_schedule_update(request, schedule_id):
    """Update a scheduled shift."""
    if request.user.role not in ["hospital_admin", "super_admin"]:
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

    try:
        shift = NurseShift.objects.get(id=schedule_id, hospital=hospital)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Update fields if provided
    if "scheduled_start" in request.data:
        from django.utils.dateparse import parse_datetime
        start_dt = parse_datetime(request.data["scheduled_start"])
        if start_dt:
            shift.shift_start = start_dt

    if "scheduled_end" in request.data:
        from django.utils.dateparse import parse_datetime
        end_dt = parse_datetime(request.data["scheduled_end"])
        if end_dt:
            shift.shift_end = end_dt

    shift.save()

    audit_log(
        request.user,
        "SHIFT_SCHEDULE_UPDATE",
        "shift_schedule",
        str(schedule_id),
        hospital,
        request,
    )

    return Response({"shift_id": str(schedule_id)}, status=status.HTTP_200_OK)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def shift_schedule_delete(request, schedule_id):
    """Delete a scheduled shift."""
    if request.user.role not in ["hospital_admin", "super_admin"]:
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

    try:
        shift = NurseShift.objects.get(id=schedule_id, hospital=hospital)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    shift.delete()

    audit_log(
        request.user,
        "SHIFT_SCHEDULE_DELETE",
        "shift_schedule",
        str(schedule_id),
        hospital,
        request,
    )

    return Response({"message": "Shift deleted"}, status=status.HTTP_200_OK)


# ============================================================================
# CONFLICT DETECTION & OVERTIME TRACKING
# ============================================================================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def shift_check_conflict(request):
    """Check for conflicts before creating/updating a shift.

    Request body:
    {
        "staff_id": "uuid",
        "scheduled_start": "2026-04-01T09:00:00Z",
        "scheduled_end": "2026-04-01T17:00:00Z",
        "exclude_shift_id": "uuid or null" (for updates)
    }

    Returns:
    {
        "has_conflict": false,
        "conflicts": [],
        "warnings": [],
        "can_proceed": true
    }
    """
    if request.user.role not in ["hospital_admin", "super_admin"]:
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

    staff_id = request.data.get("staff_id")
    scheduled_start = request.data.get("scheduled_start")
    scheduled_end = request.data.get("scheduled_end")
    exclude_shift_id = request.data.get("exclude_shift_id")

    if not staff_id or not scheduled_start or not scheduled_end:
        return Response(
            {"message": "staff_id, scheduled_start, and scheduled_end required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from django.utils.dateparse import parse_datetime
    start_dt = parse_datetime(scheduled_start)
    end_dt = parse_datetime(scheduled_end)

    if not start_dt or not end_dt:
        return Response(
            {"message": "Invalid datetime format"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Check for overlapping shifts
    qs = NurseShift.objects.filter(
        nurse_id=staff_id,
        hospital=hospital,
        status__in=("active", "completed"),
        shift_start__lt=end_dt,
        shift_end__gt=start_dt,  # Overlapping
    )

    if exclude_shift_id:
        qs = qs.exclude(id=exclude_shift_id)

    conflicts = list(qs.values_list("id", "shift_start", "shift_end"))

    return Response({
        "has_conflict": len(conflicts) > 0,
        "conflicts": [
            {
                "shift_id": str(c[0]),
                "shift_start": c[1].isoformat() if c[1] else None,
                "shift_end": c[2].isoformat() if c[2] else None,
            }
            for c in conflicts
        ],
        "warnings": [],
        "can_proceed": len(conflicts) == 0,
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shift_overtime_report(request):
    """Get overtime tracking and statistics for staff.

    Query params:
    - month: YYYY-MM (default current month)
    - ward_id: Filter by ward
    - staff_id: Filter by staff member

    Returns:
    {
        "month": "2026-03",
        "data": [
            {
                "staff_id": "uuid",
                "staff_name": "John Doe",
                "total_hours": 168,
                "overtime_hours": 8,
                "is_exceeding_limit": false,
                "shifts_completed": 20
            }
        ],
        "overtime_threshold_hours": 160
    }
    """
    if request.user.role not in ["hospital_admin", "super_admin"]:
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

    # Get month filter (default current month)
    month_str = request.query_params.get("month")
    if month_str:
        from django.utils.dateparse import parse_date
        month_date = parse_date(f"{month_str}-01")
        if not month_date:
            return Response(
                {"message": "Invalid month format (YYYY-MM)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    else:
        from django.utils import timezone
        month_date = timezone.now().date().replace(day=1)

    # Build query for shifts in this month
    import calendar
    from datetime import datetime as dt
    year = month_date.year
    month = month_date.month
    days_in_month = calendar.monthrange(year, month)[1]
    month_start = dt(year, month, 1, tzinfo=timezone.utc)
    month_end = dt(year, month, days_in_month, hour=23, minute=59, second=59, tzinfo=timezone.utc)

    qs = NurseShift.objects.filter(
        hospital=hospital,
        shift_start__gte=month_start,
        shift_start__lte=month_end,
        status="completed"
    ).select_related("nurse")

    # Filter by staff if provided
    staff_id = request.query_params.get("staff_id")
    if staff_id:
        qs = qs.filter(nurse_id=staff_id)

    # Filter by ward if provided
    ward_id = request.query_params.get("ward_id")
    if ward_id:
        qs = qs.filter(ward_id=ward_id)

    # Calculate overtime per staff
    staff_stats = {}
    for shift in qs:
        staff = shift.nurse
        staff_id_key = str(staff.id)

        if staff_id_key not in staff_stats:
            staff_stats[staff_id_key] = {
                "staff_id": staff_id_key,
                "staff_name": staff.get_full_name() or staff.username,
                "total_minutes": 0,
                "shifts_completed": 0,
            }

        if shift.shift_end:
            duration = (shift.shift_end - shift.shift_start).total_seconds() / 60
            staff_stats[staff_id_key]["total_minutes"] += int(duration)
            staff_stats[staff_id_key]["shifts_completed"] += 1

    # Convert to hours and calculate overtime
    THRESHOLD_HOURS = 160
    data = []
    for staff_data in staff_stats.values():
        total_hours = staff_data["total_minutes"] / 60
        overtime_hours = max(0, total_hours - THRESHOLD_HOURS)
        data.append({
            **staff_data,
            "total_hours": int(total_hours),
            "overtime_hours": int(overtime_hours),
            "is_exceeding_limit": total_hours > THRESHOLD_HOURS,
        })

    return Response({
        "month": f"{year}-{month:02d}",
        "data": sorted(data, key=lambda x: -x["overtime_hours"]),
        "overtime_threshold_hours": THRESHOLD_HOURS,
    }, status=status.HTTP_200_OK)


# ============================================================================
# BREAK & DURATION TRACKING
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def shift_statistics(request, shift_id):
    """Get detailed shift statistics including breaks and duration.

    Returns:
    {
        "shift_id": "uuid",
        "started_at": "2026-03-30T09:00:00Z",
        "ended_at": "2026-03-30T17:00:00Z",
        "total_duration_minutes": 480,
        "total_break_minutes": 30,
        "active_time_minutes": 450
    }
    """
    try:
        shift = NurseShift.objects.get(id=shift_id, hospital=request.user.hospital)
    except NurseShift.DoesNotExist:
        return Response(
            {"message": "Shift not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Calculate durations
    total_duration = 0
    if shift.shift_end:
        total_duration = int((shift.shift_end - shift.shift_start).total_seconds() / 60)

    break_duration = 0
    if shift.break_start and shift.break_end:
        break_duration = int((shift.break_end - shift.break_start).total_seconds() / 60)

    active_time = max(0, total_duration - break_duration)

    return Response({
        "shift_id": str(shift.id),
        "started_at": shift.shift_start.isoformat(),
        "ended_at": shift.shift_end.isoformat() if shift.shift_end else None,
        "total_duration_minutes": total_duration,
        "total_break_minutes": break_duration,
        "active_time_minutes": active_time,
    }, status=status.HTTP_200_OK)
