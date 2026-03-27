import hashlib
import hmac
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import AuditLog


def _require_super_admin(request):
    if request.user.role != "super_admin":
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    return None


def _compute_audit_chain_status(max_users=200, max_logs_per_user=2000):
    # NOTE: chain is per-user in core.models.AuditLog.save()
    user_ids = (
        AuditLog.objects.values_list("user_id", flat=True)
        .distinct()
        .order_by()[:max_users]
    )
    try:
        from django.conf import settings
        signing_key = getattr(settings, "AUDIT_LOG_SIGNING_KEY", "dev-key-change-in-production").encode()
    except Exception:
        signing_key = b"dev-key-change-in-production"

    checked = 0
    for uid in user_ids:
        prev_hash = "0"
        logs = (
            AuditLog.objects.filter(user_id=uid)
            .order_by("timestamp")
            .only("user_id", "action", "resource_type", "resource_id", "chain_hash", "signature", "timestamp")[:max_logs_per_user]
        )
        for log in logs:
            data = f"{prev_hash}{log.user_id}{log.action}{log.resource_type or ''}{log.resource_id or ''}"
            expected_hash = hashlib.sha256(data.encode()).hexdigest()
            expected_sig = hmac.new(signing_key, data.encode(), hashlib.sha256).hexdigest()
            checked += 1
            if log.chain_hash != expected_hash or (log.signature and log.signature != expected_sig):
                return {
                    "status": "invalid",
                    "last_checked_at": timezone.now().isoformat(),
                    "message": f"Mismatch user={uid} ts={log.timestamp.isoformat()}",
                    "checked_entries": checked,
                }
            prev_hash = log.chain_hash
    return {
        "status": "valid",
        "last_checked_at": timezone.now().isoformat(),
        "message": None,
        "checked_entries": checked,
    }


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def validate_chain(request):
    denied = _require_super_admin(request)
    if denied:
        return denied
    try:
        out = _compute_audit_chain_status(max_users=500, max_logs_per_user=2000)
        return Response(out)
    except Exception as e:
        return Response(
            {"status": "unknown", "last_checked_at": None, "message": str(e), "checked_entries": 0},
            status=status.HTTP_200_OK,
        )

