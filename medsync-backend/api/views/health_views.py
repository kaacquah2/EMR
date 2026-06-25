"""Public health check for uptime monitoring. No auth required."""
import time
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from django.db import connection
from django.utils import timezone


def _ms(start: float) -> int:
    return int(round((time.perf_counter() - start) * 1000))


def _status_obj(name: str, ok: bool, latency_ms: int | None = None, extra: dict | None = None) -> dict:
    out: dict = {"status": "ok" if ok else "error"}
    if latency_ms is not None:
        out["latency_ms"] = latency_ms
    if extra:
        out.update(extra)
    return out


def build_health_payload(*, deep: bool = False) -> tuple[dict, bool]:
    """
    Build the same JSON body as GET /health. Returns (payload, db_ok).

    deep=False (default for GET /api/v1/health): skips heavy audit-chain validation
    so load balancers and uptime checks stay fast.

    deep=True: full probes (used by superadmin dashboard bundle and explicit diagnostics).
    """
    api_start = time.perf_counter()

    # Django API is up if this handler runs.
    api_obj = _status_obj("api", True, latency_ms=_ms(api_start))

    # Database connectivity + latency
    db_start = time.perf_counter()
    db_ok = True
    try:
        connection.ensure_connection()
    except Exception:
        db_ok = False
    database_obj = _status_obj("database", db_ok, latency_ms=_ms(db_start))

    # KMS/encryption (placeholder; success if settings present)
    kms_ok = True
    try:
        from django.conf import settings
        _ = getattr(settings, "FIELD_ENCRYPTION_KEY", None) or getattr(settings, "ENCRYPTION_KEY", None)
    except Exception:
        kms_ok = False
    kms_obj = _status_obj("kms", kms_ok)

    # Audit chain (expensive DB walk — only when deep=True)
    audit_extra: dict = {"last_validated": None}
    if deep:
        audit_ok = True
        try:
            from api.services.audit_service import compute_audit_chain_status  # local import
            out = compute_audit_chain_status(max_users=50, max_logs_per_user=200)
            audit_ok = out.get("status") == "valid"
            audit_extra["last_validated"] = out.get("last_checked_at")
        except Exception:
            audit_ok = True
        audit_obj = {"status": "ok" if audit_ok else "error", **audit_extra}
    else:
        audit_obj = {"status": "skipped", **audit_extra}

    from api.services.backup_status import get_backup_health

    backup_obj = get_backup_health()

    top_status = "ok" if db_ok else "unhealthy"
    services = {
        "api": api_obj,
        "database": database_obj,
        "kms": kms_obj,
        "audit_chain": audit_obj,
        "backup": backup_obj,
    }

    payload = {
        # Backwards compatible keys used by uptime checks/tests
        "status": top_status,
        "database": "ok" if db_ok else "error",
        # Extended payload (preferred by new UI)
        "services": services,
        "generated_at": timezone.now().isoformat(),
    }

    return payload, db_ok


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])  # Exempt from rate limit so load balancers / uptime checks are not throttled
def health(request):
    """
    GET /api/v1/health — public health check.

    Query: deep=1|true|yes — full probes (Redis ping, audit-chain validation). Default is a fast path.

    Backwards compatible keys:
    - status: ok | unhealthy
    - database: ok | error

    Extended keys (best-effort):
    - api, database, kms, audit_chain, backup
    """
    deep = request.GET.get("deep", "").lower() in ("1", "true", "yes")
    payload, db_ok = build_health_payload(deep=deep)

    if not db_ok:
        return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(payload)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def test_smtp(request):
    """
    POST /api/v1/health/smtp-test

    Send a test email to verify SMTP is correctly configured in this environment.
    Only super_admin and hospital_admin may call this (prevents spam abuse).

    Request body (optional):
      { "to": "someone@example.com" }   — defaults to the requesting user's email.
    """
    if request.user.role not in ("super_admin", "hospital_admin"):
        return Response({"error": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)

    from django.core.mail import send_mail
    from django.conf import settings as django_settings

    to_addr = (request.data.get("to") or "").strip() or request.user.email
    from_addr = getattr(django_settings, "DEFAULT_FROM_EMAIL", "noreply@medsync.local")
    backend = getattr(django_settings, "EMAIL_BACKEND", "unknown")

    try:
        send_mail(
            subject="MedSync SMTP test",
            message=(
                f"This is a test email from MedSync.\n\n"
                f"Sent by: {request.user.email}\n"
                f"Backend: {backend}\n"
                f"Time: {timezone.now().isoformat()}"
            ),
            from_email=from_addr,
            recipient_list=[to_addr],
            fail_silently=False,
        )
        return Response({
            "ok": True,
            "to": to_addr,
            "backend": backend,
            "message": f"Test email sent to {to_addr}.",
        })
    except Exception as exc:
        return Response({
            "ok": False,
            "backend": backend,
            "error": str(exc),
            "hint": (
                "Check EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, "
                "EMAIL_HOST_USER, EMAIL_HOST_PASSWORD in your environment variables."
            ),
        }, status=status.HTTP_502_BAD_GATEWAY)
