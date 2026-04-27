"""
Tests for SOAP Encounter Draft auto-save functionality (P1 feature).

Covers:
- Draft creation and auto-save (PATCH)
- Draft retrieval (GET)
- Draft deletion (DELETE)
- Hospital scoping
- Role-based permissions
- Permission matrix enforcement
"""

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import User, Hospital, Ward
from patients.models import Patient
from records.models import Encounter, EncounterDraft


@pytest.mark.django_db
class TestEncounterDraftAutoSave(TestCase):
    """Tests for SOAP auto-save draft endpoints."""

    def setUp(self):
        """Create test data: hospitals, users, patients, encounters."""
        self.client = APIClient()

        # Create hospitals
        self.hospital_a = Hospital.objects.create(
            name="Hospital A",
            nhis_code="HOSA",
            region="Accra"
        )
        self.hospital_b = Hospital.objects.create(
            name="Hospital B",
            nhis_code="HOSB",
            region="Kumasi"
        )

        # Create ward
        self.ward = Ward.objects.create(
            hospital=self.hospital_a,
            ward_name="ICU",
            ward_type="icu"
        )

        # Create users (all roles that can create/access encounters)
        self.doctor_a = User.objects.create_user(
            email="doctor_a@test.com",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital_a,
            full_name="Dr. Alice"
        )

        self.doctor_b = User.objects.create_user(
            email="doctor_b@test.com",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital_b,
            full_name="Dr. Bob"
        )

        self.hospital_admin = User.objects.create_user(
            email="admin_a@test.com",
            password="Test123!@#",
            role="hospital_admin",
            hospital=self.hospital_a,
            full_name="Admin Alice"
        )

        self.super_admin = User.objects.create_user(
            email="super@test.com",
            password="Test123!@#",
            role="super_admin",
            full_name="Super Admin"
        )

        self.nurse = User.objects.create_user(
            email="nurse_a@test.com",
            password="Test123!@#",
            role="nurse",
            hospital=self.hospital_a,
            ward=self.ward,
            full_name="Nurse Alice"
        )

        # Create patients
        self.patient_a = Patient.objects.create(
            ghana_health_id="GHI123456A",
            full_name="Patient A",
            date_of_birth="1990-01-01",
            gender="M",
            registered_at=self.hospital_a,
            created_by=self.doctor_a
        )

        self.patient_b = Patient.objects.create(
            ghana_health_id="GHI123456B",
            full_name="Patient B",
            date_of_birth="1985-05-15",
            gender="F",
            registered_at=self.hospital_b,
            created_by=self.doctor_b
        )

        # Create encounters
        self.encounter_a = Encounter.objects.create(
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            encounter_type="consultation",
            chief_complaint="Headache"
        )

        self.encounter_b = Encounter.objects.create(
            patient=self.patient_b,
            hospital=self.hospital_b,
            created_by=self.doctor_b,
            encounter_type="consultation",
            chief_complaint="Fever"
        )

    def get_token(self, user):
        """Generate JWT token for user."""
        refresh = RefreshToken.for_user(user)
        return str(refresh.access_token)

    # ========== PATCH: AUTO-SAVE DRAFT ==========

    def test_patch_draft_creates_new_draft(self):
        """Test PATCH creates a new draft when none exists."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        payload = {
            "draft_data": {
                "subjective": "Patient reports persistent headache",
                "objective": "BP: 120/80, HR: 72",
                "assessment": "Tension headache",
                "plan": "Paracetamol 500mg TDS"
            }
        }

        response = client.patch(url, payload, format="json")
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.data}"

        data = response.data
        assert data["draft_data"]["subjective"] == "Patient reports persistent headache"
        assert data["hospital_id"] == str(self.hospital_a.id)
        assert data["patient_id"] == str(self.patient_a.id)

        # Verify draft was created in DB
        draft = EncounterDraft.objects.get(patient=self.patient_a, encounter__isnull=True)
        assert draft.draft_data["subjective"] == "Patient reports persistent headache"

    def test_patch_draft_updates_existing_draft(self):
        """Test PATCH merges with existing draft data."""
        # Create initial draft
        EncounterDraft.objects.create(
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            draft_data={
                "subjective": "Old text",
                "objective": "Old vitals"
            }
        )

        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        payload = {
            "draft_data": {
                "assessment": "New assessment"  # Only update assessment
            }
        }

        response = client.patch(url, payload, format="json")
        assert response.status_code == 200

        data = response.data
        # Verify merge: old fields preserved, new field added
        assert data["draft_data"]["subjective"] == "Old text"  # Preserved
        assert data["draft_data"]["objective"] == "Old vitals"  # Preserved
        assert data["draft_data"]["assessment"] == "New assessment"  # New

    def test_patch_draft_encounter_scoped(self):
        """Test PATCH with specific encounter creates encounter-linked draft."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/encounters/{self.encounter_a.id}/draft"
        payload = {
            "draft_data": {
                "subjective": "Encounter-specific draft"
            }
        }

        response = client.patch(url, payload, format="json")
        assert response.status_code == 200

        # Verify draft is linked to specific encounter
        draft = EncounterDraft.objects.get(encounter=self.encounter_a)
        assert draft.encounter.id == self.encounter_a.id
        assert draft.draft_data["subjective"] == "Encounter-specific draft"

    def test_patch_draft_invalid_draft_data(self):
        """Test PATCH rejects invalid draft_data."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"

        # Test non-dict draft_data
        payload = {"draft_data": "not a dict"}
        response = client.patch(url, payload, format="json")
        assert response.status_code == 400

        # Test empty draft_data
        payload = {"draft_data": {}}
        response = client.patch(url, payload, format="json")
        assert response.status_code == 400

    def test_patch_draft_hospital_scoped(self):
        """Test PATCH respects hospital scoping."""
        client = APIClient()
        token = self.get_token(self.doctor_b)  # From hospital_b
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # Try to save draft for patient_a (from hospital_a)
        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        payload = {"draft_data": {"subjective": "Unauthorized"}}

        response = client.patch(url, payload, format="json")
        assert response.status_code == 404  # Patient not accessible

    # ========== GET: RETRIEVE DRAFT ==========

    def test_get_draft_retrieves_existing_draft(self):
        """Test GET retrieves current draft."""
        draft = EncounterDraft.objects.create(
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            draft_data={"subjective": "Saved draft text"}
        )

        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.get(url)
        assert response.status_code == 200

        data = response.data
        assert data["draft_data"]["subjective"] == "Saved draft text"
        assert data["draft_id"] == str(draft.id)

    def test_get_draft_not_found(self):
        """Test GET returns 404 when no draft exists."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.get(url)
        assert response.status_code == 404

    def test_get_draft_encounter_scoped(self):
        """Test GET with specific encounter retrieves encounter draft."""
        EncounterDraft.objects.create(
            encounter=self.encounter_a,
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            draft_data={"subjective": "Encounter draft"}
        )

        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/encounters/{self.encounter_a.id}/draft"
        response = client.get(url)
        assert response.status_code == 200

        data = response.data
        assert data["draft_data"]["subjective"] == "Encounter draft"

    # ========== DELETE: CLEAR DRAFT ==========

    def test_delete_draft_removes_draft(self):
        """Test DELETE removes draft from database."""
        draft = EncounterDraft.objects.create(
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            draft_data={"subjective": "Draft to delete"}
        )

        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.delete(url)
        assert response.status_code == 204

        # Verify draft is deleted
        assert not EncounterDraft.objects.filter(id=draft.id).exists()

    def test_delete_draft_not_found(self):
        """Test DELETE returns 404 when no draft exists."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.delete(url)
        assert response.status_code == 404

    def test_delete_encounter_draft(self):
        """Test DELETE removes encounter-scoped draft."""
        draft = EncounterDraft.objects.create(
            encounter=self.encounter_a,
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            draft_data={"subjective": "To delete"}
        )

        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/encounters/{self.encounter_a.id}/draft"
        response = client.delete(url)
        assert response.status_code == 204

        assert not EncounterDraft.objects.filter(id=draft.id).exists()

    # ========== ROLE-BASED PERMISSIONS ==========

    def test_draft_permission_doctor(self):
        """Test doctor can CRUD drafts."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        # PATCH
        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.patch(url, {"draft_data": {"subjective": "Dr's draft"}}, format="json")
        assert response.status_code == 200

        # GET
        response = client.get(url)
        assert response.status_code == 200

        # DELETE
        response = client.delete(url)
        assert response.status_code == 204

    def test_draft_permission_hospital_admin(self):
        """Test hospital_admin can CRUD drafts."""
        client = APIClient()
        token = self.get_token(self.hospital_admin)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"

        # PATCH
        response = client.patch(url, {"draft_data": {"subjective": "Admin's draft"}}, format="json")
        assert response.status_code == 200

        # GET
        response = client.get(url)
        assert response.status_code == 200

    def test_draft_permission_super_admin(self):
        """Test super_admin can CRUD drafts."""
        client = APIClient()
        token = self.get_token(self.super_admin)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"

        # PATCH
        response = client.patch(url, {"draft_data": {"subjective": "Super admin's draft"}}, format="json")
        assert response.status_code == 200

        # GET
        response = client.get(url)
        assert response.status_code == 200

    def test_draft_permission_nurse_denied(self):
        """Test nurse cannot CRUD drafts (read-only access to encounters)."""
        client = APIClient()
        token = self.get_token(self.nurse)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"

        # PATCH should be denied
        response = client.patch(url, {"draft_data": {"subjective": "Nurse's draft"}}, format="json")
        assert response.status_code == 403

        # GET should also be denied (only doctors can create/save drafts)
        response = client.get(url)
        assert response.status_code == 403

    def test_draft_multi_doctor_same_patient(self):
        """Test multiple doctors from same hospital can work on same draft."""
        doctor_c = User.objects.create_user(
            email="doctor_c@test.com",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital_a,
            full_name="Dr. Charlie"
        )

        # Doctor A creates draft
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.patch(url, {"draft_data": {"subjective": "Dr A's text"}}, format="json")
        assert response.status_code == 200
        draft_id = response.data["draft_id"]

        # Doctor C can view it
        token = self.get_token(doctor_c)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        response = client.get(url)
        assert response.status_code == 200
        assert response.data["draft_id"] == draft_id

        # Doctor C can update it
        response = client.patch(url, {"draft_data": {"assessment": "Dr C's assessment"}}, format="json")
        assert response.status_code == 200
        assert response.data["draft_data"]["subjective"] == "Dr A's text"  # Preserved
        assert response.data["draft_data"]["assessment"] == "Dr C's assessment"  # New

    # ========== PERMISSION MATRIX ENFORCEMENT ==========

    @override_settings(PERMISSION_FAIL_CLOSED_UNKNOWN_ENDPOINTS=True)
    def test_draft_permission_matrix_enforced(self):
        """Test draft endpoints respect permission matrix when fail-closed is enabled."""
        # Receptionist shouldn't have access to draft endpoints
        receptionist = User.objects.create_user(
            email="receptionist@test.com",
            password="Test123!@#",
            role="receptionist",
            hospital=self.hospital_a,
            full_name="Receptionist"
        )

        client = APIClient()
        token = self.get_token(receptionist)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"

        # PATCH should be denied by permission matrix
        response = client.patch(url, {"draft_data": {"subjective": "Receptionist"}}, format="json")
        assert response.status_code == 403

    # ========== DATA INTEGRITY TESTS ==========

    def test_draft_preserves_json_structure(self):
        """Test draft_data preserves complex JSON structures."""
        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        complex_data = {
            "subjective": "Complex SOAP",
            "objective": {
                "vitals": {
                    "bp": "120/80",
                    "hr": 72,
                    "temp": 36.8
                },
                "labs": ["CBC", "BMP"]
            },
            "assessment": ["Diagnosis 1", "Diagnosis 2"],
            "plan": {
                "medications": [
                    {"drug": "Paracetamol", "dose": "500mg"},
                    {"drug": "Ibuprofen", "dose": "400mg"}
                ]
            }
        }

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.patch(url, {"draft_data": complex_data}, format="json")
        assert response.status_code == 200

        # Verify complex structure preserved
        assert response.data["draft_data"]["objective"]["vitals"]["temp"] == 36.8
        assert "CBC" in response.data["draft_data"]["objective"]["labs"]
        assert response.data["draft_data"]["plan"]["medications"][0]["dose"] == "500mg"

    def test_draft_last_saved_at_updates(self):
        """Test last_saved_at timestamp updates on each PATCH."""
        import time

        draft = EncounterDraft.objects.create(
            patient=self.patient_a,
            hospital=self.hospital_a,
            created_by=self.doctor_a,
            draft_data={"subjective": "Initial"}
        )
        first_saved = draft.last_saved_at

        time.sleep(0.1)  # Ensure timestamp differs

        client = APIClient()
        token = self.get_token(self.doctor_a)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")

        url = f"/api/v1/patients/{self.patient_a.id}/draft"
        response = client.patch(url, {"draft_data": {"assessment": "Updated"}}, format="json")
        assert response.status_code == 200

        # Verify last_saved_at was updated
        draft.refresh_from_db()
        assert draft.last_saved_at > first_saved


