from django.test import TestCase
from rest_framework.test import APIClient
from core.models import Hospital
from django.contrib.auth import get_user_model
from interop.models import GlobalPatient
from datetime import date

User = get_user_model()


class DemoNurseNegativeTest(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(name="Demo Hospital", region="GA", nhis_code="DEMO001")
        self.nurse = User.objects.create_user(
            email="nurse-demo@test",
            password="pass12345",
            role="nurse",
            full_name="Demo Nurse",
            hospital=self.hospital,
            account_status="active",
        )
        # Create a minimal GlobalPatient required for referral payload validation
        self.gp = GlobalPatient.objects.create(
            first_name="Demo",
            last_name="Patient",
            date_of_birth=date(1990,1,1),
            gender="male",
        )

    def test_nurse_cannot_create_referral(self):
        # Nurse should be forbidden from creating referrals
        self.client.force_authenticate(user=self.nurse)
        resp = self.client.post(
            "/api/v1/referrals",
            {
                "global_patient_id": str(self.gp.id),
                "to_facility_id": str(self.hospital.id),
                "reason": "Test referral",
            },
            format="json",
        )
        # The endpoint checks role before payload and should return 403
        self.assertEqual(resp.status_code, 403)
