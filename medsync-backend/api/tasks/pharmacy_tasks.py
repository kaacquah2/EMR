"""
Pharmacy Celery tasks.

Scheduled tasks for monitoring drug inventory:
- check_expiring_stock_task: Daily task to find stock expiring within 30 days
"""

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from api.models import DrugStock, StockAlert
from core.models import Hospital
from api.signals_alerts import broadcast_stock_alert

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def check_expiring_stock_task(self):
    """
    Check for stock expiring within 30 days and create StockAlert records.
    
    Runs daily at midnight (via CELERY_BEAT_SCHEDULE) or on-demand.
    """
    try:
        expiry_threshold = timezone.now().date() + timedelta(days=30)
        
        # Find all stock expiring within 30 days but not yet expired
        expiring_stock = DrugStock.objects.filter(
            expiry_date__lte=expiry_threshold,
            expiry_date__gt=timezone.now().date(),
            quantity__gt=0
        )
        
        alert_count = 0
        for stock in expiring_stock:
            # Check if alert already exists
            existing = StockAlert.objects.filter(
                drug_stock=stock,
                alert_type='expiring_soon',
                status='active'
            ).exists()
            
            if not existing:
                days_to_expiry = (stock.expiry_date - timezone.now().date()).days
                alert = StockAlert.objects.create(
                    hospital=stock.hospital,
                    drug_stock=stock,
                    alert_type='expiring_soon',
                    message=f"{stock.drug_name} (Batch {stock.batch_number}) expires in {days_to_expiry} days "
                            f"({stock.expiry_date.isoformat()}). Current stock: {stock.quantity} {stock.unit}",
                    severity='warning' if days_to_expiry > 7 else 'critical',
                    status='active'
                )
                broadcast_stock_alert(alert)
                alert_count += 1
                logger.info(f"Expiry alert created for {stock.drug_name} at {stock.hospital.name}")
        
        # Also check for already-expired stock
        expired_stock = DrugStock.objects.filter(
            expiry_date__lte=timezone.now().date(),
            quantity__gt=0
        )
        
        for stock in expired_stock:
            existing = StockAlert.objects.filter(
                drug_stock=stock,
                alert_type='expired',
                status='active'
            ).exists()
            
            if not existing:
                alert = StockAlert.objects.create(
                    hospital=stock.hospital,
                    drug_stock=stock,
                    alert_type='expired',
                    message=f"{stock.drug_name} (Batch {stock.batch_number}) EXPIRED on {stock.expiry_date.isoformat()}. "
                            f"Qty: {stock.quantity} {stock.unit}. MUST BE DESTROYED/REMOVED FROM STOCK.",
                    severity='critical',
                    status='active'
                )
                broadcast_stock_alert(alert)
                alert_count += 1
                logger.critical(f"EXPIRED STOCK ALERT for {stock.drug_name} at {stock.hospital.name}")
        
        logger.info(f"Expiry check complete: {alert_count} new alerts created")
        return {"status": "success", "alerts_created": alert_count}
    
    except Exception as exc:
        logger.error(f"Error in check_expiring_stock_task: {exc}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))

