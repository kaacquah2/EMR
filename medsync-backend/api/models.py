"""
Clinical Decision Support (CDS) and Pharmacy Models.

Models:
- ClinicalRule: Rule-based CDS rules (drug interactions, allergy contraindications, etc.)
- CdsAlert: Alerts triggered when a prescription or diagnosis matches a rule
- DrugStock: Drug inventory tracked by batch
- Dispensation: Record of medication dispensed to a patient
- StockMovement: Audit trail for all stock changes
- StockAlert: Alert for low-stock or expiring medications
"""

from uuid import uuid4

from django.db import models
from django.utils import timezone

from core.models import Hospital, User
from records.models import Encounter, Prescription, Diagnosis
from .tenancy import TenantManager


def _default_list():
    """Helper for JSONField default empty list."""
    return []


def _default_dict():
    """Helper for JSONField default empty dict."""
    return {}


# ============================================================================
# Clinical Decision Support (CDS) Models
# ============================================================================

class ClinicalRule(models.Model):
    """
    Defines a clinical rule that triggers alerts.

    Examples:
    - Drug-drug interaction: warfarin + aspirin
    - Drug-allergy: amoxicillin for penicillin-allergic patient
    - Renal dosing: adjust for eGFR < 30
    - Duplicate therapy: two drugs in same class
    """

    RULE_TYPES = [
        ('drug_interaction', 'Drug-Drug Interaction'),
        ('drug_allergy', 'Drug-Allergy Contraindication'),
        ('renal_dosing', 'Renal Dose Adjustment'),
        ('duplicate_therapy', 'Duplicate Therapy'),
    ]

    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Human-readable rule name")
    rule_type = models.CharField(max_length=50, choices=RULE_TYPES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)

    # Condition and action stored as JSON for flexibility
    condition_json = models.JSONField(default=_default_dict, help_text="Rule condition parameters")
    action_json = models.JSONField(default=_default_dict, help_text="Alert message and metadata")

    active = models.BooleanField(default=True, help_text="Enable/disable this rule")
    description = models.TextField(blank=True, help_text="Detailed description of the rule")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_rules"
    )

    class Meta:
        indexes = [
            models.Index(fields=['rule_type', 'active']),
            models.Index(fields=['severity']),
        ]
        ordering = ['rule_type', '-severity', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_rule_type_display()})"


class CdsAlert(models.Model):
    """
    Records an alert triggered when a prescription or diagnosis is created.

    Alerts are informational and don't block prescription/diagnosis creation.
    They can be acknowledged by the doctor.
    """

    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)

    # Link to encounter and triggered rule
    encounter = models.ForeignKey(
        Encounter, on_delete=models.PROTECT, related_name="cds_alerts"
    )
    rule = models.ForeignKey(
        ClinicalRule, on_delete=models.PROTECT, related_name="alerts"
    )

    # Prescription or diagnosis that triggered this alert (can be both)
    prescription = models.ForeignKey(
        Prescription, null=True, blank=True, on_delete=models.CASCADE, related_name="cds_alerts"
    )
    diagnosis = models.ForeignKey(
        Diagnosis, null=True, blank=True, on_delete=models.CASCADE, related_name="cds_alerts"
    )

    # Alert metadata
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    message = models.TextField(help_text="Alert message to display to doctor")

    # Extra context (e.g. drug names, lab values, etc.)
    context_data = models.JSONField(
        default=_default_dict, help_text="Additional context for the alert"
    )

    # Acknowledgment tracking
    acknowledged = models.BooleanField(default=False, help_text="Has doctor acknowledged this alert?")
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="acknowledged_cds_alerts"
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    acknowledgment_notes = models.TextField(blank=True, help_text="Doctor's notes on acknowledgment")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['encounter', '-created_at']),
            models.Index(fields=['encounter', 'acknowledged']),
            models.Index(fields=['severity']),
            models.Index(fields=['rule', 'severity']),
        ]
        ordering = ['-severity', '-created_at']

    def __str__(self):
        return f"CDS Alert: {self.rule.name} (Encounter: {self.encounter.id})"

    def acknowledge(self, user, notes=""):
        """Mark alert as acknowledged by a doctor."""
        self.acknowledged = True
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.acknowledgment_notes = notes
        self.save(update_fields=[
            'acknowledged', 'acknowledged_by', 'acknowledged_at', 'acknowledgment_notes'
        ])


# ============================================================================
# PHARMACY MODELS: Drug Inventory, Dispensation, Stock Tracking, Alerts
# ============================================================================


class DrugStock(models.Model):
    """
    Drug inventory tracked by batch.

    Each batch has a unique combination of drug, hospital, batch_number, and expiry_date.
    Quantity can be decremented as drugs are dispensed.
    """

    UNIT_CHOICES = [
        ('tablets', 'Tablets'),
        ('capsules', 'Capsules'),
        ('mL', 'Milliliters'),
        ('L', 'Liters'),
        ('grams', 'Grams'),
        ('mg', 'Milligrams'),
        ('vials', 'Vials'),
        ('ampoules', 'Ampoules'),
        ('units', 'Units'),
        ('patches', 'Patches'),
        ('tubes', 'Tubes'),
        ('inhalers', 'Inhalers'),
        ('sprays', 'Sprays'),
        ('drops', 'Drops'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='drug_stock')
    drug_name = models.CharField(max_length=200, help_text="Brand name or common name")
    generic_name = models.CharField(max_length=200, blank=True, help_text="Generic/active ingredient")
    batch_number = models.CharField(max_length=50, help_text="Manufacturer batch/lot number")
    quantity = models.PositiveIntegerField(help_text="Current quantity in stock")
    unit = models.CharField(max_length=20, choices=UNIT_CHOICES, help_text="Unit of measurement")
    reorder_level = models.PositiveIntegerField(help_text="Minimum quantity before alert")
    expiry_date = models.DateField(help_text="Expiration date of batch")
    created_at = models.DateTimeField(auto_now_add=True)

    tenant_objects = TenantManager()

    class Meta:
        db_table = 'pharmacy_drug_stock'
        unique_together = ('hospital', 'drug_name', 'batch_number', 'expiry_date')
        indexes = [
            models.Index(fields=['hospital', '-created_at']),
            models.Index(fields=['hospital', 'expiry_date']),
            models.Index(fields=['drug_name', 'hospital']),
        ]

    def __str__(self):
        return f"{self.drug_name} (Batch: {self.batch_number}) @ {self.hospital.name}"

    def is_low_stock(self):
        """Check if quantity is below reorder level."""
        return self.quantity < self.reorder_level

    def is_expiring_soon(self, days=30):
        """Check if expiry date is within specified days."""
        from datetime import timedelta
        cutoff = timezone.now().date() + timedelta(days=days)
        return self.expiry_date <= cutoff

    def is_expired(self):
        """Check if batch is already expired."""
        return self.expiry_date <= timezone.now().date()


class Dispensation(models.Model):
    """
    Record of medication dispensed to a patient.

    Immutable audit trail linking prescription → stock batch → quantity dispensed.
    """

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    prescription = models.ForeignKey(Prescription, on_delete=models.CASCADE, related_name='dispensations')
    drug_stock = models.ForeignKey(DrugStock, on_delete=models.PROTECT, related_name='dispensations')
    quantity_dispensed = models.PositiveIntegerField(help_text="Quantity given to patient")
    dispensed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='dispensed_medications')
    dispensed_at = models.DateTimeField(auto_now_add=True)
    batch_notes = models.TextField(blank=True, help_text="Pharmacy notes on dispensation")

    class Meta:
        db_table = 'pharmacy_dispensation'
        indexes = [
            models.Index(fields=['drug_stock', '-dispensed_at']),
            models.Index(fields=['dispensed_by', '-dispensed_at']),
        ]

    def __str__(self):
        return f"Dispensed {self.quantity_dispensed}{self.drug_stock.unit} of {self.drug_stock.drug_name}"


class StockMovement(models.Model):
    """
    Audit trail for all stock changes.

    Tracks received, dispensed, adjusted, expired, and damaged movements.
    """

    MOVEMENT_TYPES = [
        ('received', 'Stock Received'),
        ('dispensed', 'Dispensed to Patient'),
        ('adjustment', 'Manual Adjustment'),
        ('expired', 'Expired/Destroyed'),
        ('damaged', 'Damaged'),
        ('transfer', 'Transfer to Another Hospital'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    drug_stock = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    quantity = models.IntegerField(help_text="Positive = added, negative = removed")
    quantity_before = models.PositiveIntegerField(default=0, help_text="Stock quantity before movement")
    quantity_after = models.PositiveIntegerField(default=0, help_text="Stock quantity after movement")
    reason = models.TextField(blank=True, help_text="Reason for movement")
    performed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='stock_movements')
    dispensation = models.ForeignKey(
        Dispensation, null=True, blank=True, on_delete=models.SET_NULL,
        help_text="Link to dispensation if movement_type=dispensed"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pharmacy_stock_movement'
        indexes = [
            models.Index(fields=['drug_stock', '-created_at']),
            models.Index(fields=['movement_type', '-created_at']),
            models.Index(fields=['performed_by', '-created_at']),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} of {self.quantity} units"


class StockAlert(models.Model):
    """
    Alert for low-stock or expiring medications.

    Persists alert history for compliance and clinical review.
    """

    ALERT_TYPES = [
        ('low_stock', 'Low Stock'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Already Expired'),
    ]

    SEVERITY_CHOICES = [
        ('critical', 'Critical'),
        ('warning', 'Warning'),
        ('info', 'Info'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name='stock_alerts')
    drug_stock = models.ForeignKey(DrugStock, on_delete=models.CASCADE, related_name='alerts')
    alert_type = models.CharField(max_length=20, choices=ALERT_TYPES)
    message = models.TextField()
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='warning')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name='acknowledged_stock_alerts'
    )
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    tenant_objects = TenantManager()

    class Meta:
        db_table = 'pharmacy_stock_alert'
        indexes = [
            models.Index(fields=['hospital', 'status', '-created_at']),
            models.Index(fields=['drug_stock', '-created_at']),
            models.Index(fields=['alert_type', 'status']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.drug_stock.drug_name} @ {self.hospital.name}"

    def acknowledge(self, user):
        """Mark alert as acknowledged."""
        self.status = 'acknowledged'
        self.acknowledged_by = user
        self.acknowledged_at = timezone.now()
        self.save(update_fields=['status', 'acknowledged_by', 'acknowledged_at'])

    def resolve(self):
        """Mark alert as resolved."""
        self.status = 'resolved'
        self.resolved_at = timezone.now()
        self.save(update_fields=['status', 'resolved_at'])
