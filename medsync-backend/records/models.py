import uuid
from django.db import models
from django.db.models import F
from core.models import Hospital, User, Department, LabUnit
from patients.models import Patient


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
    icd10_description = models.CharField(max_length=300)
    severity = models.CharField(max_length=20, choices=SEVERITIES)
    onset_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    is_chronic = models.BooleanField(default=False)


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
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    drug_name = models.CharField(max_length=200)
    dosage = models.CharField(max_length=100)
    frequency = models.CharField(max_length=100)
    duration_days = models.IntegerField(null=True, blank=True)
    route = models.CharField(max_length=20, choices=ROUTES)
    notes = models.TextField(blank=True, null=True)
    dispense_status = models.CharField(max_length=20, choices=STATUS, default="pending")
    allergy_conflict = models.BooleanField(default=False)
    allergy_override_reason = models.TextField(blank=True, null=True)


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
    collection_time = models.DateTimeField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    resulted_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)


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
    result_value = models.TextField(blank=True, null=True)
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
    temperature_c = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    pulse_bpm = models.IntegerField(null=True, blank=True)
    resp_rate = models.IntegerField(null=True, blank=True)
    bp_systolic = models.IntegerField(null=True, blank=True)
    bp_diastolic = models.IntegerField(null=True, blank=True)
    spo2_percent = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    weight_kg = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    height_cm = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    bmi = models.DecimalField(max_digits=4, decimal_places=1, null=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)


class NursingNote(models.Model):
    NOTE_TYPES = [
        ("observation", "Observation"),
        ("handover", "Handover"),
        ("incident", "Incident"),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.OneToOneField(MedicalRecord, on_delete=models.CASCADE)
    content = models.TextField()
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
    notes = models.TextField(blank=True, null=True)
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
    chief_complaint = models.TextField(blank=True, null=True)
    hpi = models.TextField(blank=True, null=True, verbose_name="History of presenting illness")
    examination_findings = models.TextField(blank=True, null=True)
    assessment_plan = models.TextField(blank=True, null=True)
    discharge_summary = models.TextField(blank=True, null=True)

    class Meta:
        indexes = [
            models.Index(fields=["patient", "-encounter_date"]),
            models.Index(fields=["hospital", "-encounter_date"]),
            models.Index(fields=["assigned_department", "status"]),
            models.Index(fields=["assigned_doctor", "status"]),
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
        indexes = [models.Index(fields=["hospital", "-created_at"])]


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
    """Captures handover notes and critical alerts at end of shift."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    shift = models.ForeignKey(NurseShift, on_delete=models.CASCADE, related_name="handovers")
    nurse = models.ForeignKey(User, on_delete=models.CASCADE, related_name="handovers")
    hospital = models.ForeignKey(Hospital, on_delete=models.PROTECT)
    handover_notes = models.TextField()
    critical_patients = models.ManyToManyField(Patient, blank=True, related_name="critical_alerts")
    submitted_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=["shift", "-submitted_at"]),
            models.Index(fields=["hospital", "-submitted_at"]),
        ]
