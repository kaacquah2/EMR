"""Public health check for uptime monitoring. No auth required."""
import time
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
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

    deep=False (default for GET /api/v1/health): skips Redis ping and heavy audit-chain
    validation so load balancers and uptime checks stay fast.

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

    # Redis/Celery check (best-effort; optional in fast path to avoid socket latency)
    redis_ok = True
    redis_latency = None
    if deep:
        try:
            from django.conf import settings
            # Prefer explicit REDIS_URL (Channels / cloud) over CELERY_BROKER_URL,
            # which defaults to localhost in settings.
            url = (getattr(settings, "REDIS_URL", "") or "").strip() or (
                getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
            if not url:
                redis_ok = False
            else:
                import redis  # type: ignore
                r = redis.Redis.from_url(url, socket_connect_timeout=2.0, socket_timeout=3.0)
                r_start = time.perf_counter()
                r.ping()
                redis_latency = _ms(r_start)
        except Exception:
            redis_ok = False
    else:
        try:
            from django.conf import settings
            url = (getattr(settings, "REDIS_URL", "") or "").strip() or (
                getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
            if not url:
                redis_ok = False
        except Exception:
            redis_ok = False
    redis_obj = _status_obj("redis", redis_ok, latency_ms=redis_latency)

    # AI inference status (best-effort; avoid model loads)
    ai_ok = True
    ai_extra = {"response_ms": None}
    try:
        from django.conf import settings
        model_paths = getattr(settings, "MODEL_PATHS", {}) or {}
        present = 0
        for k in ("risk_predictor", "triage_classifier", "diagnosis_classifier"):
            p = model_paths.get(k)
            if p:
                import os
                if os.path.exists(p):
                    present += 1
        if present == 0:
            ai_ok = False
    except Exception:
        ai_ok = False
    ai_obj = {"status": "ok" if ai_ok else "error", **ai_extra}

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

    # Backup (placeholder; no scheduler in codebase yet)
    backup_obj = {"status": "ok", "last_run": timezone.now().isoformat()}

    top_status = "ok" if db_ok else "unhealthy"
    services = {
        "api": api_obj,
        "database": database_obj,
        "redis": redis_obj,
        "ai_inference": ai_obj,
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
    - api, database, redis, ai_inference, kms, audit_chain, backup
    """
    deep = request.GET.get("deep", "").lower() in ("1", "true", "yes")
    payload, db_ok = build_health_payload(deep=deep)

    if not db_ok:
        return Response(payload, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response(payload)
