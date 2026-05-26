"""Backup health probe — reports real status instead of a placeholder 'ok'."""

from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

BACKUP_CACHE_KEY = "backup:last_success_at"
BACKUP_META_CACHE_KEY = "backup:last_meta"


def record_backup_success(*, destination: str = "", size_bytes: int | None = None) -> None:
    """Call from the Celery/pg_dump backup task when a run completes successfully."""
    meta = {
        "recorded_at": timezone.now().isoformat(),
        "destination": destination,
        "size_bytes": size_bytes,
    }
    cache.set(BACKUP_CACHE_KEY, meta["recorded_at"], timeout=None)
    cache.set(BACKUP_META_CACHE_KEY, meta, timeout=None)


def get_backup_health() -> dict:
    """
    Return backup subsystem status for /api/v1/health.

    - not_configured: no BACKUP_ENABLED and no recorded run
    - stale: last success older than BACKUP_MAX_AGE_HOURS
    - ok: recent successful backup recorded
    - unknown: BACKUP_ENABLED but never recorded a success
    """
    enabled = bool(getattr(settings, "BACKUP_ENABLED", False))
    max_age_hours = int(getattr(settings, "BACKUP_MAX_AGE_HOURS", 26))
    last_run = cache.get(BACKUP_CACHE_KEY)
    meta = cache.get(BACKUP_META_CACHE_KEY) or {}

    if not last_run:
        if not enabled:
            return {
                "status": "not_configured",
                "message": "Backup scheduler not enabled (set BACKUP_ENABLED=true when configured).",
                "last_run": None,
            }
        return {
            "status": "unknown",
            "message": "BACKUP_ENABLED but no successful backup has been recorded yet.",
            "last_run": None,
        }

    try:
        from django.utils.dateparse import parse_datetime

        dt = parse_datetime(str(last_run))
        if dt is not None and timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        age_hours = (
            (timezone.now() - dt).total_seconds() / 3600 if dt is not None else max_age_hours + 1
        )
    except Exception:
        age_hours = max_age_hours + 1

    payload = {
        "status": "ok" if age_hours <= max_age_hours else "stale",
        "last_run": last_run,
        "age_hours": round(age_hours, 2),
        "max_age_hours": max_age_hours,
    }
    if meta:
        payload["destination"] = meta.get("destination") or ""
    if payload["status"] == "stale":
        payload["message"] = (
            f"Last backup is {payload['age_hours']:.1f}h old (max {max_age_hours}h)."
        )
    return payload
