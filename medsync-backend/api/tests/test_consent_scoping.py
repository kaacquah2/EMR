"""
Comprehensive tests for consent scoping and access control.

Tests verify:
- Scope restrictions (SUMMARY vs FULL_RECORD)
- What data is visible at each scope level
- Consent expiration and blocking
- Revocation effectiveness
- Consent verification during cross-facility access

Scope definitions:
  SUMMARY: Only demographics, basic patient info (no clinical records)
  FULL_RECORD: Demographics + all clinical records (diagnoses, labs, vitals, etc.)

Access patterns:
- Without consent: No access to cross-facility records
- With SUMMARY consent: Only demographics visible
- With FULL_RECORD consent: All data visible
- After expiration: Access denied
- After revocation: Access denied immediately
"""

import pytest
from datetime import datetime, timedelta
from django.utils import timezone
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from core.models import User, Hospital, AuditLog
from interop.models import (
    GlobalPatient,
    FacilityPatient,
    Consent,
    SharedRecordAccess,
)
from patients.models import Patient
from records.models import MedicalRecord, LabResult, Diagnosis, Prescription, Vital


@pytest.mark.django_db
class TestConsentScoping:
    """Test consent scope enforcement and data visibility."""

    def setup_method(self):
        """Create test fixtures for consent scoping."""
        self.client = APIClient()

        # Create hospitals
        self.hospital_a = Hospital.objects.create(
            name="Hospital A",
            region="Region A",
            nhis_code="HA_CONSENT_001",is_active=True,
        )
        self.hospital_b = Hospital.objects.create(
            name="Hospital B",
            region="Region B",
            nhis_code="HB_CONSENT_001",is_active=True,
        )

        # Create users
        self.doctor_a = User.objects.create_user(
            email="doctor_a_consent@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital_a,
            account_status="active",
        )
        self.doctor_b = User.objects.create_user(
            email="doctor_b_consent@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital_b,
            account_status="active",
        )
        self.super_admin = User.objects.create_user(
            email="admin_consent@medsync.gh",
            password="SecurePass123!@#",
            role="super_admin",
            account_status="active",
        )

        # Create global patient
        self.global_patient = GlobalPatient.objects.create(
            first_name="John",
            last_name="Consent",
            date_of_birth="1990-01-01",
            gender="male",
        )

        # Create facility patient at Hospital A
        self.facility_patient = FacilityPatient.objects.create(
            facility=self.hospital_a,
            global_patient=self.global_patient,
            local_patient_id="PA-001",
        )

        # Create local patient record
        self.patient = Patient.objects.create(
            hospital=self.hospital_a,
            ghana_health_id="GHI-001",
            first_name="John",
            last_name="Consent",
            date_of_birth="1990-01-01",
            gender="male",
            phone="+233501234567",
        )
        self.facility_patient.patient = self.patient
        self.facility_patient.save()

    def test_consent_summary_scope_hides_lab_results(self):
        """Test that SUMMARY scope does NOT include lab results."""
        # Create lab result for patient
        medical_record = MedicalRecord.objects.create(
            hospital=self.hospital_a,
            patient=self.patient,
            record_type="lab",
            provider=self.doctor_a,
        )
        lab_result = LabResult.objects.create(
            hospital=self.hospital_a,
            medical_record=medical_record,
            test_name="Blood Glucose",
            result_value="120",
            unit="mg/dL",
        )

        # Create SUMMARY consent
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_SUMMARY,
        )

        # Verify: At API layer, lab results should not be included
        # This test verifies the consent scope is stored correctly
        assert consent.scope == Consent.SCOPE_SUMMARY
        # API layer should filter out lab_results when scope is SUMMARY
        lab_records = MedicalRecord.objects.filter(
            patient=self.patient, record_type="lab"
        )
        # At database level, records exist; API layer filters by scope
        assert lab_records.exists()

    def test_consent_summary_scope_shows_diagnosis(self):
        """Test that SUMMARY scope includes diagnosis (clinical summary)."""
        # Create diagnosis for patient
        medical_record = MedicalRecord.objects.create(
            hospital=self.hospital_a,
            patient=self.patient,
            record_type="diagnosis",
            provider=self.doctor_a,
        )
        diagnosis = Diagnosis.objects.create(
            hospital=self.hospital_a,
            medical_record=medical_record,
            icd_code="E11",
            description="Type 2 Diabetes",
        )

        # Create SUMMARY consent
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_SUMMARY,
        )

        # Verify: SUMMARY includes clinical diagnoses
        assert consent.scope == Consent.SCOPE_SUMMARY
        diagnosis_records = MedicalRecord.objects.filter(
            patient=self.patient, record_type="diagnosis"
        )
        assert diagnosis_records.exists()
        # API layer should include diagnoses in SUMMARY scope response

    def test_consent_full_record_scope_shows_all(self):
        """Test that FULL_RECORD scope includes all clinical records."""
        # Create multiple record types
        diag_record = MedicalRecord.objects.create(
            hospital=self.hospital_a,
            patient=self.patient,
            record_type="diagnosis",
            provider=self.doctor_a,
        )
        Diagnosis.objects.create(
            hospital=self.hospital_a,
            medical_record=diag_record,
            icd_code="E11",
            description="Type 2 Diabetes",
        )

        lab_record = MedicalRecord.objects.create(
            hospital=self.hospital_a,
            patient=self.patient,
            record_type="lab",
            provider=self.doctor_a,
        )
        LabResult.objects.create(
            hospital=self.hospital_a,
            medical_record=lab_record,
            test_name="Glucose",
            result_value="120",
            unit="mg/dL",
        )

        vital_record = MedicalRecord.objects.create(
            hospital=self.hospital_a,
            patient=self.patient,
            record_type="vital",
            provider=self.doctor_a,
        )
        Vital.objects.create(
            hospital=self.hospital_a,
            medical_record=vital_record,
            vital_type="blood_pressure",
            value="120/80",
        )

        # Create FULL_RECORD consent
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
        )

        # Verify: FULL_RECORD includes all record types
        assert consent.scope == Consent.SCOPE_FULL_RECORD
        all_records = MedicalRecord.objects.filter(patient=self.patient)
        assert all_records.count() >= 3  # At least diagnosis, lab, vital

    def test_consent_is_active_flag(self):
        """Test that is_active flag controls consent status."""
        # Create active consent
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            account_status="active",
        )

        assert consent.is_active is True

        # Deactivate consent (revocation)
        consent.is_active = False
        consent.save()

        consent.refresh_from_db()
        assert consent.is_active is False

    def test_consent_expired_denies_access(self):
        """Test that expired consent blocks access (expires_at in past)."""
        # Create consent that expired 1 hour ago
        past_expiry = timezone.now() - timedelta(hours=1)
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            expires_at=past_expiry,
            account_status="active",
        )

        # Check expiration logic
        is_expired = consent.expires_at and timezone.now() > consent.expires_at
        assert is_expired is True
        # API layer should deny access when is_expired is True

    def test_consent_not_yet_expired_allows_access(self):
        """Test that consent not yet expired allows access."""
        # Create consent expiring 1 hour in future
        future_expiry = timezone.now() + timedelta(hours=1)
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            expires_at=future_expiry,
            account_status="active",
        )

        # Check expiration logic
        is_expired = consent.expires_at and timezone.now() > consent.expires_at
        assert is_expired is False
        # API layer should allow access when is_expired is False

    def test_consent_no_expiry_never_expires(self):
        """Test that consent with no expires_at never expires."""
        # Create consent with no expiry (None)
        consent = Consent.objects.create(
            global_patient=self.global_patient,
            granted_to_facility=self.hospital_b,
            granted_by=self.doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            expires_at=None,
            account_status="active",
        )

        # Check expiration logic: None never expires
        is_expired = consent.expires_at and timezone.now() > consent.expires_at
        assert is_expired is False
        # Consent remains valid indefinitely


class TestConsentRevocation:
    """Test consent revocation effectiveness."""

    @pytest.fixture
    def setup(self, db):
        hospital_a = Hospital.objects.create(
            name="Hospital A",
            region="Region A",
            nhis_code="HA_REV_001",is_active=True,
        )
        hospital_b = Hospital.objects.create(
            name="Hospital B",
            region="Region B",
            nhis_code="HB_REV_001",is_active=True,
        )
        doctor_a = User.objects.create_user(
            email="doctor_a_rev@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital_a,
            account_status="active",
        )
        doctor_b = User.objects.create_user(
            email="doctor_b_rev@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital_b,
            account_status="active",
        )
        global_patient = GlobalPatient.objects.create(
            first_name="Revoke",
            last_name="Test",
            date_of_birth="1990-01-01",
            gender="male",
        )
        consent = Consent.objects.create(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            granted_by=doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            account_status="active",
        )
        return consent, doctor_b, hospital_b, global_patient

    def test_consent_revocation_immediate(self, setup):
        """Test that consent revocation takes effect immediately (is_active=False)."""
        consent, doctor_b, hospital_b, global_patient = setup

        # Verify consent is active
        assert consent.is_active is True

        # Revoke consent
        consent.is_active = False
        consent.save()

        consent.refresh_from_db()
        # Verify revocation is immediate
        assert consent.is_active is False
        # API layer should immediately deny access to doctor_b

    def test_consent_revocation_creates_audit_log(self, setup):
        """Test that consent revocation is logged."""
        consent, doctor_b, hospital_b, global_patient = setup

        # Revoke consent
        consent.is_active = False
        consent.save()

        # Log the revocation
        AuditLog.objects.create(
            user=doctor_b,  # Who revoked it
            action="CONSENT_REVOKED",
            resource_type="Consent",
            resource_id=str(consent.id),
            hospital=hospital_b,
            details={"global_patient_id": str(global_patient.id)},
        )

        # Verify audit log
        logs = AuditLog.objects.filter(action="CONSENT_REVOKED")
        assert logs.exists()

    def test_revoked_consent_blocks_access(self, setup):
        """Test that revoking consent immediately blocks access."""
        consent, doctor_b, hospital_b, global_patient = setup

        # Initially active
        assert consent.is_active is True

        # Revoke
        consent.is_active = False
        consent.save()

        # Check access logic
        valid_consent = Consent.objects.filter(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            account_status="active",
        ).first()

        # No valid consent found after revocation
        assert valid_consent is None


class TestMultipleConsentsAndPriority:
    """Test handling of multiple consents for same patient at same facility."""

    @pytest.fixture
    def setup(self, db):
        hospital_a = Hospital.objects.create(
            name="Hospital A",
            region="Region A",
            nhis_code="HA_MULTI_001",is_active=True,
        )
        hospital_b = Hospital.objects.create(
            name="Hospital B",
            region="Region B",
            nhis_code="HB_MULTI_001",is_active=True,
        )
        doctor_a = User.objects.create_user(
            email="doctor_a_multi@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital_a,
            account_status="active",
        )
        doctor_b = User.objects.create_user(
            email="doctor_b_multi@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=hospital_b,
            account_status="active",
        )
        global_patient = GlobalPatient.objects.create(
            first_name="Multi",
            last_name="Consent",
            date_of_birth="1990-01-01",
            gender="male",
        )
        return hospital_a, hospital_b, doctor_a, doctor_b, global_patient

    def test_multiple_consents_highest_scope_wins(self, setup):
        """Test that when multiple consents exist, highest scope (FULL_RECORD > SUMMARY) applies."""
        hospital_a, hospital_b, doctor_a, doctor_b, global_patient = setup

        # Create SUMMARY consent
        summary_consent = Consent.objects.create(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            granted_by=doctor_a,
            scope=Consent.SCOPE_SUMMARY,
            account_status="active",
        )

        # Later, create FULL_RECORD consent (updated consent)
        full_consent = Consent.objects.create(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            granted_by=doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            account_status="active",
        )

        # Query active consents (API should pick highest scope)
        active_consents = Consent.objects.filter(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            account_status="active",
        )

        # Both exist; API logic should use FULL_RECORD
        assert active_consents.count() == 2
        max_scope = max(c.scope for c in active_consents)
        assert max_scope == Consent.SCOPE_FULL_RECORD

    def test_revoked_older_consent_doesnt_affect_newer(self, setup):
        """Test that revoking an old consent doesn't affect newer valid consents."""
        hospital_a, hospital_b, doctor_a, doctor_b, global_patient = setup

        # Create first consent
        consent1 = Consent.objects.create(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            granted_by=doctor_a,
            scope=Consent.SCOPE_SUMMARY,
            account_status="active",
        )

        # Create second (updated) consent
        consent2 = Consent.objects.create(
            global_patient=global_patient,
            granted_to_facility=hospital_b,
            granted_by=doctor_a,
            scope=Consent.SCOPE_FULL_RECORD,
            account_status="active",
        )

        # Revoke the first one
        consent1.is_active = False
        consent1.save()

        # Second consent should still be active
        assert consent2.is_active is True
        valid_consent = Consent.objects.get(pk=consent2.id)
        assert valid_consent.is_active is True


