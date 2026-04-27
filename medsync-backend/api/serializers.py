from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from rest_framework import serializers
from core.models import User, Ward, TaskSubmission
from patients.models import Patient, Allergy, Invoice, InvoiceItem
from interop.models import (
    GlobalPatient,
    FacilityPatient,
    Consent,
    Referral,
    BreakGlassLog,
)
from records.models import (
    MedicalRecord,
    Diagnosis,
    Prescription,
    LabOrder,
    LabResult,
    Vital,
    EncounterDraft,
    ShiftHandover,
)


class PatientSerializer(serializers.ModelSerializer):
    allergies = serializers.SerializerMethodField()
    registered_at = serializers.SerializerMethodField()
    global_patient_id = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "patient_id",
            "ghana_health_id",
            "full_name",
            "date_of_birth",
            "gender",
            "blood_group",
            "phone",
            "national_id",
            "nhis_number",
            "passport_number",
            "registered_at",
            "allergies",
            "global_patient_id",
        ]

    def get_patient_id(self, obj):
        return str(obj.id)

    def get_registered_at(self, obj):
        return str(obj.registered_at_id) if obj.registered_at_id else None

    def get_global_patient_id(self, obj):
        try:
            fp = obj.facility_profile
            return str(fp.global_patient_id) if fp else None
        except ObjectDoesNotExist:
            return None

    def get_allergies(self, obj):
        return AllergySerializer(
            obj.allergy_set.filter(is_active=True), many=True
        ).data


class PatientDemographicsOnlySerializer(serializers.ModelSerializer):
    """Receptionist scope: demographics only. No clinical data."""
    patient_id = serializers.SerializerMethodField()
    registered_at = serializers.SerializerMethodField()

    class Meta:
        model = Patient
        fields = [
            "patient_id",
            "ghana_health_id",
            "full_name",
            "date_of_birth",
            "gender",
            "nhis_number",
            "phone",
            "registered_at",
        ]

    def get_patient_id(self, obj):
        return str(obj.id)

    def get_registered_at(self, obj):
        return str(obj.registered_at_id) if obj.registered_at_id else None


class AllergySerializer(serializers.ModelSerializer):
    allergy_id = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(format="%Y-%m-%dT%H:%M:%S.%fZ")  # type: ignore[reportArgumentType]

    class Meta:
        model = Allergy
        fields = [
            "allergy_id",
            "allergen",
            "reaction_type",
            "severity",
            "is_active",
            "created_at",
        ]

    def get_allergy_id(self, obj):
        return str(obj.id)


class DiagnosisSerializer(serializers.ModelSerializer):
    record_id = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    hospital_name = serializers.SerializerMethodField()

    class Meta:
        model = Diagnosis
        fields = [
            "diagnosis_id",
            "record_id",
            "icd10_code",
            "icd10_description",
            "severity",
            "onset_date",
            "notes",
            "is_chronic",
            "created_at",
            "created_by_name",
            "hospital_name",
        ]

    def get_diagnosis_id(self, obj):
        return str(obj.id)

    def get_record_id(self, obj):
        return str(obj.record_id)

    def get_created_at(self, obj):
        return obj.record.created_at.isoformat()

    def get_created_by_name(self, obj):
        return obj.record.created_by.full_name if obj.record.created_by else None

    def get_hospital_name(self, obj):
        return obj.record.hospital.name if obj.record.hospital else None


class PrescriptionSerializer(serializers.ModelSerializer):
    record_id = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Prescription
        fields = [
            "prescription_id",
            "record_id",
            "drug_name",
            "dosage",
            "frequency",
            "duration_days",
            "route",
            "dispense_status",
            "allergy_conflict",
            "created_at",
        ]

    def get_prescription_id(self, obj):
        return str(obj.id)

    def get_record_id(self, obj):
        return str(obj.record_id)

    def get_created_at(self, obj):
        return obj.record.created_at.isoformat()


class LabResultSerializer(serializers.ModelSerializer):
    record_id = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = LabResult
        fields = [
            "lab_result_id",
            "record_id",
            "test_name",
            "result_value",
            "reference_range",
            "result_date",
            "status",
            "created_at",
        ]

    def get_lab_result_id(self, obj):
        return str(obj.id)

    def get_record_id(self, obj):
        return str(obj.record_id)

    def get_created_at(self, obj):
        return obj.record.created_at.isoformat()


class VitalSerializer(serializers.ModelSerializer):
    record_id = serializers.SerializerMethodField()
    created_at = serializers.SerializerMethodField()

    class Meta:
        model = Vital
        fields = [
            "vital_id",
            "record_id",
            "temperature_c",
            "pulse_bpm",
            "resp_rate",
            "bp_systolic",
            "bp_diastolic",
            "spo2_percent",
            "weight_kg",
            "height_cm",
            "bmi",
            "created_at",
        ]

    def get_vital_id(self, obj):
        return str(obj.id)

    def get_record_id(self, obj):
        return str(obj.record_id)

    def get_created_at(self, obj):
        return obj.record.created_at.isoformat()


class MedicalRecordSerializer(serializers.ModelSerializer):
    diagnosis = serializers.SerializerMethodField()
    prescription = serializers.SerializerMethodField()
    lab_result = serializers.SerializerMethodField()
    vital = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField(read_only=True)
    record_version = serializers.IntegerField(read_only=True)

    class Meta:
        model = MedicalRecord
        fields = [
            "record_id",
            "patient_id",
            "hospital_id",
            "record_type",
            "created_by",
            "created_at",
            "record_version",
            "is_amended",
            "amended_record_id",
            "amendment_reason",
            "diagnosis",
            "prescription",
            "lab_result",
            "vital",
        ]

    def get_record_id(self, obj):
        return str(obj.id)

    def get_patient_id(self, obj):
        return str(obj.patient_id)

    def get_hospital_id(self, obj):
        return str(obj.hospital_id)

    def get_amended_record_id(self, obj):
        return str(obj.amended_record_id) if obj.amended_record_id else None

    def get_diagnosis(self, obj):
        if obj.record_type == "diagnosis" and hasattr(obj, "diagnosis"):
            return DiagnosisSerializer(obj.diagnosis).data
        return None

    def get_prescription(self, obj):
        if obj.record_type == "prescription" and hasattr(obj, "prescription"):
            return PrescriptionSerializer(obj.prescription).data
        return None

    def get_lab_result(self, obj):
        if obj.record_type == "lab_result" and hasattr(obj, "labresult"):
            return LabResultSerializer(obj.labresult).data
        return None

    def get_vital(self, obj):
        if obj.record_type == "vital_signs" and hasattr(obj, "vital"):
            return VitalSerializer(obj.vital).data
        return None


class GlobalPatientSerializer(serializers.ModelSerializer):
    global_patient_id = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = GlobalPatient
        fields = [
            "global_patient_id",
            "national_id",
            "first_name",
            "last_name",
            "full_name",
            "date_of_birth",
            "gender",
            "blood_group",
            "phone",
            "email",
            "created_at",
            "updated_at",
            "version",
        ]

    def get_global_patient_id(self, obj):
        return str(obj.id)

    def get_full_name(self, obj):
        return obj.full_name


class FacilityPatientSerializer(serializers.ModelSerializer):
    facility_patient_id = serializers.SerializerMethodField()
    facility_id = serializers.SerializerMethodField()
    facility_name = serializers.SerializerMethodField()
    global_patient_id = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()

    class Meta:
        model = FacilityPatient
        fields = [
            "facility_patient_id",
            "facility_id",
            "facility_name",
            "global_patient_id",
            "local_patient_id",
            "patient_id",
            "created_at",
        ]

    def get_facility_patient_id(self, obj):
        return str(obj.id)

    def get_facility_id(self, obj):
        return str(obj.facility_id)

    def get_facility_name(self, obj):
        return obj.facility.name if obj.facility else None

    def get_global_patient_id(self, obj):
        return str(obj.global_patient_id)

    def get_patient_id(self, obj):
        return str(obj.patient_id) if obj.patient_id else None


class ConsentSerializer(serializers.ModelSerializer):
    consent_id = serializers.SerializerMethodField()
    global_patient_id = serializers.SerializerMethodField()
    granted_to_facility_id = serializers.SerializerMethodField()
    granted_to_facility_name = serializers.SerializerMethodField()
    granted_by_user_id = serializers.SerializerMethodField()

    class Meta:
        model = Consent
        fields = [
            "consent_id",
            "global_patient_id",
            "granted_to_facility_id",
            "granted_to_facility_name",
            "granted_by_user_id",
            "scope",
            "expires_at",
            "is_active",
            "created_at",
        ]

    def get_consent_id(self, obj):
        return str(obj.id)

    def get_global_patient_id(self, obj):
        return str(obj.global_patient_id)

    def get_granted_to_facility_id(self, obj):
        return str(obj.granted_to_facility_id)

    def get_granted_to_facility_name(self, obj):
        return obj.granted_to_facility.name if obj.granted_to_facility else None

    def get_granted_by_user_id(self, obj):
        return str(obj.granted_by_id)


class ReferralSerializer(serializers.ModelSerializer):
    referral_id = serializers.SerializerMethodField()
    global_patient_id = serializers.SerializerMethodField()
    from_facility_id = serializers.SerializerMethodField()
    from_facility_name = serializers.SerializerMethodField()
    to_facility_id = serializers.SerializerMethodField()
    to_facility_name = serializers.SerializerMethodField()
    consent_id = serializers.SerializerMethodField()

    class Meta:
        model = Referral
        fields = [
            "referral_id",
            "global_patient_id",
            "from_facility_id",
            "from_facility_name",
            "to_facility_id",
            "to_facility_name",
            "consent_id",
            "record_ids_to_share",
            "reason",
            "status",
            "created_at",
            "updated_at",
        ]

    def get_consent_id(self, obj):
        return str(obj.consent_id) if obj.consent_id else None

    def get_referral_id(self, obj):
        return str(obj.id)

    def get_global_patient_id(self, obj):
        return str(obj.global_patient_id)

    def get_from_facility_id(self, obj):
        return str(obj.from_facility_id)

    def get_from_facility_name(self, obj):
        return obj.from_facility.name if obj.from_facility else None

    def get_to_facility_id(self, obj):
        return str(obj.to_facility_id)

    def get_to_facility_name(self, obj):
        return obj.to_facility.name if obj.to_facility else None


class BreakGlassLogSerializer(serializers.ModelSerializer):
    break_glass_id = serializers.SerializerMethodField()
    global_patient_id = serializers.SerializerMethodField()
    facility_id = serializers.SerializerMethodField()
    accessed_by_user_id = serializers.SerializerMethodField()

    class Meta:
        model = BreakGlassLog
        fields = [
            "break_glass_id",
            "global_patient_id",
            "facility_id",
            "accessed_by_user_id",
            "reason_code",
            "reason",
            "expires_at",
            "created_at",
        ]

    def get_break_glass_id(self, obj):
        return str(obj.id)

    def get_global_patient_id(self, obj):
        return str(obj.global_patient_id)

    def get_facility_id(self, obj):
        return str(obj.facility_id)

    def get_accessed_by_user_id(self, obj):
        return str(obj.accessed_by_id)


class WardSerializer(serializers.ModelSerializer):
    ward_id = serializers.SerializerMethodField()

    class Meta:
        model = Ward
        fields = ["ward_id", "ward_name", "ward_type"]

    def get_ward_id(self, obj):
        return str(obj.id)


class UserSerializer(serializers.ModelSerializer):
    user_id = serializers.SerializerMethodField()
    hospital_id = serializers.SerializerMethodField()
    ward_id = serializers.SerializerMethodField()
    department_id = serializers.SerializerMethodField()
    lab_unit_id = serializers.SerializerMethodField()
    hospital_name = serializers.SerializerMethodField()
    ward_name = serializers.SerializerMethodField()
    department_name = serializers.SerializerMethodField()
    lab_unit_name = serializers.SerializerMethodField()
    mfa_enabled = serializers.SerializerMethodField()
    last_login = serializers.DateTimeField(read_only=True, allow_null=True)
    created_at = serializers.DateTimeField(read_only=True)
    invitation_expires_at = serializers.DateTimeField(read_only=True, allow_null=True)
    last_role_reviewed_at = serializers.DateTimeField(read_only=True, allow_null=True)

    class Meta:
        model = User
        fields = [
            "user_id",
            "hospital_id",
            "email",
            "role",
            "full_name",
            "department",
            "department_id",
            "department_name",
            "ward_id",
            "ward_name",
            "lab_unit_id",
            "lab_unit_name",
            "account_status",
            "gmdc_licence_number",
            "licence_verified",
            "hospital_name",
            "last_login",
            "created_at",
            "mfa_enabled",
            "invitation_expires_at",
            "last_role_reviewed_at",
        ]

    def get_user_id(self, obj):
        return str(obj.id)

    def get_hospital_id(self, obj):
        return str(obj.hospital_id) if obj.hospital_id else None

    def get_ward_id(self, obj):
        return str(obj.ward_id) if obj.ward_id else None

    def get_department_id(self, obj):
        return str(obj.department_link_id) if obj.department_link_id else None

    def get_lab_unit_id(self, obj):
        return str(obj.lab_unit_id) if obj.lab_unit_id else None

    def get_hospital_name(self, obj):
        return obj.hospital.name if obj.hospital else None

    def get_ward_name(self, obj):
        return obj.ward.ward_name if obj.ward else None

    def get_department_name(self, obj):
        return obj.department_link.name if obj.department_link else None

    def get_lab_unit_name(self, obj):
        return obj.lab_unit.name if obj.lab_unit else None

    def get_mfa_enabled(self, obj):
        return bool(obj.is_mfa_enabled)


class EncounterDraftSerializer(serializers.ModelSerializer):
    """
    Serializer for EncounterDraft model.
    Handles auto-save of encounter SOAP notes and related clinical data.
    """
    draft_id = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    created_by_id = serializers.SerializerMethodField()
    hospital_id = serializers.SerializerMethodField()

    class Meta:
        model = EncounterDraft
        fields = [
            'draft_id',
            'encounter',
            'patient_id',
            'hospital_id',
            'created_by_id',
            'draft_data',
            'last_saved_at',
            'created_at',
        ]
        read_only_fields = ['draft_id', 'last_saved_at', 'created_at']

    def get_draft_id(self, obj):
        return str(obj.id)

    def get_patient_id(self, obj):
        return str(obj.patient.id)

    def get_created_by_id(self, obj):
        return str(obj.created_by.id)

    def get_hospital_id(self, obj):
        return str(obj.hospital.id)


class EncounterDraftCreateUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating/updating EncounterDraft via PATCH endpoint.
    Accepts partial draft_data JSON updates.
    """
    class Meta:
        model = EncounterDraft
        fields = ['draft_data']

    def validate_draft_data(self, value):
        """Ensure draft_data is a dict and not empty."""
        if not isinstance(value, dict):
            raise serializers.ValidationError("draft_data must be a JSON object.")
        if not value:
            raise serializers.ValidationError("draft_data cannot be empty.")
        return value

    def update(self, instance, validated_data):
        """
        Merge draft_data updates (don't overwrite entire dict).
        If new draft_data has keys, merge them with existing.
        """
        draft_data = validated_data.get('draft_data', {})
        if draft_data:
            # Merge: new data overwrites existing keys, but preserves unmentioned keys
            instance.draft_data.update(draft_data)
        instance.save()
        return instance


class TaskStatusSerializer(serializers.Serializer):
    """Serializer for Celery task status response."""
    task_id = serializers.CharField()
    status = serializers.CharField()  # PENDING, STARTED, SUCCESS, FAILURE, RETRY
    result = serializers.JSONField(required=False, allow_null=True)
    error_message = serializers.CharField(required=False, allow_null=True)
    traceback = serializers.CharField(required=False, allow_null=True)
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()
    task_type = serializers.CharField(required=False, allow_null=True)
    resource_type = serializers.CharField(required=False, allow_null=True)
    resource_id = serializers.CharField(required=False, allow_null=True)


class TaskResultSerializer(serializers.Serializer):
    """Serializer for full task result response."""
    task_id = serializers.CharField()
    status = serializers.CharField()
    result = serializers.JSONField()
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()


class TaskSubmissionSerializer(serializers.ModelSerializer):
    """Serializer for TaskSubmission model."""
    task_submission_id = serializers.SerializerMethodField()

    class Meta:
        model = TaskSubmission
        fields = [
            "task_submission_id",
            "celery_task_id",
            "task_type",
            "resource_type",
            "resource_id",
            "submitted_at",
            "expires_at",
        ]

    def get_task_submission_id(self, obj):
        return str(obj.id)


class LabOrderSerializerRestricted(serializers.ModelSerializer):
    """
    Lab Technician view: restricted to lab-order-specific fields only.
    EXCLUDES: diagnoses, prescriptions, allergy_flag, vitals, nursing notes, patient clinical history.
    """
    id = serializers.SerializerMethodField()
    test_name = serializers.CharField()
    urgency = serializers.CharField()
    lab_unit_id = serializers.SerializerMethodField()
    status = serializers.CharField()

    class Meta:
        model = LabOrder
        fields = [
            "id",
            "test_name",
            "urgency",
            "lab_unit_id",
            "status",
        ]

    def get_id(self, obj):
        return str(obj.id)

    def get_lab_unit_id(self, obj):
        return str(obj.lab_unit_id) if obj.lab_unit_id else None


class LabResultSerializerRestricted(serializers.ModelSerializer):
    """
    Lab Technician view: restricted to lab-result-specific fields only.
    """
    id = serializers.SerializerMethodField()
    lab_order_id = serializers.SerializerMethodField()
    test_name = serializers.CharField()
    result_value = serializers.CharField()
    reference_range = serializers.CharField()
    status = serializers.CharField()

    class Meta:
        model = LabResult
        fields = [
            "id",
            "lab_order_id",
            "test_name",
            "result_value",
            "reference_range",
            "status",
        ]

    def get_id(self, obj):
        return str(obj.id)

    def get_lab_order_id(self, obj):
        return str(obj.lab_order_id)


class AIAnalysisJobSerializer(serializers.Serializer):
    """
    Serializer for AIAnalysisJob status and results.
    Used by GET /ai/async-analysis/:job_id to return job status.
    """
    job_id = serializers.SerializerMethodField()
    patient_id = serializers.SerializerMethodField()
    status = serializers.CharField()
    progress_percent = serializers.IntegerField()
    current_step = serializers.CharField()
    analysis_type = serializers.CharField()
    created_at = serializers.DateTimeField()
    started_at = serializers.DateTimeField(allow_null=True)
    completed_at = serializers.DateTimeField(allow_null=True)
    # Results only populated when status == 'completed'
    analysis = serializers.SerializerMethodField()
    error_message = serializers.CharField(allow_blank=True, allow_null=True)

    def get_job_id(self, obj):
        return str(obj.id)

    def get_patient_id(self, obj):
        return str(obj.patient_id)

    def get_analysis(self, obj):
        """Return analysis data if job is completed; otherwise None."""
        if obj.status == 'completed' and obj.analysis_result:
            # Return the analysis ID and key fields
            return {
                'analysis_id': str(obj.analysis_result.id),
                'analysis_type': obj.analysis_result.analysis_type,
                'overall_confidence': obj.analysis_result.overall_confidence,
                'clinical_summary': obj.analysis_result.clinical_summary,
            }
        return None


class ShiftHandoverSerializer(serializers.ModelSerializer):
    """
    Serialize shift handover with SBAR structure and dual signatures.

    Used in:
    - POST /nurse/shift-handover — Submit handover
    - GET /nurse/shift-handover/:id — Retrieve handover
    - POST /nurse/shift-handover/:id/acknowledge — Acknowledge handover
    """
    id = serializers.SerializerMethodField()
    shift_id = serializers.SerializerMethodField()
    outgoing_nurse_id = serializers.SerializerMethodField()
    outgoing_nurse = serializers.SerializerMethodField()
    incoming_nurse_id = serializers.SerializerMethodField()
    incoming_nurse = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    critical_patients = serializers.SerializerMethodField()

    class Meta:
        model = ShiftHandover
        fields = [
            'id', 'shift_id',
            'outgoing_nurse_id', 'outgoing_nurse',
            'incoming_nurse_id', 'incoming_nurse',
            'sbar_situation', 'sbar_background', 'sbar_assessment', 'sbar_recommendation',
            'critical_patients',
            'outgoing_signed_at', 'incoming_acknowledged_at',
            'status',
        ]
        read_only_fields = ['id', 'shift_id', 'outgoing_signed_at', 'status']

    def get_id(self, obj):
        return str(obj.id)

    def get_shift_id(self, obj):
        return str(obj.shift_id)

    def get_outgoing_nurse_id(self, obj):
        return str(obj.nurse_id)

    def get_outgoing_nurse(self, obj):
        """Return outgoing nurse details."""
        if not obj.nurse:
            return None
        return {
            'user_id': str(obj.nurse.id),
            'full_name': obj.nurse.full_name,
            'email': obj.nurse.email,
            'role': obj.nurse.role,
        }

    def get_incoming_nurse_id(self, obj):
        if not obj.incoming_nurse_id:
            return None
        return str(obj.incoming_nurse_id)

    def get_incoming_nurse(self, obj):
        """Return incoming nurse details if assigned."""
        if not obj.incoming_nurse:
            return None
        return {
            'user_id': str(obj.incoming_nurse.id),
            'full_name': obj.incoming_nurse.full_name,
            'email': obj.incoming_nurse.email,
            'role': obj.incoming_nurse.role,
        }

    def get_status(self, obj):
        """Return handover status: pending or acknowledged."""
        return obj.status

    def get_critical_patients(self, obj):
        """Return list of critical patient IDs."""
        return [str(p.id) for p in obj.critical_patients.all()]


class PatientCreateSerializer(serializers.ModelSerializer):
    """Serializer for patient creation with mandatory fields."""
    class Meta:
        model = Patient
        fields = [
            "ghana_health_id",
            "full_name",
            "date_of_birth",
            "gender",
            "blood_group",
            "phone",
            "national_id",
            "nhis_number",
            "passport_number",
            "registered_at",
        ]

    def validate_ghana_health_id(self, value):
        if Patient.objects.filter(ghana_health_id=value).exists():
            raise serializers.ValidationError("Patient with this Ghana Health ID already exists")
        return value

    def create(self, validated_data):
        # hospital and created_by should be handled in the view or here via context
        request = self.context.get("request")
        if request:
            validated_data["created_by"] = request.user
        return super().create(validated_data)


class InvoiceItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = InvoiceItem
        fields = ["description", "quantity", "unit_price", "service_type"]

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError("Quantity must be greater than zero")
        return value

    def validate_unit_price(self, value):
        if value < 0:
            raise serializers.ValidationError("Unit price cannot be negative")
        return value


class InvoiceCreateSerializer(serializers.ModelSerializer):
    items = InvoiceItemSerializer(many=True, write_only=True)

    class Meta:
        model = Invoice
        fields = [
            "patient",
            "hospital",
            "payment_method",
            "notes",
            "items"
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        request = self.context.get("request")
        if request:
            validated_data["created_by"] = request.user
        
        # Calculate total amount
        total_amount = sum(item["quantity"] * item["unit_price"] for item in items_data)
        validated_data["total_amount"] = total_amount
        validated_data["status"] = "pending"

        with transaction.atomic():
            invoice = Invoice.objects.create(**validated_data)
            for item_data in items_data:
                line_total = item_data["quantity"] * item_data["unit_price"]
                InvoiceItem.objects.create(
                    invoice=invoice,
                    line_total=line_total,
                    **item_data
                )
        return invoice
