"""
Celery configuration for MedSync EMR.

Handles async tasks for:
- PDF exports
- AI analysis jobs
- Scheduled no-show marking
- Email notifications
"""
import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

app = Celery("medsync")

# Load configuration from Django settings with namespace 'CELERY'
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    """Debug task for testing Celery connectivity."""
    print(f"Request: {self.request!r}")
