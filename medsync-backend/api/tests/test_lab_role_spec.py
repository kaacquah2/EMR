from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Hospital, LabUnit
from patients.models import Patient
from records.models import LabOrder, MedicalRecord

User = get_user_model()


class LabRoleSpecTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(
            name="Lab Spec Hospital",
            region="Greater Accra",
            nhis_code="LABSPEC01",
        )
        self.lab_unit = LabUnit.objects.create(hospital=self.hospital, name="Hematology")
        self.doctor = User.objects.create_user(
            email="doc@labspec.test",
            password="pass12345",
            role="doctor",
            full_name="Dr Lab",
            hospital=self.hospital,
            account_status="active",
        )
        self.lab_tech = User.objects.create_user(
            email="lab@labspec.test",
            password="pass12345",
            role="lab_technician",
            full_name="Lab Tech",
            hospital=self.hospital,
            lab_unit=self.lab_unit,
            account_status="active",
        )
        self.patient = Patient.objects.create(
            ghana_health_id="GHA-LAB-001",
            full_name="Lab Patient",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital,
            created_by=self.doctor,
        )
        self.record = MedicalRecord(
            patient=self.patient,
            hospital=self.hospital,
            record_type="lab_result",
            created_by=self.doctor,
        )
        # Existing model save() expects pk to be absent on first insert.
        self.record.id = None
        self.record.save()
        self.order = LabOrder.objects.create(
            record=self.record,
            test_name="Full Blood Count",
            urgency="stat",
            lab_unit=self.lab_unit,
            status="ordered",
        )

    def test_lab_orders_excludes_clinical_fields(self):
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get("/api/v1/lab/orders")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["data"])
        row = response.data["data"][0]
        self.assertIn("patient_name", row)
        self.assertIn("gha_id", row)
        self.assertNotIn("diagnosis", row)
        self.assertNotIn("prescription", row)
        self.assertNotIn("nursing_note", row)

    def test_status_transition_flow_enforced(self):
        self.client.force_authenticate(user=self.lab_tech)
        order_id = str(self.order.id)

        bad = self.client.patch(
            f"/api/v1/lab/orders/{order_id}",
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(bad.status_code, 400)

        collected = self.client.patch(
            f"/api/v1/lab/orders/{order_id}",
            {"status": "collected"},
            format="json",
        )
        self.assertEqual(collected.status_code, 200)
        self.assertEqual(collected.data["status"], "collected")

        in_progress = self.client.patch(
            f"/api/v1/lab/orders/{order_id}",
            {"status": "in_progress"},
            format="json",
        )
        self.assertEqual(in_progress.status_code, 200)
        self.assertEqual(in_progress.data["status"], "in_progress")

        result = self.client.post(
            f"/api/v1/lab/orders/{order_id}/result",
            {"result_value": "11.5 g/dL", "reference_range": "13.5-17.5"},
            format="json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.data["status"], "resulted")

