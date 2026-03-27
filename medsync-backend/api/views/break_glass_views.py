import hashlib
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from datetime import timedelta
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import AuditLog, User
from interop.models import GlobalPatient, BreakGlassLog
from api.utils import get_global_patient_queryset, get_effective_hospital, get_request_hospital
from api.serializers import BreakGlassLogSerializer


def _interop_role_ok(user):
    return user.role in ("doctor", "hospital_admin", "super_admin")


def _audit_emergency(user, global_patient_id, request, hospital=None):
    prev = AuditLog.objects.filter(user=user).order_by("-timestamp").first()
    prev_hash = prev.chain_hash if prev else "0"
    data = f"{prev_hash}{user.id}EMERGENCY_ACCESSglobal_patient{global_patient_id}"
    chain_hash = hashlib.sha256(data.encode()).hexdigest()
    try:
        rid = __import__("uuid").UUID(global_patient_id)
    except (ValueError, TypeError):
        rid = None
    AuditLog.objects.create(
        user=user,
        action="EMERGENCY_ACCESS",
        resource_type="global_patient",
        resource_id=rid,
        hospital=hospital or getattr(user, "hospital", None),
        ip_address=request.META.get("REMOTE_ADDR", "127.0.0.1"),
        user_agent=request.META.get("HTTP_USER_AGENT", "") or "",
        chain_hash=chain_hash,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def break_glass_create(request):
    if not _interop_role_ok(request.user):
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

    global_patient_id = request.data.get("global_patient_id")
    reason_code = (request.data.get("reason_code") or "").strip()
    reason = (request.data.get("reason") or "").strip()
    if not global_patient_id:
        return Response(
            {"message": "global_patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not reason_code:
        return Response(
            {"message": "reason_code required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    allowed_reason_codes = {code for code, _label in BreakGlassLog.REASON_CODES}
    if reason_code not in allowed_reason_codes:
        return Response(
            {"message": "Invalid reason_code"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not reason:
        return Response(
            {"message": "reason required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except (GlobalPatient.DoesNotExist, ValueError):
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Set expires_at to 15 minutes from now (or configured window)
    window_minutes = getattr(settings, "BREAK_GLASS_WINDOW_MINUTES", 240)
    expires_at = timezone.now() + timedelta(minutes=window_minutes)

    log = BreakGlassLog.objects.create(
        global_patient=gp,
        facility=hospital,
        accessed_by=request.user,
        reason_code=reason_code,
        reason=reason,
        expires_at=expires_at,
    )
    _audit_emergency(request.user, global_patient_id, request, hospital=hospital)

    notify_emails = list(settings.BREAK_GLASS_NOTIFY_EMAILS)
    if not notify_emails:
        notify_emails = list(
            User.objects.filter(
                role="hospital_admin",
                hospital=hospital,
                account_status="active",
            ).values_list("email", flat=True)
        )
        super_emails = list(
            User.objects.filter(role="super_admin", account_status="active").values_list("email", flat=True)
        )
        notify_emails = list(dict.fromkeys(notify_emails + super_emails))
    if notify_emails:
        subject = "[MedSync] Break-glass emergency access used"
        body = (
            f"Break-glass access was used for global patient {gp.full_name} (ID: {global_patient_id}).\n"
            f"Facility: {hospital.name}\n"
            f"User: {request.user.full_name} ({request.user.email})\n"
            f"Reason: {reason}\n"
            f"Access window expires in {window_minutes} minutes.\n"
        )
        try:
            send_mail(
                subject,
                body,
                settings.DEFAULT_FROM_EMAIL,
                notify_emails,
                fail_silently=True,
            )
        except Exception:
            pass

    return Response(
        BreakGlassLogSerializer(log).data,
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def break_glass_list(request):
    """List break-glass events for a global patient (audit trail). Only valid if within time window."""
    if not _interop_role_ok(request.user):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    global_patient_id = request.GET.get("global_patient_id")
    if not global_patient_id:
        return Response(
            {"message": "global_patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    qs = get_global_patient_queryset(request.user, get_effective_hospital(request)).filter(id=global_patient_id)
    if not qs.exists():
        return Response(
            {"message": "Global patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    gp = qs.first()
    logs = (
        BreakGlassLog.objects.filter(global_patient=gp)
        .select_related("facility", "accessed_by")
        .order_by("-created_at")[:100]
    )
    
    # Filter out expired logs from response (don't show expired access)
    active_logs = [log for log in logs if not log.is_expired()]
    
    # Log expired access attempts in audit trail
    for log in logs:
        if log.is_expired() and log.accessed_by == request.user:
            AuditLog.objects.create(
                user=request.user,
                action="BREAK_GLASS_EXPIRED_ACCESS",
                resource_type="break_glass_log",
                resource_id=log.id,
                hospital=log.facility,
                ip_address=request.META.get("REMOTE_ADDR", "127.0.0.1"),
                user_agent=request.META.get("HTTP_USER_AGENT", "") or "",
            )
    
    return Response({
        "data": BreakGlassLogSerializer(active_logs, many=True).data,
    })
