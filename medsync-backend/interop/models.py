import uuid
from django.db import models
from django.utils import timezone
from core.models import Hospital, User
from patients.models import Patient


class GlobalPatient(models.Model):
    """Global patient identity (GPID) for cross-facility interoperability."""

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
    national_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    ghana_health_id = models.CharField(max_length=50, blank=True, null=True)
    nhis_number = models.CharField(max_length=50, blank=True, null=True)
    passport_number = models.CharField(max_length=50, blank=True, null=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDERS)
    blood_group = models.CharField(
        max_length=10, choices=BLOOD_GROUPS, default="unknown", blank=True
    )
    phone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    version = models.IntegerField(default=1)

    class Meta:
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["national_id"]),
        ]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()


class FacilityPatient(models.Model):
    """Links a global patient to a facility with an optional local Patient record."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="facility_patients"
    )
    global_patient = models.ForeignKey(
        GlobalPatient, on_delete=models.CASCADE, related_name="facility_profiles"
    )
    local_patient_id = models.CharField(max_length=100)
    patient = models.OneToOneField(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="facility_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    version = models.IntegerField(default=1)

    class Meta:
        unique_together = ("facility", "global_patient")
        indexes = [models.Index(fields=["facility", "global_patient"])]


class Consent(models.Model):
    """Consent for a facility to access a global patient's records."""

    SCOPE_SUMMARY = "SUMMARY"
    SCOPE_FULL_RECORD = "FULL_RECORD"
    SCOPE_CHOICES = [
        (SCOPE_SUMMARY, "Summary"),
        (SCOPE_FULL_RECORD, "Full Record"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    global_patient = models.ForeignKey(
        GlobalPatient, on_delete=models.CASCADE, related_name="consents"
    )
    granted_to_facility = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="consents_received"
    )
    granted_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    scope = models.CharField(max_length=20, choices=SCOPE_CHOICES)
    expires_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["global_patient", "granted_to_facility", "is_active"]),
        ]


class Referral(models.Model):
    """Referral of a global patient from one facility to another."""

    STATUS_PENDING = "PENDING"
    STATUS_ACCEPTED = "ACCEPTED"
    STATUS_REJECTED = "REJECTED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACCEPTED, "Accepted"),
        (STATUS_REJECTED, "Rejected"),
        (STATUS_COMPLETED, "Completed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    global_patient = models.ForeignKey(
        GlobalPatient, on_delete=models.CASCADE, related_name="referrals"
    )
    from_facility = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="referrals_sent"
    )
    to_facility = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="referrals_received"
    )
    consent = models.ForeignKey(
        Consent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="referrals",
    )
    record_ids_to_share = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional list of record UUIDs to share with receiving facility.",
    )
    reason = models.TextField()
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=["to_facility", "status"])]


class SharedRecordAccess(models.Model):
    """Audit record when a facility accesses a global patient's cross-facility records (read-only)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    global_patient = models.ForeignKey(
        GlobalPatient, on_delete=models.CASCADE, related_name="shared_access_logs"
    )
    accessing_facility = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name="+"
    )
    accessed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    scope = models.CharField(max_length=20)  # SUMMARY or FULL_RECORD
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["global_patient", "-created_at"])]


class BreakGlassLog(models.Model):
    """Audit log for emergency access to a global patient's records without consent."""
    REASON_CODES = [
        ("life_threatening_emergency", "Life-threatening emergency"),
        ("unconscious_patient", "Unconscious patient / no consent possible"),
        ("critical_time_sensitive_care", "Critical time-sensitive care"),
        ("mass_casualty_event", "Mass casualty event"),
        ("other_emergency", "Other emergency"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    global_patient = models.ForeignKey(
        GlobalPatient, on_delete=models.CASCADE, related_name="break_glass_logs"
    )
    facility = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="+")
    accessed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    reason_code = models.CharField(max_length=64, choices=REASON_CODES, default="other_emergency")
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed = models.BooleanField(default=False)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    excessive_usage = models.BooleanField(
        default=False,
        help_text="Set true when break-glass usage is flagged as potentially abusive.",
    )
    expires_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="Time when this break-glass access expires (4 hours from creation by default)"
    )

    class Meta:
        indexes = [models.Index(fields=["global_patient", "created_at"])]

    def is_expired(self):
        """Check if break-glass access window has expired."""
        if self.expires_at is None:
            return False
        from django.utils import timezone
        return timezone.now() > self.expires_at


class Encounter(models.Model):
    """Facility-owned encounter; can be linked to MedicalRecord later."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    facility_patient = models.ForeignKey(
        FacilityPatient, on_delete=models.CASCADE, related_name="encounters"
    )
    facility = models.ForeignKey(Hospital, on_delete=models.CASCADE, related_name="+")
    notes = models.TextField(blank=True)
    diagnosis = models.CharField(max_length=500, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["facility_patient", "-created_at"])]
