"""
Celery tasks for appointment and no-show functionality.
"""
from celery import shared_task
from celery.utils.log import get_task_logger
from django.utils import timezone
from datetime import timedelta

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def mark_no_shows_task(self):
    """
    Scheduled task (runs every 15 minutes) to auto-mark no-shows.
    
    Checks appointments that have:
    - Status = "SCHEDULED"
    - scheduled_at < now - grace_period (default 15 min)
    - not yet marked as no_show (no_show_marked_at is null)
    
    Returns:
        dict with count of marked appointments
    """
    try:
        from patients.models import Appointment
        from core.models import AuditLog
        from django.conf import settings
        
        grace_period_minutes = getattr(settings, "NO_SHOW_GRACE_PERIOD_MINUTES", 15)
        grace_period = timedelta(minutes=grace_period_minutes)
        
        # Find appointments that should be marked as no-show
        cutoff_time = timezone.now() - grace_period
        
        no_show_appointments = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff_time,
            no_show_marked_at__isnull=True,  # Not yet marked
        )
        
        count = 0
        for appointment in no_show_appointments:
            try:
                appointment.status = "no_show"
                appointment.no_show_marked_at = timezone.now()
                appointment.save()
                
                # Log audit event
                AuditLog.objects.create(
                    user=None,  # System-generated
                    action="NO_SHOW_AUTO_MARKED",
                    resource_type="appointment",
                    resource_id=appointment.id,
                    hospital=appointment.hospital,
                    ip_address="0.0.0.0",
                    user_agent="celery-task",
                )
                
                count += 1
                logger.info(f"Marked appointment {appointment.id} as no-show")
            except Exception as e:
                logger.error(f"Error marking appointment {appointment.id} as no-show: {e}")
                continue
        
        logger.info(f"Marked {count} appointments as no-show")
        return {"status": "success", "marked_count": count}
    
    except Exception as exc:
        logger.error(f"Error in mark_no_shows_task: {exc}")
        raise self.retry(exc=exc, countdown=5 ** self.request.retries)


@shared_task(bind=True, max_retries=2)
def send_no_show_notification_task(self, appointment_id, provider_email):
    """
    Send notification to provider that appointment was marked as no-show.
    
    Args:
        appointment_id: UUID of appointment
        provider_email: Email of provider to notify
    """
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        
        logger.info(f"Sending no-show notification for appointment {appointment_id}")
        
        subject = "[MedSync] Appointment marked as no-show"
        body = (
            f"Appointment {appointment_id} was automatically marked as no-show.\n"
            f"To undo this, contact your administrator.\n"
        )
        
        send_mail(
            subject,
            body,
            settings.DEFAULT_FROM_EMAIL,
            [provider_email],
            fail_silently=True,
        )
        
        logger.info(f"Sent no-show notification to {provider_email}")
        return {"status": "success", "appointment_id": str(appointment_id)}
    
    except Exception as exc:
        logger.error(f"Error sending no-show notification: {exc}")
        raise self.retry(exc=exc, countdown=60)
