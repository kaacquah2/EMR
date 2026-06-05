import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F
from django.utils import timezone
from core.models import Hospital, User, Department, LabUnit, Ward
from patients.models import Patient
from django_cryptography.fields import encrypt

class MedicalRecord(models.Model):
    RECORD_TYPES = [
        ("diagnosis", "Diagnosis"),
        ("prescription", "Prescription"),
        ("lab_result", "Lab Result"),
        ("vital_signs", "Vital Signs"),
        ("nursing_note", "Nursing Note"),
        ("allergy", "Allergy"),
        ("immunisation", "Immunisation"),
        ("procedure_note", "Procedure Note"),
        ("notifiable_disease", "Notifiable Disease"),
        ("care_plan", "Care Plan"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    retention_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Ghana MoH minimum retention end date (10y adult / 25y paediatric).",
    )
    record_version = models.IntegerField(default=0)
    is_amended = models.BooleanField(default=False)
    amended_record = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.SET_NULL, related_name="amendments"
    )
    amendment_reason = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["patient", "record_type", "-created_at"]),
        ]

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.record_version = 1
            if self.retention_until is None and self.patient_id:
                self.retention_until = self.compute_retention_until(self.patient)
        elif self.pk:
            current = MedicalRecord.objects.only("record_version").get(pk=self.pk)
            self.record_version = current.record_version + 1
        else:
            self.record_version = 1
        super().save(*args, **kwargs)

    @staticmethod
    def compute_retention_until(patient) -> timezone.datetime:
        """MoH retention: 25 years from majority for paediatric, else 10 years from creation."""
        from datetime import date, datetime

        now = timezone.now()
        dob = getattr(patient, "date_of_birth", None)
        if isinstance(dob, str):
            try:
                dob = date.fromisoformat(dob[:10])
            except ValueError:
                dob = None
        elif isinstance(dob, datetime):
            dob = dob.date()

        if not dob:
            return now + timedelta(days=10 * 365)

        today = date.today()
        age_years = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )
        if age_years < 18:
            years_until_majority = 18 - age_years
            return now + timedelta(days=(25 + years_until_majority) * 365)
        return now + timedelta(days=10 * 365)

    def assert_deletable(self):
        """Raise ValidationError if legal retention period is still active."""
        from django.core.exceptions import ValidationError

        if self.retention_until and timezone.now() < self.retention_until:
            raise ValidationError(
                "Record cannot be deleted — legal retention period is still active."
            )

    @staticmethod
    def update_if_version(record_id, expected_version, **fields):
        """Optimistic lock: update only if record_version matches. Returns True if updated."""
        n = MedicalRecord.objects.filter(
            pk=record_id, record_version=expected_version
        ).update(record_version=F("record_version") + 1, **fields)
        return n > 0


class Diagnosis(models.Model):
    SEVERITIES = [
        ("mild", "Mild"),
        ("moderate", "Moderate"),
        ("severe", "Severe"),
        ("critical", "Critical"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    icd10_code = models.CharField(max_length=10)
    icd10_description = encrypt(models.CharField(max_length=300))
    severity = models.CharField(max_length=20, choices=SEVERITIES)
    onset_date = models.DateField(null=True, blank=True)
    notes = encrypt(models.TextField(blank=True, null=True))
    is_chronic = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["icd10_code"]),
        ]

