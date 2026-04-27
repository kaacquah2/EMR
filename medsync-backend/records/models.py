import uuid
from django.db import models
from django.db.models import F
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
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    record_type = models.CharField(max_length=20, choices=RECORD_TYPES)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
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
        elif self.pk:
            current = MedicalRecord.objects.only("record_version").get(pk=self.pk)
            self.record_version = current.record_version + 1
        else:
            self.record_version = 1
        super().save(*args, **kwargs)

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

    class Meta:
        indexes = [
            models.Index(fields=['hospital', '-created_at'], name='rx_hospital_created_idx'),
            models.Index(fields=['hospital', 'status'], name='rx_hospital_status_idx'),
            models.Index(fields=['patient', '-created_at'], name='rx_patient_created_idx'),
            models.Index(fields=['hospital', 'status', 'priority', '-created_at'], name='rx_pharmacy_queue_idx'),
        ]


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


class Vital(models.Model):
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
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)


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
    status = models.CharField(max_length=20, choices=STATUS, default="ordered")
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["hospital", "-created_at"]),
            models.Index(fields=["patient", "-created_at"]),
        ]


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
