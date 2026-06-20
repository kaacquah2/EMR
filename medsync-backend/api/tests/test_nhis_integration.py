import pytest
from datetime import datetime
from django.test import TestCase
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Hospital, User
from patients.models import Patient, Invoice
from api.integrations.nhis_client import NHISClient


@pytest.mark.django_db
class TestNHISMockEligibility(TestCase):
    """Test enhanced mock eligibility client behaviors based on ID suffix."""

    def setUp(self):
        self.nhis_client = NHISClient()

    def test_mock_eligibility_expired(self):
        # Suffix '0' -> EXPIRED
        result = self.nhis_client.check_eligibility("NHIS-12345670")
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.card_status, "EXPIRED")
        self.assertEqual(result.member_name, "[MOCK] Kwame Asante")
        self.assertLess(result.card_expiry_date, datetime.now())

    def test_mock_eligibility_suspended(self):
        # Suffix '9' -> SUSPENDED
        result = self.nhis_client.check_eligibility("NHIS-12345679")
        self.assertFalse(result.is_eligible)
        self.assertEqual(result.card_status, "SUSPENDED")
        self.assertEqual(result.member_name, "[MOCK] Ama Boateng")
        self.assertGreater(result.card_expiry_date, datetime.now())

    def test_mock_eligibility_pregnant(self):
        # Suffix '5' -> PREGNANT
        result = self.nhis_client.check_eligibility("NHIS-12345675")
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.card_status, "ACTIVE")
        self.assertEqual(result.exemption_category, "PREGNANT")
        self.assertEqual(result.member_name, "[MOCK] Adwoa Mensah")
        self.assertGreater(result.card_expiry_date, datetime.now())

    def test_mock_eligibility_active_default(self):
        # Other suffix (e.g. '1') -> ACTIVE
        result = self.nhis_client.check_eligibility("NHIS-12345671")
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.card_status, "ACTIVE")
        self.assertIsNone(result.exemption_category)
        self.assertEqual(result.member_name, "[MOCK] Emmanuel Tetteh")
        self.assertGreater(result.card_expiry_date, datetime.now())

    def test_mock_eligibility_empty_id(self):
        # Graceful handling of empty member ID
        result = self.nhis_client.check_eligibility("")
        self.assertTrue(result.is_eligible)
        self.assertEqual(result.card_status, "ACTIVE")
        self.assertEqual(result.member_name, "[MOCK] Emmanuel Tetteh")


@pytest.mark.django_db
class TestNHISIntegrationStatusEndpoint(TestCase):
    """Test /nhis/status endpoint access control and response data."""

    def setUp(self):
        self.api_client = APIClient()
        self.hospital = Hospital.objects.create(name="Test Status Hospital", nhis_code="TS001")
        
        # User with billing_staff role
        self.billing_user = User.objects.create_user(
            email="billing@medsync.local",
            password="SecurePassword123!@#",
            hospital=self.hospital,
            role="billing_staff",
        )
        
        # User with clinical/doctor role
        self.doctor_user = User.objects.create_user(
            email="doctor@medsync.local",
            password="SecurePassword123!@#",
            hospital=self.hospital,
            role="doctor",
        )

    def test_billing_staff_can_access_status(self):
        refresh = RefreshToken.for_user(self.billing_user)
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        
        response = self.api_client.get("/api/v1/nhis/status")
        self.assertEqual(response.status_code, 200)
        self.assertIn("mode", response.data)
        self.assertIn("configured", response.data)
        self.assertIn("circuit_breaker", response.data)
        self.assertEqual(response.data["circuit_breaker"]["state"], "CLOSED")

    def test_doctor_cannot_access_status(self):
        refresh = RefreshToken.for_user(self.doctor_user)
        self.api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        
        response = self.api_client.get("/api/v1/nhis/status")
        self.assertEqual(response.status_code, 403)


@pytest.mark.django_db
class TestSeedNHISDemoCommand(TestCase):
    """Test seed_nhis_demo Django management command."""

    def setUp(self):
        self.hospital = Hospital.objects.create(name="Demo Hospital", nhis_code="DH001")
        self.user = User.objects.create_user(
            email="admin@demo.local",
            password="SecurePassword123!@#",
            hospital=self.hospital,
            role="hospital_admin",
        )
        
        # Create 10 patient objects
        for i in range(10):
            Patient.objects.create(
                ghana_health_id=f"GHA-{10000+i}",
                full_name=f"Patient {i}",
                date_of_birth="1990-01-01",
                gender="male",
                registered_at=self.hospital,
                created_by=self.user,
            )

    def test_command_seeds_successfully(self):
        # Call command
        call_command("seed_nhis_demo", hospital_id=str(self.hospital.id))
        
        # Verify invoices
        invoices = Invoice.objects.filter(hospital=self.hospital, payment_method="nhis")
        self.assertEqual(invoices.count(), 5)
        
        # Check specific invoice values
        first_invoice = invoices.filter(invoice_number="INV-2406-1000").first()
        self.assertIsNotNone(first_invoice)
        self.assertEqual(first_invoice.nhis_claim_status, "submitted")
        self.assertTrue(first_invoice.nhis_claim_reference.startswith("NHIS-MOCK-"))
        self.assertEqual(first_invoice.status, "pending")
        self.assertEqual(first_invoice.paid_amount, 0)
        
        # Check approved / paid invoice
        approved_invoice = invoices.filter(invoice_number="INV-2406-1001").first()
        self.assertIsNotNone(approved_invoice)
        self.assertEqual(approved_invoice.nhis_claim_status, "approved")
        self.assertEqual(approved_invoice.status, "paid")
        self.assertGreater(approved_invoice.paid_amount, 0)
        self.assertEqual(approved_invoice.paid_amount, approved_invoice.total_amount)

    def test_command_defaults_to_gac001(self):
        # Create hospital with nhis_code="GAC-001"
        gac_hospital = Hospital.objects.create(name="Korle Bu Hospital", nhis_code="GAC-001")
        # Create a patient for this hospital
        Patient.objects.create(
            ghana_health_id="GHA-GAC001-PAT",
            full_name="GAC Patient",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=gac_hospital,
            created_by=self.user,
        )
        
        # Call command without hospital_id
        call_command("seed_nhis_demo")
        
        # Verify invoices
        invoices = Invoice.objects.filter(hospital=gac_hospital, payment_method="nhis")
        self.assertEqual(invoices.count(), 1)
