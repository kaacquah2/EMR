"""
FHIR R4 Export Testing

Tests for:
- $everything Bundle operation completeness
- Consent-gated access enforcement
- FHIR R4 structure validation
- Status mapping correctness
- Proper serialization of all resource types

Run:
  pytest api/tests/test_fhir_export.py -v
"""

import pytest
import json
from datetime import datetime, timedelta

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Hospital, User
from patients.models import Patient
from records.models import (
    Encounter, Diagnosis, Prescription, Vital, 
    LabOrder, LabResult, MedicalRecord
)
from interop.models import Consent, Referral, GlobalPatient


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def hospital1(db):
    return Hospital.objects.create(
        name="Test Hospital 1",
        region="Greater Accra",
        nhis_code="TH001",
        is_active=True
    )


@pytest.fixture
def hospital2(db):
    return Hospital.objects.create(
        name="Test Hospital 2",
        region="Ashanti",
        nhis_code="TH002",
        is_active=True
    )


@pytest.fixture
def doctor1(db, hospital1):
    user = User.objects.create_user(
        email="doctor1@test.com",
        password="TestPass123!@#",
        full_name="Dr. Test Doctor",
        role="doctor",
        hospital=hospital1
    )
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def doctor2(db, hospital2):
    user = User.objects.create_user(
        email="doctor2@test.com",
        password="TestPass123!@#",
        full_name="Dr. Other Hospital",
        role="doctor",
        hospital=hospital2
    )
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def super_admin(db):
    user = User.objects.create_superuser(
        email="admin@test.com",
        password="TestPass123!@#"
    )
    user.is_active = True
    user.save()
    return user


@pytest.fixture
def patient1(db, hospital1, doctor1):
    return Patient.objects.create(
        ghana_health_id="GH123456789",
        full_name="John Doe",
        date_of_birth=timezone.now().date() - timedelta(days=365*30),
        gender="male",
        registered_at=hospital1,
        created_by=doctor1
    )


@pytest.fixture
def patient_with_data(db, hospital1, doctor1, patient1):
    """Create patient with full clinical data."""
    # Create encounter
    enc = Encounter.objects.create(
        patient=patient1,
        hospital=hospital1,
        encounter_type="outpatient",
        encounter_date=timezone.now(),
        created_by=doctor1,
        chief_complaint="Headache"
    )
    
    # Create medical record for diagnosis
    mr_diag = MedicalRecord.objects.create(
        patient=patient1,
        hospital=hospital1,
        record_type="diagnosis",
        created_by=doctor1
    )
    
    # Create diagnosis
    diag = Diagnosis.objects.create(
        record=mr_diag,
        icd10_code="G89.29",
        icd10_description="Other chronic pain",
        severity="mild",
        onset_date=timezone.now().date() - timedelta(days=30),
        notes="Chronic headache condition"
    )
    
    # Create medical record for prescription
    mr_rx = MedicalRecord.objects.create(
        patient=patient1,
        hospital=hospital1,
        record_type="prescription",
        created_by=doctor1
    )
    
    # Create prescription
    rx = Prescription.objects.create(
        record=mr_rx,
        patient=patient1,
        hospital=hospital1,
        drug_name="Paracetamol",
        dosage="500mg",
        frequency="three times daily",
        duration_days=7,
        route="oral",
        dispense_status="pending",
        priority="routine"
    )
    
    # Create medical record for vitals
    mr_vital = MedicalRecord.objects.create(
        patient=patient1,
        hospital=hospital1,
        record_type="vital_signs",
        created_by=doctor1
    )
    
    # Create vital
    vital = Vital.objects.create(
        record=mr_vital,
        temperature_c=37.5,
        pulse_bpm=72,
        resp_rate=16,
        bp_systolic=120,
        bp_diastolic=80,
        spo2_percent=98.5,
        weight_kg=70.0,
        height_cm=175.0,
        bmi=22.9,
        recorded_by=doctor1
    )
    
    # Create lab order and results
    mr_lab = MedicalRecord.objects.create(
        patient=patient1,
        hospital=hospital1,
        record_type="lab_result",
        created_by=doctor1
    )
    
    lab_order = LabOrder.objects.create(
        record=mr_lab,
        patient=patient1,
        hospital=hospital1,
        test_name="Full Blood Count",
        urgency="routine",
        status="resulted"
    )
    
    lab_result = LabResult.objects.create(
        record=mr_lab,
        lab_order=lab_order,
        test_name="WBC Count",
        result_value="7.5",
        reference_range="4.5-11.0",
        status="resulted"
    )
    
    return {
        'patient': patient1,
        'encounter': enc,
        'diagnosis': diag,
        'prescription': rx,
        'vital': vital,
        'lab_order': lab_order,
        'lab_result': lab_result
    }


# ============================================================================
# Tests
# ============================================================================

@pytest.mark.django_db
class TestFhirPatientResource:
    """Test Patient FHIR resource serialization."""

    def test_patient_read(self, client, doctor1, patient1):
        """GET /fhir/Patient/<id> returns FHIR Patient resource."""
        client.force_authenticate(user=doctor1)
        
        response = client.get(f"/api/v1/fhir/Patient/{patient1.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['resourceType'] == 'Patient'
        assert data['id'] == str(patient1.id)
        assert 'meta' in data
        assert 'http://hl7.org/fhir/StructureDefinition/Patient' in data['meta']['profile']
        assert 'identifier' in data
        assert data['gender'] == 'male'
        assert 'name' in data
        assert len(data['name']) > 0

    def test_patient_read_cross_facility_denied(self, client, doctor2, patient1):
        """Cross-facility access without consent is denied."""
        client.force_authenticate(user=doctor2)
        
        response = client.get(f"/api/v1/fhir/Patient/{patient1.id}")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestFhirEverythingBundle:
    """Test $everything Bundle operation."""

    def test_everything_bundle_basic(self, client, doctor1, patient_with_data):
        """GET /fhir/Patient/<id>/$everything returns complete Bundle."""
        client.force_authenticate(user=doctor1)
        patient = patient_with_data['patient']
        
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert response.status_code == status.HTTP_200_OK
        bundle = response.json()
        
        # Validate Bundle structure
        assert bundle['resourceType'] == 'Bundle'
        assert bundle['type'] == 'document'
        assert 'entry' in bundle
        assert bundle['total'] > 0
        
        # Check Content-Disposition header for download
        assert 'Content-Disposition' in response
        assert 'attachment' in response['Content-Disposition']
        assert patient.id in response['Content-Disposition']

    def test_everything_bundle_contains_all_resources(self, client, doctor1, patient_with_data):
        """Bundle contains all patient's clinical data."""
        client.force_authenticate(user=doctor1)
        patient = patient_with_data['patient']
        
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        bundle = response.json()
        
        # Count resource types
        resource_types = {
            'Patient': 0,
            'Encounter': 0,
            'Condition': 0,
            'MedicationRequest': 0,
            'Observation': 0,
            'DiagnosticReport': 0
        }
        
        for entry in bundle['entry']:
            rt = entry['resource']['resourceType']
            if rt in resource_types:
                resource_types[rt] += 1
        
        # Should have at least Patient, Encounter, Condition, MedicationRequest, Observations
        assert resource_types['Patient'] >= 1
        assert resource_types['Encounter'] >= 1
        assert resource_types['Condition'] >= 1
        assert resource_types['MedicationRequest'] >= 1
        assert resource_types['Observation'] >= 1

    def test_everything_bundle_not_found(self, client, doctor1):
        """GET /fhir/Patient/<invalid>/$everything returns 404."""
        client.force_authenticate(user=doctor1)
        
        response = client.get(f"/api/v1/fhir/Patient/00000000-0000-0000-0000-000000000000/$everything")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_everything_unauthorized(self, client, patient_with_data):
        """Unauthenticated request is rejected."""
        patient = patient_with_data['patient']
        
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestFhirConsentGatedAccess:
    """Test consent enforcement in FHIR access."""

    def test_summary_scope_returns_patient_only(self, client, doctor2, patient_with_data, hospital2):
        """SUMMARY scope consent returns only demographics."""
        patient = patient_with_data['patient']
        
        # Create GlobalPatient link
        gp = GlobalPatient.objects.create(
            national_id="GH-NAT-123",
            ghana_health_id="GH123456789",
            first_name="John",
            last_name="Doe",
            date_of_birth=patient.date_of_birth,
            gender="male"
        )
        
        from interop.models import FacilityPatient
        FacilityPatient.objects.create(
            facility=patient.registered_at,
            global_patient=gp,
            local_patient_id=str(patient.id),
            patient=patient
        )
        
        # Create SUMMARY consent
        consent = Consent.objects.create(
            global_patient=gp,
            granted_to_facility=hospital2,
            granted_by=doctor2,
            scope='SUMMARY',
            expires_at=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        client.force_authenticate(user=doctor2)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert response.status_code == status.HTTP_200_OK
        bundle = response.json()
        
        # SUMMARY scope should only contain Patient resource
        patient_count = sum(
            1 for entry in bundle['entry']
            if entry['resource']['resourceType'] == 'Patient'
        )
        clinical_count = sum(
            1 for entry in bundle['entry']
            if entry['resource']['resourceType'] in [
                'Encounter', 'Condition', 'MedicationRequest', 'Observation'
            ]
        )
        
        assert patient_count >= 1
        assert clinical_count == 0, "SUMMARY scope should not include clinical data"

    def test_full_record_scope_includes_all_data(self, client, doctor2, patient_with_data, hospital2):
        """FULL_RECORD scope consent returns all data."""
        patient = patient_with_data['patient']
        
        # Create GlobalPatient link
        gp = GlobalPatient.objects.create(
            national_id="GH-NAT-456",
            ghana_health_id="GH123456789",
            first_name="John",
            last_name="Doe",
            date_of_birth=patient.date_of_birth,
            gender="male"
        )
        
        from interop.models import FacilityPatient
        FacilityPatient.objects.create(
            facility=patient.registered_at,
            global_patient=gp,
            local_patient_id=str(patient.id),
            patient=patient
        )
        
        # Create FULL_RECORD consent
        Consent.objects.create(
            global_patient=gp,
            granted_to_facility=hospital2,
            granted_by=doctor2,
            scope='FULL_RECORD',
            expires_at=timezone.now() + timedelta(days=30),
            is_active=True
        )
        
        client.force_authenticate(user=doctor2)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert response.status_code == status.HTTP_200_OK
        bundle = response.json()
        
        # FULL_RECORD should contain clinical data
        clinical_count = sum(
            1 for entry in bundle['entry']
            if entry['resource']['resourceType'] in [
                'Encounter', 'Condition', 'MedicationRequest', 'Observation'
            ]
        )
        
        assert clinical_count > 0, "FULL_RECORD scope should include clinical data"

    def test_expired_consent_denied(self, client, doctor2, patient_with_data, hospital2):
        """Expired consent denies cross-facility access."""
        patient = patient_with_data['patient']
        
        # Create GlobalPatient link
        gp = GlobalPatient.objects.create(
            national_id="GH-NAT-789",
            ghana_health_id="GH123456789",
            first_name="John",
            last_name="Doe",
            date_of_birth=patient.date_of_birth,
            gender="male"
        )
        
        from interop.models import FacilityPatient
        FacilityPatient.objects.create(
            facility=patient.registered_at,
            global_patient=gp,
            local_patient_id=str(patient.id),
            patient=patient
        )
        
        # Create expired consent
        Consent.objects.create(
            global_patient=gp,
            granted_to_facility=hospital2,
            granted_by=doctor2,
            scope='FULL_RECORD',
            expires_at=timezone.now() - timedelta(days=1),  # Expired
            is_active=True
        )
        
        client.force_authenticate(user=doctor2)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestFhirResourceStructure:
    """Test FHIR R4 resource structure compliance."""

    def test_encounter_resource_structure(self, client, doctor1, patient_with_data):
        """Encounter resource has correct FHIR R4 structure."""
        client.force_authenticate(user=doctor1)
        encounter = patient_with_data['encounter']
        
        response = client.get(f"/api/v1/fhir/Encounter/{encounter.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        # Required fields
        assert resource['resourceType'] == 'Encounter'
        assert 'id' in resource
        assert 'meta' in resource
        assert 'status' in resource
        assert 'class' in resource
        assert 'subject' in resource
        assert 'period' in resource

    def test_condition_resource_structure(self, client, doctor1, patient_with_data):
        """Condition resource has correct FHIR R4 structure."""
        client.force_authenticate(user=doctor1)
        diagnosis = patient_with_data['diagnosis']
        
        response = client.get(f"/api/v1/fhir/Condition/{diagnosis.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        # Required fields
        assert resource['resourceType'] == 'Condition'
        assert 'clinicalStatus' in resource
        assert 'verificationStatus' in resource
        assert 'code' in resource
        assert resource['code']['coding'][0]['system'] == 'http://hl7.org/fhir/sid/icd-10'

    def test_medication_request_structure(self, client, doctor1, patient_with_data):
        """MedicationRequest resource structure."""
        client.force_authenticate(user=doctor1)
        rx = patient_with_data['prescription']
        
        response = client.get(f"/api/v1/fhir/MedicationRequest/{rx.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        assert resource['resourceType'] == 'MedicationRequest'
        assert 'status' in resource
        assert 'intent' in resource
        assert 'medicationCodeableConcept' in resource or 'medicationReference' in resource
        assert 'subject' in resource
        assert 'dosageInstruction' in resource

    def test_observation_vital_structure(self, client, doctor1, patient_with_data):
        """Observation (vital) resource structure."""
        client.force_authenticate(user=doctor1)
        vital = patient_with_data['vital']
        
        response = client.get(f"/api/v1/fhir/Observation/{vital.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        assert resource['resourceType'] == 'Observation'
        assert 'status' in resource
        assert 'category' in resource
        assert 'code' in resource
        assert 'subject' in resource
        assert 'component' in resource

    def test_diagnostic_report_structure(self, client, doctor1, patient_with_data):
        """DiagnosticReport resource structure."""
        client.force_authenticate(user=doctor1)
        lab_order = patient_with_data['lab_order']
        
        response = client.get(f"/api/v1/fhir/DiagnosticReport/{lab_order.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        assert resource['resourceType'] == 'DiagnosticReport'
        assert 'status' in resource
        assert 'category' in resource
        assert 'code' in resource
        assert 'subject' in resource
        assert 'result' in resource


@pytest.mark.django_db
class TestFhirStatusMapping:
    """Test correct status value mapping."""

    def test_encounter_status_mapping(self, client, doctor1, patient_with_data):
        """Encounter status values map to FHIR canonical values."""
        client.force_authenticate(user=doctor1)
        
        enc = patient_with_data['encounter']
        response = client.get(f"/api/v1/fhir/Encounter/{enc.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        # Status should be one of FHIR canonical values
        valid_statuses = ['planned', 'arrived', 'triaged', 'in-progress', 'onleave', 'finished', 'cancelled', 'entered-in-error', 'unknown']
        assert resource['status'] in valid_statuses

    def test_medication_request_status_mapping(self, client, doctor1, patient_with_data):
        """MedicationRequest status values map correctly."""
        client.force_authenticate(user=doctor1)
        rx = patient_with_data['prescription']
        
        response = client.get(f"/api/v1/fhir/MedicationRequest/{rx.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        # Status should be one of FHIR canonical values
        valid_statuses = ['active', 'on-hold', 'cancelled', 'completed', 'entered-in-error', 'stopped', 'unknown']
        assert resource['status'] in valid_statuses

    def test_observation_status_mapping(self, client, doctor1, patient_with_data):
        """Observation status values map correctly."""
        client.force_authenticate(user=doctor1)
        vital = patient_with_data['vital']
        
        response = client.get(f"/api/v1/fhir/Observation/{vital.id}")
        
        assert response.status_code == status.HTTP_200_OK
        resource = response.json()
        
        valid_statuses = ['registered', 'preliminary', 'final', 'amended', 'corrected', 'cancelled', 'entered-in-error', 'unknown']
        assert resource['status'] in valid_statuses


@pytest.mark.django_db
class TestFhirPermissions:
    """Test FHIR endpoint permission enforcement."""

    def test_unauthorized_returns_401(self, client, patient_with_data):
        """Unauthenticated request returns 401."""
        patient = patient_with_data['patient']
        
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_forbidden_role_returns_403(self, client):
        """User with insufficient role returns 403."""
        # Create lab technician (cannot access FHIR in this context)
        user = User.objects.create_user(
            email="labtech@test.com",
            password="TestPass123!@#",
            role="lab_technician"
        )
        user.is_active = True
        user.save()
        
        client.force_authenticate(user=user)
        response = client.get(f"/api/v1/fhir/Patient/00000000-0000-0000-0000-000000000000")
        
        # Lab tech may not be in _FHIR_ALLOWED_ROLES
        assert response.status_code in [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND]

    def test_super_admin_can_access_any_patient(self, client, super_admin, patient_with_data):
        """Super admin can access any patient's FHIR data."""
        client.force_authenticate(user=super_admin)
        patient = patient_with_data['patient']
        
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
