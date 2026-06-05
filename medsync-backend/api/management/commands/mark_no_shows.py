"""
Management command: mark_no_shows

Marks overdue scheduled appointments as no-shows.
Run every 15 minutes via cron:

    */15 * * * *  cd /app && python manage.py mark_no_shows >> /var/log/mark_no_shows.log 2>&1
"""
import logging
from django.core.management.base import BaseCommand
from api.tasks.appointment_tasks import run_mark_no_shows

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Mark overdue scheduled appointments as no-shows (run every 15 min via cron)."

    def handle(self, *args, **options):
        result = run_mark_no_shows()
        marked = result.get("marked_count", 0)
        self.stdout.write(
            self.style.SUCCESS(f"mark_no_shows: {marked} appointment(s) marked as no-show.")
        )
