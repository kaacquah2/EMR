"""
End-to-end tests for previously-gap features:
  - NHIS eligibility check
  - NHIS claim submission (invoice-scoped)
  - NHIS claim status polling
  - FHIR write: POST /fhir/Observation
  - FHIR write: POST /fhir/MedicationRequest
  - SMTP test endpoint
  - Dead stub route removed (billing/nhis-claim returns 404)
"""

import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from core.models import Hospital, User
from patients.models import Patient, Invoice, InvoiceItem
from records.models import MedicalRecord, Vital, Prescription


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def hospital(db):
    return Hospital.objects.create(name="Gap-Test Hospital", region="Accra", nhis_code="GT01")


@pytest.fixture
def billing_user(db, hospital):
    u = User.objects.create_user(
        email="billing@gap.test", password="Pass123!@#",
        role="billing_staff", hospital=hospital, account_status="active",
    )
    return u


@pytest.fixture
def doctor(db, hospital):
    u = User.objects.create_user(
        email="doctor@gap.test", password="Pass123!@#",
        role="doctor", hospital=hospital, account_status="active",
    )
    return u


@pytest.fixture
def hospital_admin(db, hospital):
    u = User.objects.create_user(
        email="hadmin@gap.test", password="Pass123!@#",
        role="hospital_admin", hospital=hospital, account_status="active",
    )
    return u


@pytest.fixture
def patient(db, hospital, billing_user):
    return Patient.objects.create(
        ghana_health_id="GH-GAP-0001", full_name="Gap Patient",
        date_of_birth=timezone.now().date().replace(year=1985),
        gender="female", registered_at=hospital, created_by=billing_user,
    )


@pytest.fixture
def nhis_invoice(db, hospital, patient, billing_user):
    inv = Invoice.objects.create(
        patient=patient, hospital=hospital,
        payment_method="nhis", amount_cents=15000,
        currency="GHS", status="draft", created_by=billing_user,
    )
    return inv


@pytest.fixture
def nhis_invoice_with_claim(nhis_invoice):
    nhis_invoice.nhis_claim_reference = "NHIS-TEST-ABC123"
    nhis_invoice.nhis_claim_status = "submitted"
    nhis_invoice.save()
    return nhis_invoice


def _mock_eligibility(is_eligible=True, card_status="ACTIVE"):
    from api.integrations.nhis_client import NHISEligibilityResult
    from datetime import datetime, timedelta
    return NHISEligibilityResult(
        is_eligible=is_eligible,
        member_id="NHIS-001",
        member_name="Gap Patient",
        card_status=card_status,
        card_expiry_date=datetime.now() + timedelta(days=365),
        benefit_package="BASIC",
        exemption_category=None,
        facility_contracted=True,
    )


def _mock_claim_result(ref="NHIS-MOCK-XYZ", claim_status="SUBMITTED"):
    from api.integrations.nhis_client import NHISClaimResult
    return NHISClaimResult(
        claim_reference=ref,
        status=claim_status,
        submitted_at=timezone.now(),
    )


# ─── NHIS Eligibility ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNHISEligibility:
    def test_eligible_member(self, hospital_admin):
        client = APIClient()
        client.force_authenticate(user=hospital_admin)
        with patch("api.integrations.nhis_client.NHISClient") as mock_client:
            mock_client.return_value.check_eligibility.return_value = _mock_eligibility()
            resp = client.get("/api/v1/billing/nhis/eligibility?nhis_member_id=NHIS-001")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["is_eligible"] is True
        assert data["card_status"] == "ACTIVE"
        assert data["member_name"] == "Gap Patient"

    def test_ineligible_member(self, billing_user):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        with patch("api.integrations.nhis_client.NHISClient") as mock_client:
            mock_client.return_value.check_eligibility.return_value = _mock_eligibility(
                is_eligible=False, card_status="EXPIRED"
            )
            resp = client.get("/api/v1/billing/nhis/eligibility?nhis_member_id=NHIS-EXP")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["is_eligible"] is False
        assert resp.json()["card_status"] == "EXPIRED"

    def test_missing_param(self, billing_user):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        resp = client.get("/api/v1/billing/nhis/eligibility")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_wrong_role(self, doctor):
        """Doctors cannot use the standalone eligibility check."""
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.get("/api/v1/billing/nhis/eligibility?nhis_member_id=X")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated(self):
        resp = APIClient().get("/api/v1/billing/nhis/eligibility?nhis_member_id=X")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_circuit_open_returns_503(self, billing_user):
        from api.integrations.nhis_client import NHISCircuitOpenError
        client = APIClient()
        client.force_authenticate(user=billing_user)
        with patch("api.integrations.nhis_client.NHISClient") as mock_client:
            mock_client.return_value.check_eligibility.side_effect = NHISCircuitOpenError("open")
            resp = client.get("/api/v1/billing/nhis/eligibility?nhis_member_id=X")
        assert resp.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


# ─── NHIS Claim Submission ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNHISClaimSubmit:
    def test_successful_claim_submission(self, billing_user, nhis_invoice):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        with patch("api.integrations.nhis_client.NHISClient") as mock_client:
            mock_client.return_value.check_eligibility.return_value = _mock_eligibility()
            mock_client.return_value.submit_claim.return_value = _mock_claim_result()
            resp = client.post(
                f"/api/v1/billing/invoices/{nhis_invoice.id}/submit-nhis",
                {"nhis_member_id": "NHIS-001", "diagnosis_codes": ["A09"], "check_eligibility": True},
                format="json",
            )
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert "claim_reference" in data
        assert data["nhis_status"] == "SUBMITTED"
        # Invoice should be updated
        nhis_invoice.refresh_from_db()
        assert nhis_invoice.nhis_claim_status == "submitted"
        assert nhis_invoice.nhis_claim_reference == "NHIS-MOCK-XYZ"

    def test_ineligible_patient_blocked(self, billing_user, nhis_invoice):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        with patch("api.integrations.nhis_client.NHISClient") as mock_client:
            mock_client.return_value.check_eligibility.return_value = _mock_eligibility(
                is_eligible=False, card_status="SUSPENDED"
            )
            resp = client.post(
                f"/api/v1/billing/invoices/{nhis_invoice.id}/submit-nhis",
                {"nhis_member_id": "NHIS-BAD", "diagnosis_codes": ["A09"]},
                format="json",
            )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "SUSPENDED" in resp.json()["error"]

    def test_non_nhis_invoice_rejected(self, billing_user, patient, hospital):
        cash_invoice = Invoice.objects.create(
            patient=patient, hospital=hospital,
            payment_method="cash", amount_cents=5000,
            currency="GHS", status="draft", created_by=billing_user,
        )
        client = APIClient()
        client.force_authenticate(user=billing_user)
        resp = client.post(
            f"/api/v1/billing/invoices/{cash_invoice.id}/submit-nhis",
            {"nhis_member_id": "NHIS-001", "diagnosis_codes": ["A09"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_nhis_member_id(self, billing_user, nhis_invoice):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        resp = client.post(
            f"/api/v1/billing/invoices/{nhis_invoice.id}/submit-nhis",
            {"diagnosis_codes": ["A09"]},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ─── NHIS Claim Status ────────────────────────────────────────────────────────

@pytest.mark.django_db
class TestNHISClaimStatus:
    def test_returns_live_status(self, billing_user, nhis_invoice_with_claim):
        from api.integrations.nhis_client import NHISClaimResult
        approved = NHISClaimResult(
            claim_reference="NHIS-TEST-ABC123", status="APPROVED",
            approved_amount_ghs=Decimal("120.00"),
        )
        client = APIClient()
        client.force_authenticate(user=billing_user)
        with patch("api.integrations.nhis_client.NHISClient") as mock_client:
            mock_client.return_value.get_claim_status.return_value = approved
            resp = client.get(f"/api/v1/billing/invoices/{nhis_invoice_with_claim.id}/nhis-status")
        assert resp.status_code == status.HTTP_200_OK
        data = resp.json()
        assert data["nhis_status"] == "APPROVED"
        assert data["approved_amount_ghs"] == 120.0
        assert data["is_approved"] is True
        # Invoice status should be updated
        nhis_invoice_with_claim.refresh_from_db()
        assert nhis_invoice_with_claim.nhis_claim_status == "approved"

    def test_no_claim_reference_returns_400(self, billing_user, nhis_invoice):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        resp = client.get(f"/api/v1/billing/invoices/{nhis_invoice.id}/nhis-status")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_invoice_not_found(self, billing_user):
        client = APIClient()
        client.force_authenticate(user=billing_user)
        resp = client.get("/api/v1/billing/invoices/00000000-0000-0000-0000-000000000000/nhis-status")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


# ─── Dead stub route removed ─────────────────────────────────────────────────

@pytest.mark.django_db
def test_old_nhis_stub_route_removed(billing_user):
    """billing/nhis-claim (the old stub) must no longer be accessible.
    RBAC fail-closed returns 403 for unknown endpoints; Django returns 404 if it
    were missing from the URL conf — either signals the route is dead."""
    client = APIClient()
    client.force_authenticate(user=billing_user)
    resp = client.post("/api/v1/billing/nhis-claim", {"encounter_id": "x"}, format="json")
    assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


# ─── FHIR Write: POST /fhir/Observation ─────────────────────────────────────

@pytest.mark.django_db
class TestFHIRObservationCreate:
    def _observation_payload(self, patient_id):
        return {
            "resourceType": "Observation",
            "status": "final",
            "subject": {"reference": f"Patient/{patient_id}"},
            "code": {
                "coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}]
            },
            "valueQuantity": {"value": 37.2, "unit": "Cel"},
        }

    def test_create_vital_observation(self, doctor, patient):
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.post(
            "/api/v1/fhir/Observation",
            self._observation_payload(patient.id),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["resourceType"] == "Observation"
        assert "id" in data

    def test_wrong_resource_type_rejected(self, doctor, patient):
        client = APIClient()
        client.force_authenticate(user=doctor)
        payload = self._observation_payload(patient.id)
        payload["resourceType"] = "Patient"
        resp = client.post("/api/v1/fhir/Observation", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_subject_rejected(self, doctor):
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.post(
            "/api/v1/fhir/Observation",
            {"resourceType": "Observation", "status": "final"},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_patient_returns_404(self, doctor):
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.post(
            "/api/v1/fhir/Observation",
            {"resourceType": "Observation", "status": "final",
             "subject": {"reference": "Patient/00000000-0000-0000-0000-000000000000"},
             "code": {"coding": [{"system": "http://loinc.org", "code": "8310-5"}]},
             "valueQuantity": {"value": 37.0, "unit": "Cel"}},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_no_recognized_loinc_returns_400(self, doctor, patient):
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.post(
            "/api/v1/fhir/Observation",
            {"resourceType": "Observation", "status": "final",
             "subject": {"reference": f"Patient/{patient.id}"},
             "code": {"coding": [{"system": "http://loinc.org", "code": "UNKNOWN-99"}]},
             "valueQuantity": {"value": 42.0, "unit": "x"}},
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_get_returns_list_bundle(self, doctor):
        """GET /fhir/Observation returns Bundle, not 405."""
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.get("/api/v1/fhir/Observation")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["resourceType"] == "Bundle"

    def test_unauthenticated_returns_401(self, patient):
        resp = APIClient().post(
            "/api/v1/fhir/Observation",
            {"resourceType": "Observation", "subject": {"reference": f"Patient/{patient.id}"}},
            format="json",
        )
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED


# ─── FHIR Write: POST /fhir/MedicationRequest ────────────────────────────────

@pytest.mark.django_db
class TestFHIRMedicationRequestCreate:
    def _rx_payload(self, patient_id):
        return {
            "resourceType": "MedicationRequest",
            "status": "active",
            "intent": "order",
            "subject": {"reference": f"Patient/{patient_id}"},
            "medicationCodeableConcept": {
                "coding": [{"system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                             "code": "1049502", "display": "Amoxicillin 500mg"}],
                "text": "Amoxicillin 500mg"
            },
            "dosageInstruction": [{
                "text": "500mg every 8 hours for 7 days",
                "timing": {"code": {"text": "every 8 hours"},
                           "repeat": {"boundsDuration": {"value": 7, "unit": "d"}}},
                "doseAndRate": [{"doseQuantity": {"value": 500, "unit": "mg"}}],
                "route": {"text": "oral"},
            }],
        }

    def test_create_medication_request(self, doctor, patient):
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.post(
            "/api/v1/fhir/MedicationRequest",
            self._rx_payload(patient.id),
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["resourceType"] == "MedicationRequest"
        assert "id" in data

    def test_wrong_resource_type_rejected(self, doctor, patient):
        client = APIClient()
        client.force_authenticate(user=doctor)
        payload = self._rx_payload(patient.id)
        payload["resourceType"] = "Observation"
        resp = client.post("/api/v1/fhir/MedicationRequest", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_missing_medication_name_rejected(self, doctor, patient):
        client = APIClient()
        client.force_authenticate(user=doctor)
        payload = self._rx_payload(patient.id)
        payload["medicationCodeableConcept"] = {}
        resp = client.post("/api/v1/fhir/MedicationRequest", payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_unknown_patient_returns_404(self, doctor):
        client = APIClient()
        client.force_authenticate(user=doctor)
        payload = self._rx_payload("00000000-0000-0000-0000-000000000000")
        resp = client.post("/api/v1/fhir/MedicationRequest", payload, format="json")
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_get_returns_bundle(self, doctor):
        """GET /fhir/MedicationRequest returns Bundle, not 405."""
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.get("/api/v1/fhir/MedicationRequest")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["resourceType"] == "Bundle"

    def test_nurse_cannot_create(self, hospital, patient):
        nurse = User.objects.create_user(
            email="nurse@fhir.test", password="Pass123!@#",
            role="nurse", hospital=hospital, account_status="active",
        )
        client = APIClient()
        client.force_authenticate(user=nurse)
        resp = client.post(
            "/api/v1/fhir/MedicationRequest",
            self._rx_payload(patient.id),
            format="json",
        )
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ─── SMTP test endpoint ───────────────────────────────────────────────────────

@pytest.mark.django_db
class TestSMTPTest:
    def test_sends_email_and_returns_ok(self, hospital_admin):
        from django.core import mail
        client = APIClient()
        client.force_authenticate(user=hospital_admin)
        resp = client.post("/api/v1/health/smtp-test", {"to": "test@example.com"}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json()["ok"] is True
        # Django test runner uses the locmem email backend — verify email was queued
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == ["test@example.com"]
        assert "MedSync SMTP test" in mail.outbox[0].subject

    def test_defaults_to_user_email(self, hospital_admin):
        from django.core import mail
        client = APIClient()
        client.force_authenticate(user=hospital_admin)
        resp = client.post("/api/v1/health/smtp-test", {}, format="json")
        assert resp.status_code == status.HTTP_200_OK
        assert mail.outbox[-1].to == [hospital_admin.email]

    def test_doctor_cannot_use(self, doctor):
        client = APIClient()
        client.force_authenticate(user=doctor)
        resp = client.post("/api/v1/health/smtp-test", {}, format="json")
        assert resp.status_code == status.HTTP_403_FORBIDDEN

    def test_unauthenticated_returns_401(self):
        resp = APIClient().post("/api/v1/health/smtp-test", {}, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED
