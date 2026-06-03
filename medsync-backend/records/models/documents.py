import uuid
from datetime import timedelta

from django.db import models
from django.db.models import F
from django.utils import timezone
from core.models import Hospital, User, Department, LabUnit, Ward
from patients.models import Patient
from django_cryptography.fields import encrypt

from .base import MedicalRecord

class NursingNote(models.Model):
    NOTE_TYPES = [
        ("observation", "Observation"),
        ("handover", "Handover"),
        ("incident", "Incident"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    content = encrypt(models.TextField())
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default="observation")
    incoming_nurse = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="incoming_handover_notes"
    )
    acknowledged_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="acknowledged_handover_notes"
    )
    outgoing_signed_at = models.DateTimeField(auto_now_add=True)
    acknowledged_at = models.DateTimeField(null=True, blank=True)


class Incident(models.Model):
    """
    Clinical incident/safety report for risk management.
    """
    SEVERITY_CHOICES = [
        ('near_miss', 'Near Miss'),
        ('minor', 'Minor - No Harm'),
        ('moderate', 'Moderate'),
        ('serious', 'Serious'),
        ('critical', 'Critical/Death'),
    ]
    
    CATEGORY_CHOICES = [
        ('medication', 'Medication Error'),
        ('fall', 'Patient Fall'),
        ('procedure', 'Procedure Related'),
        ('equipment', 'Equipment Failure'),
        ('communication', 'Communication Error'),
        ('documentation', 'Documentation Error'),
        ('infection', 'Infection Control'),
        ('security', 'Security/Safety'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('reported', 'Reported'),
        ('under_review', 'Under Review'),
        ('investigated', 'Investigated'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey('core.Hospital', on_delete=models.CASCADE)
    ward = models.ForeignKey('core.Ward', on_delete=models.SET_NULL, null=True, blank=True)
    patient = models.ForeignKey('patients.Patient', on_delete=models.SET_NULL, null=True, blank=True)
    
    reported_by = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, related_name='reported_incidents')
    assigned_to = models.ForeignKey('core.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_incidents')
    
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='reported')
    
    incident_datetime = models.DateTimeField()
    location = models.CharField(max_length=255, blank=True)
    description = models.TextField()
    immediate_actions = models.TextField(blank=True)
    
    is_anonymous = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['hospital', 'status']),
            models.Index(fields=['hospital', 'severity']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Incident {self.id} - {self.category} ({self.severity})"

class Immunisation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE, related_name="immunisation")
    vaccine_name = models.CharField(max_length=200)
    dose_number = models.IntegerField()
    lot_number = models.CharField(max_length=100, blank=True, null=True)
    expiry_date = models.DateField(blank=True, null=True)
    site = models.CharField(max_length=100, blank=True, null=True)
    route = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.vaccine_name} (Dose {self.dose_number})"


class ProcedureNote(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE, related_name="procedure_note")
    procedure_name = models.CharField(max_length=255)
    surgeon = models.ForeignKey(User, on_delete=models.PROTECT, related_name="procedure_notes_as_surgeon")
    assistant = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="procedure_notes_as_assistant")
    anaesthesia_type = models.CharField(max_length=100, blank=True, null=True)
    findings = models.TextField()
    procedure_details = models.TextField()
    complications = models.TextField(blank=True, null=True)
    post_op_instructions = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.procedure_name} by {self.surgeon}"


class ChronicDiseaseProgram(models.Model):
    PROGRAM_STATUS = [
        ("active", "Active"),
        ("completed", "Completed"),
        ("withdrawn", "Withdrawn"),
        ("deceased", "Deceased"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="chronic_programs")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    disease_name = models.CharField(max_length=200)
    enrolled_at = models.DateField(auto_now_add=True)
    enrolled_by = models.ForeignKey(User, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=PROGRAM_STATUS, default="active")
    last_review_date = models.DateField(null=True, blank=True)
    next_review_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.disease_name} - {self.patient}"


class NotifiableDisease(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE, related_name="notifiable_disease")
    disease_name = models.CharField(max_length=200)
    ghs_case_id = models.CharField(max_length=100, blank=True, null=True)
    is_confirmed = models.BooleanField(default=False)
    reported_to_ghs = models.BooleanField(default=False)
    reported_at = models.DateTimeField(null=True, blank=True)
    outcome = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"{self.disease_name} (Confirmed: {self.is_confirmed})"

class Equipment(models.Model):
    EQUIPMENT_STATUS = [
        ("available", "Available"),
        ("in_use", "In Use"),
        ("maintenance", "Maintenance"),
        ("out_of_service", "Out of Service"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(Hospital, on_delete=models.CASCADE)
    name = models.CharField(max_length=200)
    serial_number = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100)
    status = models.CharField(max_length=20, choices=EQUIPMENT_STATUS, default="available")
    current_ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    last_maintenance_at = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.name} ({self.serial_number})"

class FamilyLink(models.Model):
    RELATIONSHIPS = [
        ("parent", "Parent"),
        ("child", "Child"),
        ("sibling", "Sibling"),
        ("spouse", "Spouse"),
        ("next_of_kin", "Next of Kin"),
        ("other", "Other"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    from_patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="links_from")
    to_patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="links_to")
    relationship_type = models.CharField(max_length=20, choices=RELATIONSHIPS)
    is_emergency_contact = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.from_patient} is {self.relationship_type} of {self.to_patient}"


class CarePlan(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("active", "Active"),
        ("suspended", "Suspended"),
        ("completed", "Completed"),
        ("entered-in-error", "Entered in Error"),
        ("cancelled", "Cancelled"),
        ("unknown", "Unknown"),
    ]
    INTENT_CHOICES = [
        ("proposal", "Proposal"),
        ("plan", "Plan"),
        ("order", "Order"),
        ("option", "Option"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(
        MedicalRecord, on_delete=models.CASCADE, related_name="care_plan"
    )
    title = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    intent = models.CharField(max_length=20, choices=INTENT_CHOICES, default="plan")
    description = models.TextField(blank=True, null=True)
    period_start = models.DateTimeField(null=True, blank=True)
    period_end = models.DateTimeField(null=True, blank=True)
    goals = models.JSONField(default=list, blank=True)
    activities = models.JSONField(default=list, blank=True)


class FamilyHistory(models.Model):
    RELATIONSHIP_CHOICES = [
        ("father", "Father"),
        ("mother", "Mother"),
        ("sibling", "Sibling"),
        ("grandparent", "Grandparent"),
        ("uncle", "Uncle"),
        ("aunt", "Aunt"),
        ("other", "Other"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name="family_histories"
    )
    relationship = models.CharField(max_length=30, choices=RELATIONSHIP_CHOICES)
    relative_name = models.CharField(max_length=100, blank=True, null=True)
    condition_name = models.CharField(max_length=200)
    icd10_code = models.CharField(max_length=10, blank=True, null=True)
    onset_age = models.IntegerField(null=True, blank=True)
    is_deceased = models.BooleanField(default=False)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class SocialDeterminantsOfHealth(models.Model):
    EDUCATION_CHOICES = [
        ("none", "No formal education"),
        ("primary", "Primary Education"),
        ("secondary", "Secondary/High School"),
        ("tertiary", "Tertiary/University"),
        ("unknown", "Unknown"),
    ]
    WATER_CHOICES = [
        ("piped_indoor", "Piped water (indoor)"),
        ("piped_yard", "Piped water (yard/borehole)"),
        ("public_tap", "Public tap/standpipe"),
        ("surface_water", "Surface water (river/stream)"),
        ("tanker", "Water tanker/vendor"),
    ]
    SANITATION_CHOICES = [
        ("flush_toilet", "Flush toilet (private)"),
        ("shared_latrine", "Shared toilet/latrine"),
        ("public_toilet", "Public toilet"),
        ("open_defecation", "No facility/open defecation"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.OneToOneField(
        Patient, on_delete=models.CASCADE, related_name="sdoh"
    )
    occupation = models.CharField(max_length=150, blank=True, null=True)
    education_level = models.CharField(
        max_length=20, choices=EDUCATION_CHOICES, default="unknown"
    )
    water_access = models.CharField(
        max_length=20, choices=WATER_CHOICES, default="piped_indoor"
    )
    sanitation = models.CharField(
        max_length=20, choices=SANITATION_CHOICES, default="flush_toilet"
    )
    distance_to_facility_km = models.DecimalField(
        max_digits=5, decimal_places=1, null=True, blank=True
    )
    has_health_insurance = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class DHIMS2Report(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("submitted", "Submitted"),
        ("failed", "Failed"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospital = models.ForeignKey(
        Hospital, on_delete=models.PROTECT, related_name="dhims2_reports"
    )
    month = models.CharField(max_length=7, help_text="Format YYYY-MM")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    indicators = models.JSONField(default=dict)
    submitted_at = models.DateTimeField(null=True, blank=True)
    submitted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_dhims2_reports",
    )
    response_metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("hospital", "month")

    def __str__(self):
        return f"DHIMS2 Report - {self.hospital.name} ({self.month}) - {self.status}"
