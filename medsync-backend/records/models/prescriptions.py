import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F
from django.utils import timezone
from core.models import Hospital, User, Department, LabUnit, Ward
from patients.models import Patient
from django_cryptography.fields import encrypt
from api.tenancy import TenantManager

from .base import MedicalRecord

class Prescription(models.Model):
    ROUTES = [
        ("oral", "Oral"),
        ("iv", "IV"),
        ("im", "IM"),
        ("topical", "Topical"),
        ("inhalation", "Inhalation"),
        ("other", "Other"),
    ]
    STATUS = [
        ("pending", "Pending"),
        ("dispensing", "Dispensing"),
        ("partially_dispensed", "Partially Dispensed"),
        ("dispensed", "Dispensed"),
        ("cancelled", "Cancelled"),
    ]
    PRIORITY_CHOICES = [
        ('routine', 'Routine'),
        ('urgent', 'Urgent'),
        ('stat', 'STAT'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, null=True, blank=True)
    drug_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration_days = models.IntegerField(null=True, blank=True)
    route = models.CharField(max_length=20, choices=ROUTES)
    notes = models.TextField(blank=True, null=True)
    dispense_status = models.CharField(max_length=20, choices=STATUS, default="pending")
    allergy_conflict = models.BooleanField(default=False)
    allergy_override_reason = models.TextField(blank=True, null=True)
    version = models.IntegerField(default=1, help_text="Version for optimistic locking")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    prescribed_quantity = models.PositiveIntegerField(default=10, help_text="Total prescribed quantity")
    
    # Pharmacy dispensing fields
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='routine', help_text='Prescription priority level')
    dispensed_at = models.DateTimeField(null=True, blank=True, help_text='Timestamp when medication was dispensed')
    dispensed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='dispensed_prescriptions',
        help_text='Pharmacy technician who dispensed medication'
    )
    dispensed_quantity = models.PositiveIntegerField(null=True, blank=True, help_text='Quantity dispensed')
    dispense_notes = models.TextField(blank=True, null=True, help_text='Pharmacy dispensing notes')
    drug_interaction_checked = models.BooleanField(default=False, help_text='Whether drug interactions were checked')
    drug_interactions = models.JSONField(null=True, blank=True, help_text='Detected drug-drug interactions')

    tenant_objects = TenantManager()

    class Meta:
        indexes = [
            models.Index(fields=['hospital', '-created_at'], name='rx_hospital_created_idx'),
            models.Index(fields=['hospital', 'status'], name='rx_hospital_status_idx'),
            models.Index(fields=['patient', '-created_at'], name='rx_patient_created_idx'),
            models.Index(fields=['hospital', 'status', 'priority', '-created_at'], name='rx_pharmacy_queue_idx'),
        ]


class MedicationAdministration(models.Model):
    """
    Records when a medication dose was actually administered to a patient.
    Tracks compliance, refusals, and notes by nursing staff.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey('Prescription', on_delete=models.CASCADE, related_name='administrations')
    patient = models.ForeignKey('patients.Patient', on_delete=models.CASCADE, related_name='medication_administrations')
    hospital = models.ForeignKey('core.Hospital', on_delete=models.CASCADE)
    administered_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='administered_medications')
    administered_at = models.DateTimeField()
    notes = models.TextField(blank=True, default='')
    was_refused = models.BooleanField(default=False, help_text="True if patient refused the medication")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'records_medication_administration'
        ordering = ['-administered_at']
        indexes = [
            models.Index(fields=['prescription', '-administered_at']),
            models.Index(fields=['patient', '-administered_at']),
            models.Index(fields=['hospital', '-administered_at']),
        ]
    
    def __str__(self):
        status = "Refused" if self.was_refused else "Administered"
        return f"{self.patient} - {self.prescription.drug_name} {status} at {self.administered_at}"

class PrescriptionFavorite(models.Model):
    """
    Doctor's frequently used prescription templates.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    doctor = models.ForeignKey('core.User', on_delete=models.CASCADE, related_name='prescription_favorites')
    
    drug_name = models.CharField(max_length=255)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    route = models.CharField(max_length=50, blank=True)
    duration_days = models.PositiveIntegerField(null=True, blank=True)
    instructions = models.TextField(blank=True)
    
    use_count = models.PositiveIntegerField(default=0)
    last_used_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-use_count', '-last_used_at']
        unique_together = ['doctor', 'drug_name', 'dosage', 'frequency']
    
    def __str__(self):
        return f"{self.drug_name} {self.dosage} - {self.doctor}"


class MedicationSchedule(models.Model):
    """
    Medication Administration Record (MAR) Schedule.
    Tracks scheduled medication doses and their administration status.
    """
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('administered', 'Administered'),
        ('missed', 'Missed'),
        ('held', 'Held'),
        ('refused', 'Refused'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    prescription = models.ForeignKey(
        'Prescription',
        on_delete=models.CASCADE,
        related_name='schedules'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.CASCADE,
        related_name='medication_schedules'
    )
    hospital = models.ForeignKey(
        'core.Hospital',
        on_delete=models.CASCADE,
        related_name='medication_schedules'
    )
    scheduled_time = models.DateTimeField(help_text='When medication should be given')
    actual_time = models.DateTimeField(null=True, blank=True, help_text='When medication was actually administered')
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='scheduled',
        help_text='Current status of the scheduled dose'
    )
    administered_by = models.ForeignKey(
        'core.User',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='administered_schedules'
    )
    hold_reason = models.TextField(null=True, blank=True, help_text='Reason for holding the medication')
    refused_reason = models.TextField(null=True, blank=True, help_text='Reason patient refused medication')
    notes = models.TextField(null=True, blank=True, help_text='Additional administration notes')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'records_medication_schedule'
        ordering = ['scheduled_time']
        indexes = [
            models.Index(fields=['hospital', 'scheduled_time', 'status'], name='mar_hospital_sched_idx'),
            models.Index(fields=['patient', 'scheduled_time'], name='mar_patient_sched_idx'),
        ]
    
    def __str__(self):
        return f"{self.patient} - {self.prescription.drug_name} @ {self.scheduled_time} ({self.status})"
