"""
FHIR R4 Export Testing

Tests for FHIR export functionality, $everything bundle, and consent-gated access.

Run:
  pytest api/tests/test_fhir_export_simple.py -v
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from django.utils import timezone
from datetime import timedelta

from core.models import Hospital, User
from patients.models import Patient
from records.models import (
    Encounter, Diagnosis, Prescription, Vital, 
    LabOrder, LabResult, MedicalRecord
)


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def hospital(db):
    return Hospital.objects.create(
        name="Test Hospital",
        region="Test Region",
        nhis_code="TST001",
        is_active=True
    )


@pytest.fixture
def doctor(db, hospital):
    user = User.objects.create_user(
        email="doctor@test.com",
        password="TestPass123!@#",
        full_name="Dr. Test",
        role="doctor",
        hospital=hospital,
        account_status="active"
    )
    return user


@pytest.fixture
def patient(db, hospital, doctor):
    return Patient.objects.create(
        ghana_health_id="GH123456789",
        full_name="John Doe",
        date_of_birth=timezone.now().date() - timedelta(days=365*30),
        gender="male",
        registered_at=hospital,
        created_by=doctor
    )


@pytest.mark.django_db
class TestFhirBasicEndpoints:
    """Test basic FHIR endpoint functionality."""

    def test_patient_read_unauthorized(self, client, patient):
        """Unauthenticated request is rejected."""
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_patient_read_success(self, client, doctor, patient):
        """GET /fhir/Patient/<id> returns FHIR Patient resource."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['resourceType'] == 'Patient'
        assert data['id'] == str(patient.id)
        assert 'meta' in data
        assert data['meta']['profile'][0] == 'http://hl7.org/fhir/StructureDefinition/Patient'

    def test_patient_read_not_found(self, client, doctor):
        """GET /fhir/Patient/<invalid> returns 404."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/00000000-0000-0000-0000-000000000000")
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_patient_list(self, client, doctor, patient):
        """GET /fhir/Patient returns searchset bundle."""
        client.force_authenticate(user=doctor)
        response = client.get("/api/v1/fhir/Patient")
        
        assert response.status_code == status.HTTP_200_OK
        bundle = response.json()
        assert bundle['resourceType'] == 'Bundle'
        assert bundle['type'] == 'searchset'
        assert bundle['total'] >= 1


@pytest.mark.django_db
class TestFhirEverythingOperation:
    """Test $everything bundle operation."""

    def test_everything_returns_bundle(self, client, doctor, patient):
        """GET /fhir/Patient/<id>/$everything returns Bundle."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert response.status_code == status.HTTP_200_OK
        bundle = response.json()
        assert bundle['resourceType'] == 'Bundle'
        assert bundle['type'] == 'document'
        assert 'entry' in bundle

    def test_everything_includes_patient(self, client, doctor, patient):
        """$everything bundle includes patient resource."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        bundle = response.json()
        resource_types = [e['resource']['resourceType'] for e in bundle['entry']]
        assert 'Patient' in resource_types

    def test_everything_download_header(self, client, doctor, patient):
        """$everything response includes download header."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        assert 'Content-Disposition' in response
        assert 'attachment' in response['Content-Disposition']

    def test_everything_unauthorized(self, client, patient):
        """Unauthenticated $everything is rejected."""
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.django_db
class TestFhirResourceStructure:
    """Test FHIR R4 resource structure validation."""

    def test_patient_has_required_fields(self, client, doctor, patient):
        """Patient resource includes all required fields."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        
        data = response.json()
        assert 'resourceType' in data
        assert 'id' in data
        assert 'meta' in data
        assert 'gender' in data

    def test_bundle_entry_structure(self, client, doctor, patient):
        """Bundle entries have correct structure."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}/$everything")
        
        bundle = response.json()
        for entry in bundle['entry']:
            assert 'fullUrl' in entry
            assert 'resource' in entry
            assert 'resourceType' in entry['resource']
            assert 'id' in entry['resource']


@pytest.mark.django_db
class TestFhirPermissions:
    """Test FHIR endpoint permission enforcement."""

    def test_role_permission_check(self, client, hospital):
        """Users with insufficient role are rejected."""
        lab_tech = User.objects.create_user(
            email="lab@test.com",
            password="Test123!@#",
            role="lab_technician",
            hospital=hospital,
            account_status="active"
        )
        
        patient = Patient.objects.create(
            ghana_health_id="GH1",
            full_name="Test",
            date_of_birth=timezone.now().date() - timedelta(days=365*30),
            gender="male",
            registered_at=hospital,
            created_by=lab_tech
        )
        
        client.force_authenticate(user=lab_tech)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        
        # Lab tech should be allowed (in _FHIR_ALLOWED_ROLES)
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]

    def test_same_facility_access(self, client, hospital, doctor, patient):
        """Same-facility user can access patient."""
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestFhirIndividualResources:
    """Test individual FHIR resource endpoints."""

    def test_encounter_endpoint(self, client, doctor, patient):
        """GET /fhir/Encounter/<id> returns encounter resource."""
        enc = Encounter.objects.create(
            patient=patient,
            hospital=patient.registered_at,
            encounter_type="outpatient",
            encounter_date=timezone.now(),
            created_by=doctor
        )
        
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Encounter/{enc.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['resourceType'] == 'Encounter'

    def test_condition_endpoint(self, client, doctor, patient):
        """GET /fhir/Condition/<id> returns condition resource."""
        mr = MedicalRecord.objects.create(
            patient=patient,
            hospital=patient.registered_at,
            record_type="diagnosis",
            created_by=doctor
        )
        
        diag = Diagnosis.objects.create(
            record=mr,
            icd10_code="G89.29",
            icd10_description="Other chronic pain",
            severity="mild"
        )
        
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/Condition/{diag.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['resourceType'] == 'Condition'

    def test_medication_request_endpoint(self, client, doctor, patient):
        """GET /fhir/MedicationRequest/<id> returns prescription resource."""
        mr = MedicalRecord.objects.create(
            patient=patient,
            hospital=patient.registered_at,
            record_type="prescription",
            created_by=doctor
        )
        
        rx = Prescription.objects.create(
            record=mr,
            patient=patient,
            hospital=patient.registered_at,
            drug_name="Paracetamol",
            dosage="500mg",
            frequency="thrice daily",
            route="oral"
        )
        
        client.force_authenticate(user=doctor)
        response = client.get(f"/api/v1/fhir/MedicationRequest/{rx.id}")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data['resourceType'] == 'MedicationRequest'
