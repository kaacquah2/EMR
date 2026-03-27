import uuid
from django.db import models
from core.models import Hospital, User, Ward, Bed
from django_cryptography.fields import encrypt


class Patient(models.Model):
    GENDERS = [
        ("male", "Male"),
        ("female", "Female"),
        ("other", "Other"),
        ("unknown", "Unknown"),
    ]
    BLOOD_GROUPS = [
        ("A+", "A+"),
        ("A-", "A-"),
        ("B+", "B+"),
        ("B-", "B-"),
        ("AB+", "AB+"),
        ("AB-", "AB-"),
        ("O+", "O+"),
        ("O-", "O-"),
        ("unknown", "Unknown"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ghana_health_id = models.CharField(max_length=30, unique=True)
    full_name = models.CharField(max_length=200)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDERS)
    phone = encrypt(models.CharField(max_length=20, blank=True, null=True))
    national_id = encrypt(models.CharField(max_length=50, blank=True, null=True))
    nhis_number = encrypt(models.CharField(max_length=50, blank=True, null=True))
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    blood_group = models.CharField(max_length=10, choices=BLOOD_GROUPS, default="unknown")
    registered_at = models.ForeignKey(Hospital, on_delete=models.PROTECT, related_name="+")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class Allergy(models.Model):
    SEVERITIES = [
        ("mild", "Mild"),
        ("moderate", "Moderate"),
        ("severe", "Severe"),
        ("life_threatening", "Life Threatening"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    allergen = encrypt(models.CharField(max_length=200))
    reaction_type = encrypt(models.CharField(max_length=200))
    severity = models.CharField(max_length=20, choices=SEVERITIES)
    is_active = models.BooleanField(default=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)
    verified_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PatientAdmission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT)
    bed = models.ForeignKey(Bed, on_delete=models.SET_NULL, null=True, blank=True, related_name="admissions")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    admitted_by = models.ForeignKey(User, on_delete=models.PROTECT)
    admitted_at = models.DateTimeField(auto_now_add=True)
    discharged_at = models.DateTimeField(null=True, blank=True)
    discharge_reason = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ClinicalAlert(models.Model):
    SEVERITY = [
        ("low", "Low"),
        ("medium", "Medium"),
        ("high", "High"),
        ("critical", "Critical"),
    ]
    STATUS = [
        ("active", "Active"),
        ("resolved", "Resolved"),
        ("dismissed", "Dismissed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    severity = models.CharField(max_length=20, choices=SEVERITY, default="medium")
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS, default="active")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    resource_type = models.CharField(max_length=50, blank=True, null=True)
    resource_id = models.UUIDField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "status", "-created_at"]),
        ]


class PotentialDuplicate(models.Model):
    """Possible duplicate patient pair for admin/HIM review and merge workflow."""
    STATUS = [
        ("pending", "Pending Review"),
        ("not_duplicate", "Not Duplicate"),
        ("approved_duplicate", "Approved Duplicate"),
        ("merged", "Merged"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    patient_a = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="duplicate_candidates_a"
    )
    patient_b = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="duplicate_candidates_b"
    )
    status = models.CharField(max_length=30, choices=STATUS, default="pending")
    reviewed_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    merged_into_patient_id = models.UUIDField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "status"]),
        ]


class Invoice(models.Model):
    """Minimal billing: service charges, payment status. Optional link to encounter."""
    STATUS = [
        ("draft", "Draft"),
        ("issued", "Issued"),
        ("paid", "Paid"),
        ("partial", "Partially Paid"),
        ("cancelled", "Cancelled"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    amount_cents = models.IntegerField(default=0)
    currency = models.CharField(max_length=3, default="GHS")
    status = models.CharField(max_length=20, choices=STATUS, default="draft")
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["hospital", "-created_at"])]


class Appointment(models.Model):
    STATUS = [
        ("scheduled", "Scheduled"),
        ("checked_in", "Checked In"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
        ("no_show", "No Show"),
    ]
    TYPE = [
        ("outpatient", "Outpatient"),
        ("follow_up", "Follow-up"),
        ("consultation", "Consultation"),
        ("procedure", "Procedure"),
        ("other", "Other"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS, default="scheduled")
    appointment_type = models.CharField(max_length=20, choices=TYPE, default="outpatient")
    provider = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    notes = models.TextField(blank=True, null=True)
    no_show_marked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Time when appointment was auto-marked as no-show (null if manual or not no-show)"
    )
    no_show_override_reason = models.TextField(
        blank=True,
        null=True,
        help_text="Reason for unmarking a no-show (if doctor overrides)"
    )
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "scheduled_at"]),
            models.Index(fields=["patient", "-scheduled_at"]),
            models.Index(fields=["status", "no_show_marked_at"]),
        ]
