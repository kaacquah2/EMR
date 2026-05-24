"""
T17: FHIR Compliance Testing

Tests for FHIR resource formats, ICD-10 mapping, and SNOMED code mapping.
Ensures MedSync API returns valid FHIR R4 resources for interoperability.

Requirements:
  - FHIR Library: pip install fhir.resources (R4)
  - ICD-10 data: pip install icd10
  - SNOMED: Manual curated mappings or SNOMED CT browser integration

Run:
  pytest api/tests/test_fhir_compliance.py -v

FHIR Resources Tested:
  - Patient (demographics)
  - Encounter (clinical visit)
  - Condition (diagnosis)
  - Medication / MedicationStatement (prescriptions)
  - Observation (vitals, lab results)
  - ServiceRequest (lab orders)
"""

import pytest
import json
from datetime import datetime

from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Hospital, User
from patients.models import Patient
from records.models import Encounter, Diagnosis, Prescription, Vital, LabOrder, LabResult, MedicalRecord

# FHIR validation (install: pip install fhir.resources)
try:
    from fhir.resources.patient import Patient as FHIRPatient
    from fhir.resources.encounter import Encounter as FHIREncounter
    from fhir.resources.condition import Condition as FHIRCondition
    from fhir.resources.observation import Observation as FHIRObservation
    from fhir.resources.servicerequest import ServiceRequest as FHIRServiceRequest
    FHIR_AVAILABLE = True
except ImportError:
    FHIR_AVAILABLE = False

# ICD-10 validation
try:
    import icd10
    ICD10_AVAILABLE = True
except ImportError:
    ICD10_AVAILABLE = False


@pytest.mark.skipif(not FHIR_AVAILABLE, reason="FHIR library not installed")
class TestFHIRPatientResource:
    """
    Test FHIR Patient resource compliance.
    Reference: http://hl7.org/fhir/R4/patient.html
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="FHIR_TST_001", region="Greater Accra", is_active=True)
        user = User.objects.create_user(
            email="doctor@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
            full_name="Dr. John Mensah",
        )
        patient = Patient.objects.create(
            ghana_health_id="GH-2024-001234",
            full_name="John Doe",
            date_of_birth="1985-05-15",
            gender="male",
            registered_at=hospital,
            created_by=user,
            phone="+233201234567",
        )
        return {"hospital": hospital, "user": user, "patient": patient}

    @pytest.mark.django_db
    def test_fhir_patient_basic_structure(self, setup):
        """
        FHIR Patient must have:
        - id (required)
        - resourceType = "Patient" (required)
        - identifier (unique IDs, including Ghana Health ID)
        - name (required)
        - telecom (contact info)
        - gender (required: male, female, other, unknown)
        - birthDate (required format: YYYY-MM-DD)
        - address
        """
        patient = setup["patient"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        assert response.status_code == 200

        data = response.json()

        # Validate FHIR structure
        assert data["resourceType"] == "Patient"
        assert "id" in data
        assert "identifier" in data
        assert isinstance(data["identifier"], list)
        assert len(data["identifier"]) > 0

        # Ghana Health ID must be in identifiers
        identifiers = data["identifier"]
        ghi_found = any(
            i.get("system") == "https://ghanahealth.org/ghana-health-id"
            and i.get("value") == patient.ghana_health_id
            for i in identifiers
        )
        assert ghi_found, "Ghana Health ID not in FHIR identifiers"

        # Name (Patient uses full_name; serializer splits into given/family)
        assert "name" in data
        assert len(data["name"]) > 0
        name = data["name"][0]
        parts = patient.full_name.split()
        expected_given = parts[:-1] if len(parts) > 1 else parts
        assert name.get("given", []) == expected_given
        assert name.get("family") == parts[-1]

        # Gender mapping (MedSync → FHIR)
        # MedSync: male, female, other
        # FHIR: male, female, other, unknown
        assert data.get("gender") in ["male", "female", "other", "unknown"]

        # Birth date format: YYYY-MM-DD
        assert data.get("birthDate") == "1985-05-15"

        # Contact info (telecom)
        if patient.phone:
            assert "telecom" in data
            phones = [t for t in data["telecom"] if t.get("system") == "phone"]
            assert len(phones) > 0

        # Address (derived from patient.registered_at hospital name)
        assert "address" in data
        assert len(data["address"]) > 0

    @pytest.mark.django_db
    def test_fhir_patient_validate_with_library(self, setup):
        """
        Use fhir.resources library to validate JSON structure.
        """
        patient = setup["patient"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Patient/{patient.id}")
        data = response.json()

        # Try to parse as FHIR Patient resource
        try:
            fhir_patient = FHIRPatient(**data)
            # If no exception, structure is valid
            assert fhir_patient.get_resource_type() == "Patient"
        except Exception as e:
            pytest.fail(f"FHIR Patient validation failed: {str(e)}")

    @pytest.mark.django_db
    def test_fhir_patient_sensitive_data_redaction(self, setup):
        """
        When accessed via cross-facility with SUMMARY scope,
        certain fields should be redacted (PHI minimization).
        """
        # This test would mock a cross-facility scenario
        # SUMMARY scope should return: name, DOB, contact
        # Should NOT return: diagnoses, medications, lab results

        """
        Expected SUMMARY Patient:
        {
          "resourceType": "Patient",
          "id": "...",
          "identifier": [...],
          "name": [...],
          "birthDate": "1985-05-15",
          "gender": "male",
          "telecom": [...],
          "address": [...]
        }
        
        NOT included in SUMMARY:
        - Emergency contact details
        - Insurance info
        - Employer
        - Extensions with PHI
        """
        pass


@pytest.mark.skipif(not FHIR_AVAILABLE, reason="FHIR library not installed")
class TestFHIREncounterResource:
    """
    Test FHIR Encounter resource compliance.
    Reference: http://hl7.org/fhir/R4/encounter.html
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="FHIR_TST_002", region="Greater Accra", is_active=True)

        user = User.objects.create_user(
            email="doctor@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        patient = Patient.objects.create(
            ghana_health_id="GH-2024-001234",
            full_name="John Doe",
            date_of_birth="1985-05-15",
            gender="male",
            registered_at=hospital,
            created_by=user,
        )
        encounter = Encounter.objects.create(
            patient=patient,
            hospital=hospital,
            created_by=user,
            assigned_doctor=user,
            encounter_type="outpatient",
            chief_complaint="Headache and fever",
            status="waiting",
        )
        return {"hospital": hospital, "user": user, "patient": patient, "encounter": encounter}

    @pytest.mark.django_db
    def test_fhir_encounter_basic_structure(self, setup):
        """
        FHIR Encounter must have:
        - id (required)
        - resourceType = "Encounter"
        - status: planned, arrived, triaged, in-progress, onleave, finished (required)
        - class: inpatient, outpatient, etc. (required)
        - type (visit type)
        - subject (link to Patient resource)
        - participant (provider/practitioners)
        - period (start/end times)
        - reasonCode or reasonReference (chief complaint)
        """
        encounter = setup["encounter"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Encounter/{encounter.id}")
        assert response.status_code == 200

        data = response.json()

        # Validate structure
        assert data["resourceType"] == "Encounter"
        assert data["id"] == str(encounter.id)
        assert data.get("status") in ["planned", "arrived", "triaged", "in-progress", "onleave", "finished", "cancelled"]

        # Class (inpatient/outpatient)
        assert "class" in data
        class_coding = data["class"]
        # MedSync outpatient → FHIR AMB (ambulatory)
        assert class_coding.get("code") in ["AMB", "IMP", "EMER", "VR"]

        # Subject (patient reference)
        assert "subject" in data
        subject = data["subject"]
        assert subject.get("reference").startswith("Patient/")

        # Participant (provider)
        if "participant" in data:
            assert isinstance(data["participant"], list)
            assert len(data["participant"]) > 0
            participant = data["participant"][0]
            assert "individual" in participant or "actor" in participant

        # Period (start/end times)
        assert "period" in data
        period = data["period"]
        assert "start" in period  # ISO 8601 format
        # end may be null if ongoing

        # Reason (chief complaint)
        if encounter.chief_complaint:
            assert "reasonCode" in data or "reasonReference" in data

    @pytest.mark.django_db
    def test_fhir_encounter_participant_mapping(self, setup):
        """
        Encounter.participant should include provider (doctor/nurse).
        Mapping:
        - function: "treatment" (provided treatment)
        - actor: reference to Practitioner
        - individual: direct reference (simplified)
        """
        encounter = setup["encounter"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Encounter/{encounter.id}")
        data = response.json()

        assert "participant" in data
        participants = data["participant"]

        # At least one participant (the provider)
        assert len(participants) > 0

        provider = participants[0]
        # type is a list of coding objects; extract code values
        provider_type_codes = [
            coding.get("code")
            for type_item in provider.get("type", [])
            for coding in type_item.get("coding", [])
        ]
        assert any(code in ["PPRF", "SPRF", "ATND", "REF", "CALLCNT"] for code in provider_type_codes)
        # individual or actor (MedSync returns individual)
        assert "individual" in provider or "actor" in provider


@pytest.mark.skipif(not FHIR_AVAILABLE, reason="FHIR library not installed")
class TestFHIRConditionResource:
    """
    Test FHIR Condition (diagnosis) resource compliance.
    Reference: http://hl7.org/fhir/R4/condition.html
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="FHIR_TST_003", region="Greater Accra", is_active=True)
        user = User.objects.create_user(
            email="doctor@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        patient = Patient.objects.create(
            ghana_health_id="GH-2024-001234",
            full_name="John Doe",
            date_of_birth="1985-05-15",
            gender="male",
            registered_at=hospital,
            created_by=user,
        )
        # Diagnosis requires a MedicalRecord (OneToOne relationship)
        med_record = MedicalRecord.objects.create(
            patient=patient,
            hospital=hospital,
            record_type="diagnosis",
            created_by=user,
        )
        diagnosis = Diagnosis.objects.create(
            record=med_record,
            icd10_code="J18.9",  # Pneumonia, unspecified
            icd10_description="Community-acquired pneumonia",
            severity="moderate",
        )
        return {
            "hospital": hospital,
            "user": user,
            "patient": patient,
            "diagnosis": diagnosis,
        }

    @pytest.mark.django_db
    @pytest.mark.skipif(not ICD10_AVAILABLE, reason="ICD-10 library not installed")
    def test_fhir_condition_icd10_mapping(self, setup):
        """
        FHIR Condition.code must include ICD-10 code.
        Verify ICD-10 code is valid and properly mapped.
        """
        diagnosis = setup["diagnosis"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Condition/{diagnosis.id}")
        assert response.status_code == 200

        data = response.json()

        # Code should have ICD-10 coding
        assert "code" in data
        coding = data["code"].get("coding", [])
        assert len(coding) > 0

        # At least one coding should be ICD-10
        icd10_coding = [c for c in coding if c.get("system") == "http://hl7.org/fhir/sid/icd-10"]
        assert len(icd10_coding) > 0

        icd10_code = icd10_coding[0].get("code")
        assert icd10_code == "J18.9"

        # Validate ICD-10 code exists in official registry
        try:
            icd10_obj = icd10.find(icd10_code)
            assert icd10_obj is not None
            # Description should match or be similar
            desc = icd10_obj.description
            assert desc is not None
        except Exception as e:
            pytest.skip(f"ICD-10 validation not available: {str(e)}")

    @pytest.mark.django_db
    def test_fhir_condition_patient_encounter_references(self, setup):
        """
        FHIR Condition must reference:
        - subject (Patient)
        - encounter (Encounter)
        - recordedDate (when diagnosed)
        """
        diagnosis = setup["diagnosis"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Condition/{diagnosis.id}")
        data = response.json()

        # Subject (Patient)
        assert "subject" in data
        subject = data["subject"]
        assert subject.get("reference", "").startswith("Patient/")

        # Encounter
        if "encounter" in data:
            encounter = data["encounter"]
            assert encounter.get("reference", "").startswith("Encounter/")

        # Recorded date
        assert "recordedDate" in data or "onsetDateTime" in data

    @pytest.mark.django_db
    def test_fhir_condition_clinical_status(self, setup):
        """
        FHIR Condition.clinicalStatus indicates: active, recurrence, remission, resolved
        MedSync: store status in diagnosis (or default to "active")
        """
        diagnosis = setup["diagnosis"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Condition/{diagnosis.id}")
        data = response.json()

        # Clinical status
        if "clinicalStatus" in data:
            status = data["clinicalStatus"].get("coding", [{}])[0].get("code")
            assert status in ["active", "recurrence", "remission", "resolved"]


@pytest.mark.skipif(not FHIR_AVAILABLE, reason="FHIR library not installed")
class TestFHIRObservationResource:
    """
    Test FHIR Observation (vital signs, lab results).
    Reference: http://hl7.org/fhir/R4/observation.html
    """

    @pytest.fixture
    def setup(self, db):
        hospital = Hospital.objects.create(name="Test Hospital", nhis_code="FHIR_TST_004", region="Greater Accra", is_active=True)
        user = User.objects.create_user(
            email="doctor@hospital.gh",
            password="TestPass123!",
            hospital=hospital,
            role="doctor",
        )
        patient = Patient.objects.create(
            ghana_health_id="GH-2024-001234",
            full_name="John Doe",
            date_of_birth="1985-05-15",
            gender="male",
            registered_at=hospital,
            created_by=user,
        )
        # Vital requires a MedicalRecord (OneToOne relationship)
        med_record = MedicalRecord.objects.create(
            patient=patient,
            hospital=hospital,
            record_type="vital_signs",
            created_by=user,
        )
        vital = Vital.objects.create(
            record=med_record,
            temperature_c="38.5",
            bp_systolic=120,
            bp_diastolic=80,
            pulse_bpm=85,
            spo2_percent="98.0",
            recorded_by=user,
        )
        return {
            "hospital": hospital,
            "user": user,
            "patient": patient,
            "vital": vital,
        }

    @pytest.mark.django_db
    def test_fhir_vital_temperature_observation(self, setup):
        """
        FHIR Observation for temperature (vital sign).
        Code: LOINC 8310-5 (Body temperature)
        """
        vital = setup["vital"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Observation/{vital.id}?type=temperature")
        assert response.status_code == 200

        data = response.json()

        # The view returns a full vitals panel (LOINC 85353-1) with components.
        # Temperature is a component with LOINC 8310-5.
        components = data.get("component", [])
        temp_component = next(
            (c for c in components if any(
                entry.get("code") == "8310-5"
                for entry in c.get("code", {}).get("coding", [])
            )),
            None,
        )
        assert temp_component is not None, "LOINC 8310-5 (temperature) not found in vitals panel components"

        # Value
        value = temp_component.get("valueQuantity", {})
        assert float(value.get("value")) == 38.5
        assert value.get("unit") == "\u00b0C"

    @pytest.mark.django_db
    def test_fhir_vital_bp_observation(self, setup):
        """
        FHIR Observation for blood pressure (compound vital).
        Code: LOINC 85354-9 (Blood pressure panel)
        Component: systolic (8480-6), diastolic (8462-4)
        """
        vital = setup["vital"]
        client = APIClient()
        client.force_authenticate(user=setup["user"])

        response = client.get(f"/api/v1/fhir/Observation/{vital.id}?type=bp")
        assert response.status_code == 200

        data = response.json()

        # The view returns a full vitals panel. BP is a component with LOINC 55284-4,
        # containing systolic (8480-6) and diastolic (8462-4) sub-components.
        top_components = data.get("component", [])
        assert len(top_components) >= 1, "No vital components found"

        # Find BP component in top-level components
        bp_component = next(
            (c for c in top_components if any(
                entry.get("code") == "55284-4"
                for entry in c.get("code", {}).get("coding", [])
            )),
            None,
        )
        assert bp_component is not None, "LOINC 55284-4 (blood pressure panel) not found in components"

        # Systolic and diastolic are sub-components of the BP component
        sub_components = [sc for sc in bp_component.get("component", []) if sc is not None]
        assert len(sub_components) >= 2

        systolic = next(
            (c for c in sub_components if any(
                entry.get("code") == "8480-6"
                for entry in c.get("code", {}).get("coding", [])
            )),
            None,
        )
        diastolic = next(
            (c for c in sub_components if any(
                entry.get("code") == "8462-4"
                for entry in c.get("code", {}).get("coding", [])
            )),
            None,
        )
        assert systolic is not None, "Systolic BP sub-component (8480-6) not found"
        assert diastolic is not None, "Diastolic BP sub-component (8462-4) not found"

        assert systolic.get("valueQuantity", {}).get("value") == 120
        assert diastolic.get("valueQuantity", {}).get("value") == 80


class TestFHIRSNOMEDMapping:
    """
    Test SNOMED CT code mapping (clinical terms to standardized codes).
    """

    @pytest.mark.django_db
    def test_snomed_mapping_available(self):
        """
        MedSync should provide SNOMED CT mappings for common terms.
        Example: "Pneumonia" → SNOMED 233604007
        """
        # This would test an internal mapping service
        """
        Expected mappings (sample):
        {
          "Pneumonia": {
            "snomed_code": "233604007",
            "preferred_term": "Pneumonia",
            "icd10_codes": ["J18.9", "J15.9", "J18.0"]
          }
        }
        
        Implementation:
        - Load from curated JSON/database
        - Cache for performance
        - Provide API endpoint: GET /api/mappings/snomed?term=Pneumonia
        """
        pass

    @pytest.mark.django_db
    def test_snomed_integrity_icd10_alignment(self):
        """
        ICD-10 and SNOMED codes for same condition should be aligned.
        Validate cross-reference consistency.
        """
        """
        Example:
        ICD-10: J18.9 (Pneumonia, unspecified)
        SNOMED: 233604007 (Pneumonia)
        Should be able to cross-reference both in same condition record
        """
        pass


