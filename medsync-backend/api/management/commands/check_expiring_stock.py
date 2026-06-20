"""
Management command: check_expiring_stock

Creates StockAlert records for drug stock expiring within 30 days or already expired.
Run daily via cron:

    0 6 * * *  cd /app && python manage.py check_expiring_stock >> /var/log/medsync/expiry.log 2>&1
"""
import logging
from django.core.management.base import BaseCommand
from api.tasks.pharmacy_tasks import check_expiring_stock_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Create StockAlert records for expiring/expired drug stock (run daily via cron)."

    def handle(self, *args, **options):
        # hospital=None → scan all hospitals (cron / system-wide check)
        result = check_expiring_stock_task(hospital=None)
        alerts = result.get("alerts_created", 0)
        self.stdout.write(
            self.style.SUCCESS(f"check_expiring_stock: {alerts} new alert(s) created.")
        )
