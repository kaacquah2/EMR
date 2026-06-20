import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F
from django.utils import timezone
from core.models import Hospital, User, Department, LabUnit, Ward
from patients.models import Patient
from django_cryptography.fields import encrypt

from .base import MedicalRecord

class Encounter(models.Model):
    ENCOUNTER_TYPES = [
        ("outpatient", "Outpatient"),
        ("inpatient", "Inpatient"),
        ("emergency", "Emergency"),
        ("follow_up", "Follow-up"),
        ("consultation", "Consultation"),
        ("other", "Other"),
    ]
    ENCOUNTER_STATUS = [
        ("waiting", "Waiting"),
        ("in_consultation", "In Consultation"),
        ("completed", "Completed"),
    ]
    VISIT_STATUS = [
        ("registered", "Registered"),
        ("waiting_triage", "Waiting for Triage"),
        ("waiting_doctor", "Waiting for Doctor"),
        ("in_consultation", "In Consultation"),
        ("sent_to_lab", "Sent to Lab"),
        ("admitted", "Admitted"),
        ("discharged", "Discharged"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    encounter_type = models.CharField(max_length=20, choices=ENCOUNTER_TYPES, default="outpatient")
    encounter_date = models.DateTimeField(auto_now_add=True)
    notes = encrypt(models.TextField(blank=True, null=True))
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    assigned_department = models.ForeignKey(
        Department, null=True, blank=True, on_delete=models.SET_NULL, related_name="encounters"
    )
    assigned_doctor = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_encounters",
    )
    status = models.CharField(max_length=20, choices=ENCOUNTER_STATUS, default="waiting")
    visit_status = models.CharField(
        max_length=30, choices=VISIT_STATUS, default="registered", blank=True
    )
    chief_complaint = encrypt(models.TextField(blank=True, null=True))
    hpi = encrypt(models.TextField(blank=True, null=True, verbose_name="History of presenting illness"))
    examination_findings = encrypt(models.TextField(blank=True, null=True))
    assessment_plan = encrypt(models.TextField(blank=True, null=True))
    discharge_summary = encrypt(models.TextField(blank=True, null=True))
    version = models.IntegerField(default=1, help_text="Version for optimistic locking")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'encounter'
        ordering = ['-encounter_date']
        indexes = [
            # Hot query patterns with explicit names
            models.Index(fields=['hospital', '-encounter_date'], name='enc_hospital_created_idx'),
            models.Index(fields=['hospital', 'status'], name='enc_hospital_status_idx'),
            models.Index(fields=['patient', '-encounter_date'], name='enc_patient_date_idx'),
            models.Index(fields=['assigned_doctor', 'status'], name='enc_doctor_status_idx'),
        ]


class RadiologyOrder(models.Model):
    """Radiology/imaging order placeholder: study type and optional attachment URL."""
    STATUS = [
        ("ordered", "Ordered"),
        ("in_progress", "In Progress"),
        ("completed", "Completed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    encounter = models.ForeignKey(
        Encounter, null=True, blank=True, on_delete=models.SET_NULL, related_name="radiology_orders"
    )
    study_type = models.CharField(max_length=200)
    attachment_url = models.URLField(max_length=500, blank=True, null=True)
    findings = models.TextField(
        blank=True,
        default="",
        help_text="Radiologist narrative findings / report text.",
    )
    status = models.CharField(max_length=20, choices=STATUS, default="ordered")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    reported_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="radiology_reports",
        help_text="Technician who finalized the report.",
    )
    reported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "-created_at"]),
            models.Index(fields=["patient", "-created_at"]),
        ]


class EncounterDraft(models.Model):
    """
    Temporary SOAP draft state for in-progress encounters.
    Auto-saved every 30s, deleted when encounter is finalized.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    encounter = models.OneToOneField(
        Encounter,
        on_delete=models.CASCADE,
        related_name='draft',
        null=True,
        blank=True
    )
    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name='encounter_drafts'
    )
    hospital = models.ForeignKey(
        Hospital,
        on_delete=models.CASCADE
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='draft_encounters'
    )
    
    # SOAP content as JSON blob for flexibility
    # {
    #   "subjective": "Patient reports...",
    #   "objective": "Vitals: BP...",
    #   "assessment": "Diagnosis...",
    #   "plan": "Treatment...",
    #   "diagnoses": [...],
    #   "prescriptions": [...],
    #   "lab_orders": [...]
    # }
    draft_data = models.JSONField(default=dict)
    
    last_saved_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'records_encounter_draft'
        indexes = [
            models.Index(fields=['patient', 'hospital']),
            models.Index(fields=['created_by', 'last_saved_at']),
        ]
    
    def __str__(self):
        return f"Draft for {self.patient} by {self.created_by}"


class EncounterTemplate(models.Model):
    """
    Reusable templates for encounter SOAP notes.
    Can be personal (owned by doctor) or shared (hospital-wide).
    """
    TEMPLATE_TYPES = [
        ('personal', 'Personal'),
        ('shared', 'Shared'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    template_type = models.CharField(max_length=20, choices=TEMPLATE_TYPES, default='personal')
    
    # Template owner (doctor for personal, null for shared)
    created_by = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='encounter_templates'
    )
    hospital = models.ForeignKey(
        Hospital, on_delete=models.CASCADE, related_name='encounter_templates'
    )
    
    # SOAP template content
    chief_complaint_template = models.TextField(blank=True)
    hpi_template = models.TextField(blank=True)
    examination_template = models.TextField(blank=True)
    assessment_template = models.TextField(blank=True)
    
    # Optional: common diagnoses/prescriptions to pre-fill
    default_diagnoses = models.JSONField(default=list, blank=True)
    default_prescriptions = models.JSONField(default=list, blank=True)
    
    # Metadata
    specialty = models.CharField(max_length=100, blank=True, help_text="Medical specialty this template is for")
    encounter_type = models.CharField(max_length=50, blank=True, help_text="Type of encounter (outpatient, emergency, etc)")
    usage_count = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'encounter_template'
        ordering = ['-usage_count', 'name']
        indexes = [
            models.Index(fields=['hospital', 'template_type', 'is_active']),
            models.Index(fields=['created_by', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.template_type})"

class ImagingStudy(models.Model):
    STATUS_CHOICES = [
        ("registered", "Registered"),
        ("available", "Available"),
        ("cancelled", "Cancelled"),
        ("entered-in-error", "Entered in Error"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="imaging_studies"
    )
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, related_name="imaging_studies"
    )
    radiology_order = models.ForeignKey(
        RadiologyOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imaging_studies",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="available")
    started = models.DateTimeField(null=True, blank=True)
    modality = models.CharField(max_length=50, help_text="e.g., CT, MR, US, DX")
    description = models.CharField(max_length=255, blank=True, null=True)
    number_of_series = models.PositiveIntegerField(default=1)
    number_of_instances = models.PositiveIntegerField(default=1)
    series = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class NurseShift(models.Model):
    """Tracks nurse shift start/end times and ward assignments."""
    STATUS = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("on_break", "On Break"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nurse = models.ForeignKey(User, on_delete=models.CASCADE, related_name="shifts")
    ward = models.ForeignKey("core.Ward", on_delete=models.SET_NULL, null=True, blank=True, related_name="shifts")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    shift_start = models.DateTimeField()
    shift_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="active")
    break_start = models.DateTimeField(null=True, blank=True)
    break_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["nurse", "-shift_start"]),
            models.Index(fields=["ward", "status"]),
        ]


class ShiftHandover(models.Model):
    """
    Captures handover notes with SBAR structure and dual signatures.
    
    Workflow:
    1. Outgoing nurse submits handover with SBAR details and assigns incoming nurse
    2. System sets outgoing_signed_at/submitted_at (auto, when created)
    3. Incoming nurse reviews and acknowledges
    4. System records incoming_acknowledged_at and incoming_nurse confirmation
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(NurseShift, on_delete=models.CASCADE, related_name="handovers")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    
    # Outgoing Nurse (Submitter)
    nurse = models.ForeignKey(User, on_delete=models.CASCADE, related_name="handovers_submitted")
    submitted_at = models.DateTimeField(auto_now_add=True)  # Keep for backward compatibility
    outgoing_signed_at = models.DateTimeField(auto_now_add=True, null=True, help_text="Outgoing nurse submission timestamp")
    
    # Incoming Nurse (Receiver/Acknowledger)
    incoming_nurse = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL,
        related_name="handovers_received",
        help_text="Incoming nurse assigned to receive this handover"
    )
    incoming_acknowledged_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Incoming nurse acknowledgement timestamp (second signature)"
    )
    
    # SBAR Structure (Situation, Background, Assessment, Recommendation)
    sbar_situation = models.TextField(
        blank=True, default='',
        help_text="Current patient status, vitals, recent changes"
    )
    sbar_background = models.TextField(
        blank=True, default='',
        help_text="Patient history, admission reason, relevant context"
    )
    sbar_assessment = models.TextField(
        blank=True, default='',
        help_text="Current clinical assessment and concerns"
    )
    sbar_recommendation = models.TextField(
        blank=True, default='',
        help_text="Recommended actions for incoming nurse"
    )
    
    # Legacy field
    handover_notes = models.TextField(blank=True, default='')
    
    # Critical Patients (many-to-many)
    critical_patients = models.ManyToManyField(Patient, blank=True, related_name="critical_handover_alerts")
    
    class Meta:
        indexes = [
            models.Index(fields=["shift", "-submitted_at"]),
            models.Index(fields=["hospital", "-submitted_at"]),
            models.Index(fields=["incoming_nurse", "incoming_acknowledged_at"]),
        ]
        ordering = ["-submitted_at"]
    
    @property
    def is_acknowledged(self) -> bool:
        """Returns True if incoming nurse has acknowledged."""
        return self.incoming_acknowledged_at is not None
    
    @property
    def status(self) -> str:
        """Returns handover status: pending or acknowledged."""
        return "acknowledged" if self.is_acknowledged else "pending"
