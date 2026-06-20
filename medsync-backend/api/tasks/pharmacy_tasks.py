"""
Pharmacy background tasks.

check_expiring_stock_task: Check drug inventory for expiring/expired stock.
Run daily via cron: python manage.py check_expiring_stock
"""

import logging
from datetime import timedelta

from django.utils import timezone

from api.models import DrugStock, StockAlert
logger = logging.getLogger(__name__)


def check_expiring_stock_task(hospital=None):
    """
    Check for stock expiring within 30 days and create StockAlert records.

    Args:
        hospital: Scope to a single Hospital instance. When None (cron path),
                  all hospitals are checked. Always pass a hospital when called
                  from an HTTP request to avoid cross-tenant alert creation.

    Runs daily (via management command / cron) or on-demand.
    """
    today = timezone.now().date()
    expiry_threshold = today + timedelta(days=30)

    base_qs = DrugStock.objects.all()
    if hospital is not None:
        base_qs = base_qs.filter(hospital=hospital)

    expiring_stock = base_qs.filter(
        expiry_date__lte=expiry_threshold,
        expiry_date__gt=today,
        quantity__gt=0,
    )

    alert_count = 0
    for stock in expiring_stock:
        existing = StockAlert.objects.filter(
            drug_stock=stock,
            alert_type='expiring_soon',
            status='active',
        ).exists()

        if not existing:
            days_to_expiry = (stock.expiry_date - today).days
            StockAlert.objects.create(
                hospital=stock.hospital,
                drug_stock=stock,
                alert_type='expiring_soon',
                message=(
                    f"{stock.drug_name} (Batch {stock.batch_number}) expires in {days_to_expiry} days "
                    f"({stock.expiry_date.isoformat()}). Current stock: {stock.quantity} {stock.unit}"
                ),
                severity='warning' if days_to_expiry > 7 else 'critical',
                status='active',
            )
            alert_count += 1
            logger.info("Expiry alert created for %s at %s", stock.drug_name, stock.hospital.name)

    expired_stock = base_qs.filter(
        expiry_date__lte=today,
        quantity__gt=0,
    )

    for stock in expired_stock:
        existing = StockAlert.objects.filter(
            drug_stock=stock,
            alert_type='expired',
            status='active',
        ).exists()

        if not existing:
            StockAlert.objects.create(
                hospital=stock.hospital,
                drug_stock=stock,
                alert_type='expired',
                message=(
                    f"{stock.drug_name} (Batch {stock.batch_number}) EXPIRED on "
                    f"{stock.expiry_date.isoformat()}. "
                    f"Qty: {stock.quantity} {stock.unit}. MUST BE REMOVED FROM STOCK."
                ),
                severity='critical',
                status='active',
            )
            alert_count += 1
            logger.critical("EXPIRED STOCK ALERT for %s at %s", stock.drug_name, stock.hospital.name)

    logger.info("Expiry check complete: %d new alerts created", alert_count)
    return {"status": "success", "alerts_created": alert_count}
