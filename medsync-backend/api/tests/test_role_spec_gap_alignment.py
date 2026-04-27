from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from core.models import Hospital, SuperAdminHospitalAccess, Ward
from patients.models import Appointment, Patient, PatientAdmission

User = get_user_model()


class RoleSpecGapAlignmentTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(
            name="Spec Hospital",
            region="Greater Accra",
            nhis_code="SPEC001",
        )
        self.ward = Ward.objects.create(hospital=self.hospital, ward_name="Ward A")
        self.doctor = User.objects.create_user(
            email="doctor@spec.test",
            password="pass12345",
            role="doctor",
            full_name="Spec Doctor",
            hospital=self.hospital,
            account_status="active",
        )
        self.nurse = User.objects.create_user(
            email="nurse@spec.test",
            password="pass12345",
            role="nurse",
            full_name="Spec Nurse",
            hospital=self.hospital,
            ward=self.ward,
            account_status="active",
        )
        self.receptionist = User.objects.create_user(
            email="reception@spec.test",
            password="pass12345",
            role="receptionist",
            full_name="Spec Reception",
            hospital=self.hospital,
            account_status="active",
        )
        self.super_admin = User.objects.create_user(
            email="sa@spec.test",
            password="pass12345",
            role="super_admin",
            full_name="Spec Super Admin",
            account_status="active",
        )
        self.other_super_admin = User.objects.create_user(
            email="sa2@spec.test",
            password="pass12345",
            role="super_admin",
            full_name="Spec Super Admin 2",
            account_status="active",
        )
        self.patient = Patient.objects.create(
            ghana_health_id="GHA-SPEC-1",
            full_name="Patient One",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital,
            created_by=self.doctor,
        )
        self.second_nurse = User.objects.create_user(
            email="nurse2@spec.test",
            password="pass12345",
            role="nurse",
            full_name="Spec Nurse 2",
            hospital=self.hospital,
            ward=self.ward,
            account_status="active",
        )

    def test_dashboard_alias_route_works(self):
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn("queue_count", response.data)
        self.assertIn("pending_prescriptions", response.data)

    def test_appointments_post_route_accepts_creation(self):
        self.client.force_authenticate(user=self.receptionist)
        response = self.client.post(
            "/api/v1/appointments",
            {
                "patient_id": str(self.patient.id),
                "scheduled_at": (timezone.now() + timedelta(hours=4)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)

    def test_appointments_post_rejects_past_time(self):
        self.client.force_authenticate(user=self.receptionist)
        response = self.client.post(
            "/api/v1/appointments",
            {
                "patient_id": str(self.patient.id),
                "scheduled_at": (timezone.now() - timedelta(hours=1)).isoformat(),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_check_in_rejects_outside_two_hour_window(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=timezone.now() + timedelta(hours=6),
            appointment_type="outpatient",
            created_by=self.receptionist,
        )
        self.client.force_authenticate(user=self.receptionist)
        response = self.client.post(f"/api/v1/appointments/{appointment.id}/check-in", format="json")
        self.assertEqual(response.status_code, 400)

    def test_grant_hospital_access_endpoint(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.post(
            "/api/v1/superadmin/grant-hospital-access",
            {
                "super_admin_id": str(self.other_super_admin.id),
                "hospital_id": str(self.hospital.id),
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(
            SuperAdminHospitalAccess.objects.filter(
                super_admin=self.other_super_admin,
                hospital=self.hospital,
            ).exists()
        )

    def test_hospitals_list_includes_spec_fields(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get("/api/v1/superadmin/hospitals")
        self.assertEqual(response.status_code, 200)
        self.assertGreaterEqual(len(response.data.get("data", [])), 1)
        row = response.data["data"][0]
        self.assertIn("staff_count", row)
        self.assertIn("patient_count", row)
        self.assertIn("created_at", row)

    def test_nursing_note_handover_requires_incoming_nurse(self):
        self.client.force_authenticate(user=self.nurse)
        PatientAdmission.objects.create(
            patient=self.patient,
            ward=self.ward,
            hospital=self.hospital,
            admitted_by=self.doctor,
        )
        missing = self.client.post(
            "/api/v1/records/nursing-note",
            {
                "patient_id": str(self.patient.id),
                "content": "handover text",
                "note_type": "handover",
            },
            format="json",
        )
        self.assertEqual(missing.status_code, 400)

        invalid_incoming = self.client.post(
            "/api/v1/records/nursing-note",
            {
                "patient_id": str(self.patient.id),
                "content": "handover text",
                "note_type": "handover",
                "incoming_nurse_id": str(self.doctor.id),
            },
            format="json",
        )
        self.assertEqual(invalid_incoming.status_code, 400)

    def test_superadmin_dashboard_bundle_ok(self):
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get("/api/v1/superadmin/dashboard-bundle")
        self.assertEqual(response.status_code, 200)
        body = response.data
        self.assertIn("health", body)
        self.assertIn("services", body["health"])
        self.assertIn("ai_status", body)
        self.assertIn("hospitals", body)
        self.assertIn("compliance_alerts", body)
        self.assertIn("break_glass_summary_7d", body)


