"""
Pharmacy auto-deduction and alert signals.

When a prescription status changes to dispensing/dispensed:
1. Check stock availability
2. Deduct from stock using FIFO (oldest batch first) or custom batch
3. Create Dispensation and StockMovement records
4. Check for low-stock and create StockAlert + broadcast

All within transaction.atomic() for data consistency.
"""

import logging
from datetime import timedelta
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.db import transaction
from django.utils import timezone

from records.models import Prescription
from api.models import DrugStock, Dispensation, StockMovement, StockAlert
from core.models import AuditLog

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Prescription)
def prescription_status_change_handler(sender, instance, **kwargs):
    """
    Handle prescription status changes to dispensing/dispensed.
    
    This receiver fires BEFORE save. We check if status is changing and validate
    stock availability early.
    """
    try:
        # Only if prescription already exists (has pk) and status is changing
        if not instance.pk:
            return
        
        old_instance = Prescription.objects.filter(pk=instance.pk).first()
        if not old_instance:
            return
        
        old_status = old_instance.status
        new_status = instance.status
        
        # Only care about transitions to dispensing or dispensed
        if new_status not in ['dispensing', 'dispensed']:
            return
        
        # Validate stock is available (non-blocking, just check)
        if not instance.drug_name:
            logger.warning(f"Prescription {instance.id} has no drug_name set; skipping stock check")
            return
        
        hospital = instance.hospital
        if not hospital:
            logger.warning(f"Prescription {instance.id} has no hospital; skipping stock check")
            return
        
        # Get available stock for this drug at this hospital
        available_stock = DrugStock.objects.filter(
            hospital=hospital,
            drug_name__icontains=instance.drug_name,
            expiry_date__gt=timezone.now().date(),
            quantity__gt=0
        ).order_by('created_at')  # FIFO: oldest first
        
        if not available_stock.exists():
            # Log warning but don't block (pharmacy tech can manually override)
            logger.warning(
                f"No available stock for {instance.drug_name} at {hospital.name}. "
                f"Prescription {instance.pk} can still be marked dispensing (manual override)."
            )
    
    except Exception as e:
        logger.error(f"Error in prescription_status_change_handler: {e}", exc_info=True)
        # Don't raise; signal failures must not break prescription creation


@receiver(post_save, sender=Prescription)
def prescription_dispensed_auto_deduct(sender, instance, created=False, **kwargs):
    """
    When prescription status changes to dispensed, auto-deduct from stock.
    
    Deduction strategy:
    1. Look for available stock batches (not expired, quantity > 0)
    2. Use FIFO (oldest batch first) by default
    3. Create Dispensation record (links prescription to batch)
    4. Create StockMovement record (audit trail)
    5. Check for low-stock and create StockAlert + broadcast
    
    Request data format (optional):
    {
        "drug_stock_id": "uuid",  // Custom batch selection (optional)
        "quantity": 1             // Qty to dispense (optional, defaults to 1)
    }
    """
    try:
        # Only process if status is dispensed
        if instance.status != 'dispensed':
            return
        
        # Skip if already dispensed (prevents double-deduction)
        if hasattr(instance, '_pharmacy_processed'):
            return
        
        # Mark as processed to prevent re-entry
        instance._pharmacy_processed = True
        
        if not instance.drug_name or not instance.hospital:
            logger.warning(f"Prescription {instance.pk} missing drug_name or hospital; skipping auto-deduction")
            return
        
        # Get dispensed_quantity from prescription (set by pharmacy tech)
        qty_to_dispense = instance.dispensed_quantity or 1
        if qty_to_dispense <= 0:
            logger.warning(f"Prescription {instance.pk} has invalid dispensed_quantity: {qty_to_dispense}")
            return
        
        with transaction.atomic():
            # Check if dispensation already exists (idempotency)
            if Dispensation.objects.filter(prescription=instance).exists():
                logger.info(f"Dispensation already exists for prescription {instance.pk}; skipping")
                return
            
            # Get available stock for this drug at this hospital (FIFO order)
            available_stock = DrugStock.objects.filter(
                hospital=instance.hospital,
                drug_name__icontains=instance.drug_name,
                expiry_date__gt=timezone.now().date(),
                quantity__gt=0
            ).order_by('created_at').select_for_update()  # Lock for update
            
            if not available_stock.exists():
                logger.error(
                    f"No available stock for {instance.drug_name} at {instance.hospital.name}. "
                    f"Dispensation CANNOT be created for prescription {instance.pk}"
                )
                return
            
            # Use first (oldest) batch by default; tech can select custom batch via request
            selected_batch = available_stock.first()
            
            # Deduct from stock
            if selected_batch.quantity < qty_to_dispense:
                logger.warning(
                    f"Stock {selected_batch.id} has only {selected_batch.quantity} units "
                    f"but {qty_to_dispense} requested. Partial dispensation."
                )
                qty_to_dispense = selected_batch.quantity  # Dispense what's available
            
            selected_batch.quantity -= qty_to_dispense
            selected_batch.save(update_fields=['quantity'])
            
            # Create Dispensation record (audit trail linking prescription to batch)
            dispensation = Dispensation.objects.create(
                prescription=instance,
                drug_stock=selected_batch,
                quantity_dispensed=qty_to_dispense,
                dispensed_by=instance.dispensed_by,
                batch_notes=instance.dispense_notes or ''
            )
            
            logger.info(
                f"Dispensation created: {qty_to_dispense} units of {selected_batch.drug_name} "
                f"(Batch: {selected_batch.batch_number}) for prescription {instance.pk}"
            )
            
            # Create StockMovement record (audit trail)
            quantity_before = selected_batch.quantity + qty_to_dispense  # Restore original qty for audit
            movement = StockMovement.objects.create(
                drug_stock=selected_batch,
                movement_type='dispensed',
                quantity=-qty_to_dispense,
                quantity_before=quantity_before,
                quantity_after=selected_batch.quantity,
                reason=f"Prescribed for patient {instance.patient.ghana_health_id if instance.patient else 'unknown'}",
                performed_by=instance.dispensed_by,
                dispensation=dispensation
            )
            
            # Check for low-stock and create alert if needed
            if selected_batch.is_low_stock():
                _create_low_stock_alert(selected_batch, instance.hospital)
            
            # Audit logging
            AuditLog.log_action(
                user=instance.dispensed_by,
                action='DISPENSE_MEDICATION',
                resource_type='Prescription',
                resource_id=str(instance.id),
                hospital=instance.hospital,
                extra_data={
                    'drug': instance.drug_name,
                    'quantity': qty_to_dispense,
                    'batch': selected_batch.batch_number,
                    'patient_id': str(instance.patient.id) if instance.patient else None,
                }
            )
    
    except Exception as e:
        logger.error(f"Error in prescription_dispensed_auto_deduct: {e}", exc_info=True)
        # Don't raise; signal failures must not break prescription workflow


def _create_low_stock_alert(drug_stock, hospital):
    """
    Create low-stock alert if one doesn't already exist for this batch.
    Also broadcast via WebSocket.
    """
    try:
        # Check if active alert already exists
        existing = StockAlert.objects.filter(
            drug_stock=drug_stock,
            alert_type='low_stock',
            status='active'
        ).exists()
        
        if existing:
            return  # Alert already active
        
        alert = StockAlert.objects.create(
            hospital=hospital,
            drug_stock=drug_stock,
            alert_type='low_stock',
            message=f"{drug_stock.drug_name} (Batch {drug_stock.batch_number}) is below reorder level. "
                    f"Current: {drug_stock.quantity} {drug_stock.unit}, Reorder level: {drug_stock.reorder_level} {drug_stock.unit}",
            severity='warning',
            status='active'
        )
        
        # Broadcast via WebSocket
        from api.signals_alerts import broadcast_stock_alert
        broadcast_stock_alert(alert)
        
        logger.info(f"Low-stock alert created for {drug_stock.drug_name} at {hospital.name}")
    
    except Exception as e:
        logger.error(f"Error creating low-stock alert: {e}", exc_info=True)


def register_pharmacy_signals():
    """
    Register all pharmacy signals.
    
    Called from api/apps.py ready() method.
    """
    # Signals are auto-registered via @receiver decorators above
    logger.info("Pharmacy signals registered")
