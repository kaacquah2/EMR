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

class LabTestType(models.Model):
    """Maps test name/type to lab unit for routing (e.g. Full Blood Count -> Hematology)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lab_unit = models.ForeignKey(LabUnit, on_delete=models.CASCADE)
    test_name = models.CharField(max_length=200)
    specimen = models.CharField(max_length=80, blank=True, default="")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("lab_unit", "test_name")


class LabOrder(models.Model):
    URGENCIES = [
        ("routine", "Routine"),
        ("urgent", "Urgent"),
        ("stat", "STAT"),
    ]
    ORDER_STATUS = [
        ("ordered", "Ordered"),
        ("collected", "Specimen Collected"),
        ("in_progress", "In Progress"),
        ("resulted", "Resulted"),
        ("verified", "Verified"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, null=True, blank=True)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT, null=True, blank=True)
    test_name = models.CharField(max_length=200)
    urgency = models.CharField(max_length=20, choices=URGENCIES, default="routine")
    notes = models.TextField(blank=True, null=True)
    lab_unit = models.ForeignKey(
        LabUnit, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=ORDER_STATUS, default="ordered")
    assigned_to = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="lab_orders"
    )
    ordering_doctor = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="ordered_lab_tests"
    )
    collection_time = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    resulted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1, help_text="Version for optimistic locking")
    created_at = models.DateTimeField(auto_now_add=True)

    tenant_objects = TenantManager()

    class Meta:
        indexes = [
            models.Index(fields=['hospital', '-created_at'], name='lab_hospital_created_idx'),
            models.Index(fields=['hospital', 'status'], name='lab_hospital_status_idx'),
            models.Index(fields=['lab_unit', 'urgency', '-created_at'], name='lab_unit_urgency_idx'),
            models.Index(fields=['ordering_doctor', 'status'], name='lab_doctor_status_idx'),
        ]


class LabResult(models.Model):
    STATUS = [
        ("pending", "Pending"),
        ("resulted", "Resulted"),
        ("verified", "Verified"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    lab_order = models.OneToOneField(LabOrder, on_delete=models.CASCADE, null=True, blank=True)
    test_name = models.CharField(max_length=200)
    result_value = encrypt(models.TextField(blank=True, null=True))
    reference_range = models.CharField(max_length=100, blank=True, null=True)
    result_date = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS, default="pending")
    lab_tech = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    attachment_url = models.URLField(max_length=500, blank=True, null=True)
    verified_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
