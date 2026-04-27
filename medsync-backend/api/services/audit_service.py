"""
Audit logging and tamper-evident chain validation.

Delegates persistence to ``api.utils.audit_log`` so chain hashing in ``AuditLog.save()``
stays unchanged.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

from django.conf import settings
from django.utils import timezone

from core.models import AuditLog

from api.utils import audit_log as _audit_log_impl


def log_event(
    user,
    action: str,
    *,
    resource_type=None,
    resource_id=None,
    hospital=None,
    request=None,
    extra_data=None,
):
    """Write one audit row (chained hash). Prefer this over calling ``utils.audit_log`` directly."""
    return _audit_log_impl(
        user,
        action,
        resource_type=resource_type,
        resource_id=resource_id,
        hospital=hospital,
        request=request,
        extra_data=extra_data,
    )


def compute_audit_chain_status(
    max_users: int = 200,
    max_logs_per_user: int = 2000,
) -> dict[str, Any]:
    """
    Validate AuditLog chain_hash and signature per user (tamper-evident).
    Bounded to avoid long runtimes on large deployments.
    """
    user_ids = (
        AuditLog.objects.values_list("user_id", flat=True)
        .distinct()
        .order_by()[:max_users]
    )
    try:
        signing_key = getattr(settings, "AUDIT_LOG_SIGNING_KEY", "dev-key-change-in-production").encode()
    except Exception:
        signing_key = b"dev-key-change-in-production"

    checked = 0
    for uid in user_ids:
        prev_hash = "0"
        logs = (
            AuditLog.objects.filter(user_id=uid)
            .order_by("timestamp")
            .only(
                "user_id",
                "action",
                "resource_type",
                "resource_id",
                "chain_hash",
                "signature",
                "timestamp",
            )[:max_logs_per_user]
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
                    "message": (
                        f"Mismatch at {str(log.id) if getattr(log, 'id', None) else ''} "
                        f"user={uid} ts={log.timestamp.isoformat()}"
                    ),
                    "checked_entries": checked,
                }
            prev_hash = log.chain_hash
    return {
        "status": "valid",
        "last_checked_at": timezone.now().isoformat(),
        "message": None,
        "checked_entries": checked,
    }
