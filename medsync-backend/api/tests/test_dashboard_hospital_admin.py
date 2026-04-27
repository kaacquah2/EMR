"""Hospital admin dashboard metrics payload shape."""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Hospital
from patients.models import Patient

User = get_user_model()


class HospitalAdminDashboardMetricsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(
            name="HA Dash Hospital",
            region="Greater Accra",
            nhis_code="HADASH01",
        )
        self.ha = User.objects.create_user(
            email="ha@dash.test",
            password="pass12345",
            role="hospital_admin",
            full_name="Hospital Admin",
            hospital=self.hospital,
            account_status="active",
        )
        self.staff = User.objects.create_user(
            email="doc@dash.test",
            password="pass12345",
            role="doctor",
            full_name="Staff Doc",
            hospital=self.hospital,
            account_status="active",
        )
        Patient.objects.create(
            ghana_health_id="GHA-DASH-1",
            full_name="P One",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital,
            created_by=self.staff,
        )
        User.objects.create_user(
            email="pending@dash.test",
            password="pass12345",
            role="nurse",
            full_name="Pending Nurse",
            hospital=self.hospital,
            account_status="pending",
        )

    def test_metrics_contains_expected_keys(self):
        self.client.force_authenticate(user=self.ha)
        response = self.client.get("/api/v1/dashboard/metrics")
        self.assertEqual(response.status_code, 200)
        data = response.data
        for key in (
            "total_patients",
            "total_users",
            "total_active",
            "pending_invite_count",
            "encounters_today",
            "encounters_in_consultation",
            "admission_count",
            "beds_available",
            "locked_accounts_count",
            "recent_audit_events",
            "pending_invitations_list",
            "appointment_summary",
        ):
            self.assertIn(key, data, msg=f"missing {key}")
        self.assertEqual(data["total_patients"], 1)
        self.assertEqual(data["total_users"], 1)
        self.assertGreaterEqual(len(data["pending_invitations_list"]), 1)

    def test_pending_invitation_without_expiry_included(self):
        User.objects.create_user(
            email="nopexpire@dash.test",
            password="pass12345",
            role="receptionist",
            full_name="No Expiry",
            hospital=self.hospital,
            account_status="pending",
        )
        self.client.force_authenticate(user=self.ha)
        response = self.client.get("/api/v1/dashboard/metrics")
        self.assertEqual(response.status_code, 200)
        emails = {row["email"] for row in response.data["pending_invitations_list"]}
        self.assertIn("nopexpire@dash.test", emails)


