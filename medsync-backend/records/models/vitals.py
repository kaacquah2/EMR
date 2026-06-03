import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F
from django.utils import timezone
from core.models import Hospital, User, Department, LabUnit, Ward
from patients.models import Patient
from django_cryptography.fields import encrypt

from .base import MedicalRecord

class Vital(models.Model):
    AVPU_CHOICES = [
        ("A", "Alert"),
        ("V", "Voice"),
        ("P", "Pain"),
        ("U", "Unresponsive"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    temperature_c = encrypt(models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True))
    pulse_bpm = encrypt(models.IntegerField(null=True, blank=True))
    resp_rate = encrypt(models.IntegerField(null=True, blank=True))
    bp_systolic = encrypt(models.IntegerField(null=True, blank=True))
    bp_diastolic = encrypt(models.IntegerField(null=True, blank=True))
    spo2_percent = encrypt(models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True))
    weight_kg = encrypt(models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True))
    height_cm = encrypt(models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True))
    bmi = encrypt(models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True))
    gcs_score = encrypt(
        models.IntegerField(
            null=True, blank=True, help_text="Glasgow Coma Scale total (3-15)"
        )
    )
    avpu_score = encrypt(
        models.CharField(
            max_length=2,
            choices=AVPU_CHOICES,
            null=True,
            blank=True,
            help_text="AVPU scale score",
        )
    )
    pain_score = encrypt(
        models.IntegerField(
            null=True, blank=True, help_text="Pain score 0-10 (NRS)"
        )
    )
    news2_score = encrypt(
        models.IntegerField(
            null=True, blank=True, help_text="National Early Warning Score 2 (0-20)"
        )
    )
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)

    def compute_news2_score(self, on_supplemental_o2: bool = False) -> int:
        from api.vitals_utils import calculate_news2

        consciousness = self.avpu_score or "A"
        score, _ = calculate_news2(
            self.resp_rate,
            self.spo2_percent,
            on_supplemental_o2,
            self.bp_systolic,
            self.pulse_bpm,
            consciousness,
            self.temperature_c,
        )
        return score

    def save(self, *args, **kwargs):
        if self.news2_score is None:
            self.news2_score = self.compute_news2_score()
        super().save(*args, **kwargs)
