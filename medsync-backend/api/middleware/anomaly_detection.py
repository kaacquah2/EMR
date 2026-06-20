"""
Anomaly Detection Middleware

Monitors user behavior and alerts on suspicious patterns.
Rule: Alert if user accesses >200 unique patients in 1 hour.

Uses Redis SET (SADD/SCARD/EXPIRE) when available; falls back to Django cache.
"""

import logging
import re
import time

from django.core.cache import cache

logger = logging.getLogger(__name__)

PATIENT_ACCESS_THRESHOLD: int = 200
WINDOW_SECONDS = 3600


def _redis_client():
    try:
        from django.conf import settings

        url = (getattr(settings, "REDIS_URL", "") or "").strip() or (
            getattr(settings, "CELERY_BROKER_URL", "") or ""
        ).strip()
        if not url:
            return None
        import redis

        return redis.Redis.from_url(url, socket_connect_timeout=2.0, socket_timeout=3.0)
    except Exception:
        return None


def _track_with_redis(user_id: str, patient_id: str) -> tuple[bool, int]:
    """Redis SET + EXPIRE — shared across all ASGI workers."""
    client = _redis_client()
    if client is None:
        return False, 0

    key = f"anomaly:patients:{user_id}"
    try:
        pipe = client.pipeline()
        pipe.sadd(key, patient_id)
        pipe.expire(key, WINDOW_SECONDS)
        pipe.scard(key)
        _, _, count = pipe.execute()
        count = int(count)
        return count > PATIENT_ACCESS_THRESHOLD, count
    except Exception as exc:
        logger.debug("Redis anomaly tracking unavailable: %s", exc)
        return False, 0


def _track_with_cache(user_id: str, patient_id: str) -> tuple[bool, int]:
    cache_key = f"anomaly:patient_access:{user_id}"
    now = time.time()

    data = cache.get(cache_key)
    if data is None:
        patients = [patient_id]
        window_start = now
    else:
        if isinstance(data, dict):
            raw = data.get("patients", [])
            patients = list(raw) if isinstance(raw, (list, tuple)) else list(raw or [])
            window_start = data.get("window_start", now)
        else:
            patients = [patient_id]
            window_start = now

        if now - window_start > WINDOW_SECONDS:
            patients = [patient_id]
            window_start = now
        elif patient_id not in patients:
            patients.append(patient_id)

    patient_count = len(patients)
    remaining_ttl = int((window_start + WINDOW_SECONDS) - now)
    if remaining_ttl > 0:
        cache.set(
            cache_key,
            {"patients": patients, "window_start": window_start},
            timeout=remaining_ttl,
        )
    else:
        cache.delete(cache_key)

    return patient_count > PATIENT_ACCESS_THRESHOLD, patient_count


def track_patient_access(user_id: str, patient_id: str) -> tuple[bool, int]:
    """
    Track unique patient access in a 1-hour window.
    Returns (is_anomaly, unique_patient_count).

    Prefers Redis (shared across all workers) so counts are accurate in
    multi-process deployments.  Falls back to Django cache when Redis is
    unavailable:
    - DatabaseCache (production default): shared across workers; the 200-patient
      threshold is enforced correctly, though concurrent updates may be off by
      a small margin (no atomic set-union).
    - LocMemCache (Vercel / single-worker dev): per-process; threshold is only
      enforced within a single process.  A startup warning is logged to make
      this limitation visible.
    """
    is_anomaly_redis, count_redis = _track_with_redis(user_id, patient_id)
    if count_redis > 0 or is_anomaly_redis:
        return is_anomaly_redis, count_redis

    # Redis unavailable — fall back to Django cache.
    from django.conf import settings
    cache_backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if "LocMemCache" in cache_backend:
        logger.warning(
            "Anomaly detection is using LocMemCache (per-process). "
            "The %d-patient threshold is not enforced across multiple workers. "
            "Configure REDIS_URL for accurate cross-worker anomaly detection.",
            PATIENT_ACCESS_THRESHOLD,
        )
    return _track_with_cache(user_id, patient_id)


def reset_patient_access(user_id: str) -> None:
    key = f"anomaly:patients:{user_id}"
    client = _redis_client()
    if client is not None:
        try:
            client.delete(key)
        except Exception:
            pass
    cache.delete(f"anomaly:patient_access:{user_id}")


def create_anomaly_alert(user, patient_count: int, window_hours: int) -> None:
    from core.models import AuditLog

    try:
        AuditLog.objects.create(
            user=user,
            action="ANOMALY_DETECTED",
            resource_type="SecurityAlert",
            # resource_id is a CharField(max_length=64) — keep it as a string.
            resource_id=f"patient_access_{user.id}"[:64],
            hospital=getattr(user, "hospital", None),
            # ip_address is a GenericIPAddressField; "system" is not a valid IP.
            # Use None (allowed because the field is nullable) for non-request events.
            ip_address=None,
            # The correct field name on AuditLog is extra_data (JSONField).
            extra_data={
                "alert_type": "excessive_patient_access",
                "patient_count": patient_count,
                "window_hours": window_hours,
                "threshold": PATIENT_ACCESS_THRESHOLD,
                "message": (
                    f"User accessed {patient_count} patients in {window_hours} hour(s)"
                ),
            },
        )
        logger.warning(
            "ANOMALY ALERT: User %s accessed %s patients in %s hour(s) (threshold: %s)",
            user.email,
            patient_count,
            window_hours,
            PATIENT_ACCESS_THRESHOLD,
        )
    except Exception as exc:
        logger.error("Failed to create anomaly alert: %s", exc)


class AnomalyDetectionMiddleware:
    """Django middleware to detect anomalous user behavior."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.patient_patterns = [
            r"/api/v1/patients/([a-f0-9-]+)",
            r"/api/v1/patients/([a-f0-9-]+)/records",
            r"/api/v1/patients/([a-f0-9-]+)/encounters",
            r"/api/v1/patients/([a-f0-9-]+)/vitals",
        ]

    def __call__(self, request):
        self._track_access(request)
        return self.get_response(request)

    def _track_access(self, request) -> None:
        if not hasattr(request, "user") or not request.user.is_authenticated:
            return

        for pattern in self.patient_patterns:
            match = re.search(pattern, request.path)
            if not match:
                continue

            patient_id = match.group(1)
            user_id = str(request.user.id)
            is_anomaly, patient_count = track_patient_access(user_id, patient_id)

            if is_anomaly:
                create_anomaly_alert(request.user, patient_count, WINDOW_SECONDS // 3600)
                reset_patient_access(user_id)
            break

