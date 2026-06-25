"""
Appointment and no-show background tasks.

These run synchronously (via execute_task_sync_or_async) or as a management
command (python manage.py mark_no_shows) invoked by cron every 15 minutes.
"""
import logging
from django.utils import timezone
from datetime import timedelta

logger = logging.getLogger(__name__)


def run_mark_no_shows():
    """
    Mark overdue scheduled appointments as no-shows.

    Checks appointments that have:
    - status = "scheduled"
    - scheduled_at < now - grace_period (default 15 min)
    - not yet marked (no_show_marked_at is null)

    Returns:
        dict with count of marked appointments
    """
    from patients.models import Appointment
    from core.models import AuditLog
    from django.conf import settings

    grace_period_minutes = getattr(settings, "NO_SHOW_GRACE_PERIOD_MINUTES", 15)
    grace_period = timedelta(minutes=grace_period_minutes)
    cutoff_time = timezone.now() - grace_period

    no_show_appointments = Appointment.objects.filter(
        status="scheduled",
        scheduled_at__lt=cutoff_time,
        no_show_marked_at__isnull=True,
    )

    count = 0
    for appointment in no_show_appointments:
        try:
            appointment.status = "no_show"
            appointment.no_show_marked_at = timezone.now()
            appointment.save()

            AuditLog.objects.create(
                user=None,
                action="NO_SHOW_AUTO_MARKED",
                resource_type="appointment",
                resource_id=appointment.id,
                hospital=appointment.hospital,
                ip_address="0.0.0.0",
                user_agent="cron-task",
            )
            count += 1
            logger.info("Marked appointment %s as no-show", appointment.id)
        except Exception as e:
            logger.error("Error marking appointment %s as no-show: %s", appointment.id, e)

    logger.info("Marked %d appointments as no-show", count)
    return {"status": "success", "marked_count": count}


# Keep these names so existing callers (execute_task_sync_or_async) don't break.
def mark_no_shows_task():
    """Alias kept for backwards compatibility with callers."""
    return run_mark_no_shows()


