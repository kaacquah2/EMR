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
    is_archived = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["full_name"]),
            models.Index(fields=["is_archived", "registered_at"]),
        ]


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

    class Meta:
        indexes = [
            models.Index(fields=['ward', 'discharged_at'], name='adm_ward_discharged_idx'),
            models.Index(fields=['hospital', '-admitted_at'], name='adm_hospital_admitted_idx'),
        ]


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
    updated_at = models.DateTimeField(auto_now=True)
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
        indexes = [
            models.Index(fields=["hospital", "-created_at"]),
            models.Index(fields=["patient", "-created_at"]),
        ]


class InvoiceItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="items")
    description = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    unit_price = models.IntegerField(default=0)  # in cents
    service_type = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)


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
        ("walk_in", "Walk-in"),
        ("other", "Other"),
    ]
    URGENCY_CHOICES = [
        ("routine", "Routine"),
        ("urgent", "Urgent"),
        ("emergency", "Emergency"),
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
    # PHASE 7.4: Walk-in queue fields
    queue_position = models.PositiveIntegerField(null=True, blank=True, help_text="Queue position for walk-in appointments")
    urgency = models.CharField(max_length=20, choices=URGENCY_CHOICES, default="routine", help_text="Urgency level of appointment")
    reason = models.TextField(blank=True, null=True, help_text="Reason for visit")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Emergency Department Triage fields
    TRIAGE_COLOR_CHOICES = [
        ('red', 'RED - Immediate (<5min)'),
        ('yellow', 'YELLOW - Urgent (<30min)'),
        ('green', 'GREEN - Less Urgent (<2hr)'),
        ('blue', 'BLUE - Non-Urgent (routine)'),
    ]
    triage_color = models.CharField(
        max_length=10, 
        choices=TRIAGE_COLOR_CHOICES, 
        null=True, 
        blank=True,
        help_text="Emergency triage color code (red=immediate, yellow=urgent, green=less urgent, blue=non-urgent)"
    )
    triage_assessed_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when triage assessment was completed")
    triaged_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='triage_assessments',
        help_text="User (doctor/nurse) who performed triage assessment"
    )
    chief_complaint = models.TextField(blank=True, null=True, help_text="Primary reason for emergency visit")
    triage_vitals = models.JSONField(
        null=True, 
        blank=True,
        help_text="Vital signs captured during triage (BP, HR, RR, SpO2, temp, pain_scale)"
    )
    ed_arrival_time = models.DateTimeField(null=True, blank=True, help_text="Time patient arrived to Emergency Department")
    ed_room_assignment = models.CharField(max_length=50, blank=True, null=True, help_text="Assigned ED room/bed (e.g., 'ED-1', 'Trauma Bay 2')")

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "scheduled_at"]),
            models.Index(fields=["patient", "-scheduled_at"]),
            models.Index(fields=["status", "no_show_marked_at"]),
        ]
