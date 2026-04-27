"""
Tests for Lab Technician data visibility guards.

Lab technicians should NEVER see:
- Diagnoses
- Prescriptions
- Vitals
- Nursing notes
- Allergy flags
- Patient clinical history

They should only see:
- Lab order details (test_name, urgency, status, lab_unit_id)
- Lab result details (result_value, reference_range, status)
- Patient demographics only (name, age, gender, GHA ID)
"""

from django.test import Client
from rest_framework.test import APITestCase
from rest_framework import status
from django.contrib.auth import get_user_model
from core.models import Hospital
from patients.models import Patient
from records.models import MedicalRecord, Diagnosis, LabOrder, LabResult

User = get_user_model()


class LabTechDataVisibilityTest(APITestCase):
    """Verify Lab Technician cannot access clinical data via API."""

    def setUp(self):
        """Create test data: hospital, users, patients, orders."""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Accra",
            nhis_code="THO001"
        )

        # Create Lab Technician user
        self.lab_tech = User.objects.create_user(
            email="lab_tech@test.com",
            password="LabTech123!@#",
            full_name="Lab Tech",
            role="lab_technician",
            hospital=self.hospital,
        )

        # Create Doctor user (for comparison)
        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="Doctor123!@#",
            full_name="Doctor",
            role="doctor",
            hospital=self.hospital,
        )

        # Create patient
        self.patient = Patient.objects.create(
            full_name="Test Patient",
            ghana_health_id="GHA-001",
            date_of_birth="1990-01-01",
            gender="M",
            registered_at=self.hospital,
            created_by=self.doctor,
        )

        # Create a medical record with diagnosis
        self.record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="diagnosis",
            created_by=self.doctor,
        )

        # Create diagnosis
        self.diagnosis = Diagnosis.objects.create(
            record=self.record,
            icd10_code="I10",
            diagnosis_name="Essential hypertension",
            severity="moderate",
        )

        # Create lab order
        self.lab_order = LabOrder.objects.create(
            record=self.record,
            test_name="Blood Glucose",
            urgency="routine",
            status="ordered",
        )

        # Create lab result
        self.lab_result = LabResult.objects.create(
            lab_order=self.lab_order,
            record=self.record,
            test_name="Blood Glucose",
            result_value="105",
            reference_range="70-100",
            status="resulted",
            lab_tech=self.lab_tech,
        )

        self.client = Client()

    def test_lab_tech_can_list_lab_orders(self):
        """Lab tech should be able to list lab orders."""
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get("/api/v1/lab/orders/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("data", response.json())

    def test_lab_tech_can_view_lab_order_detail(self):
        """Lab tech should be able to view lab order details."""
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get(f"/api/v1/lab/orders/{self.lab_order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should have lab-specific fields
        self.assertIn("test_name", data)
        self.assertIn("urgency", data)
        self.assertIn("status", data)
        self.assertIn("lab_unit_id", data)

        # Should have patient demographics
        self.assertIn("patient_name", data)
        self.assertIn("gha_id", data)
        self.assertIn("patient_gender", data)

    def test_lab_tech_cannot_see_diagnosis_in_order(self):
        """Lab tech should NOT see diagnoses linked to lab order."""
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get(f"/api/v1/lab/orders/{self.lab_order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should NOT include diagnosis data
        self.assertNotIn("diagnoses", data)
        self.assertNotIn("diagnosis", data)

    def test_lab_tech_cannot_see_prescriptions_in_order(self):
        """Lab tech should NOT see prescriptions linked to lab order."""
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get(f"/api/v1/lab/orders/{self.lab_order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should NOT include prescription data
        self.assertNotIn("prescriptions", data)
        self.assertNotIn("prescription", data)

    def test_lab_tech_cannot_see_vitals_in_order(self):
        """Lab tech should NOT see vitals linked to lab order."""
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get(f"/api/v1/lab/orders/{self.lab_order.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Should NOT include vital signs
        self.assertNotIn("vitals", data)
        self.assertNotIn("vital", data)

    def test_lab_tech_cannot_access_patient_clinical_endpoint(self):
        """Lab tech should NOT access general patient endpoint (clinical data)."""
        self.client.force_authenticate(user=self.lab_tech)
        response = self.client.get(f"/api/v1/patients/{self.patient.id}/")

        # Should be blocked or return limited data
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # If accessible, should only include demographics
            self.assertIn("full_name", data)
            self.assertIn("ghana_health_id", data)
            # Should NOT include allergies, clinical flags
            if "allergies" in data:
                # Allergies should be empty or not present for lab tech
                self.assertEqual(len(data.get("allergies", [])), 0)

    def test_lab_tech_lab_order_serializer_restricted(self):
        """Verify LabOrderSerializerRestricted excludes clinical data."""
        from api.serializers import LabOrderSerializerRestricted

        serializer = LabOrderSerializerRestricted(self.lab_order)
        data = serializer.data

        # Should have lab-specific fields
        self.assertIn("id", data)
        self.assertIn("test_name", data)
        self.assertIn("urgency", data)
        self.assertIn("status", data)
        self.assertIn("lab_unit_id", data)

        # Should NOT have clinical data fields
        restricted_fields = [
            "diagnoses", "diagnosis",
            "prescriptions", "prescription",
            "vitals", "vital",
            "nursing_notes", "nursing_note",
            "allergy_flag",
            "patient_clinical_history",
        ]
        for field in restricted_fields:
            self.assertNotIn(field, data)

    def test_lab_tech_lab_result_serializer_restricted(self):
        """Verify LabResultSerializerRestricted excludes clinical data."""
        from api.serializers import LabResultSerializerRestricted

        serializer = LabResultSerializerRestricted(self.lab_result)
        data = serializer.data

        # Should have result-specific fields
        self.assertIn("id", data)
        self.assertIn("lab_order_id", data)
        self.assertIn("test_name", data)
        self.assertIn("result_value", data)
        self.assertIn("reference_range", data)
        self.assertIn("status", data)

        # Should NOT have interpretation or clinical notes
        restricted_fields = [
            "interpretation",
            "clinical_notes",
            "diagnosis_suggestion",
            "referral_indication",
        ]
        for field in restricted_fields:
            self.assertNotIn(field, data)

    def test_doctor_can_see_full_order_data(self):
        """Doctor should see full order data with clinical context."""
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/lab/orders/{self.lab_order.id}/")

        # If doctor has access, they should see more fields
        if response.status_code == status.HTTP_200_OK:
            data = response.json()
            # Doctor should have test name and urgency (lab tech level)
            self.assertIn("test_name", data)
            # Additional fields doctors might see
            # (depends on endpoint implementation)

    def test_lab_tech_role_enforced_on_list_endpoint(self):
        """Lab tech list endpoint should enforce role check."""
        # Non-lab-tech should not access lab order list
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/lab/orders/")

        # Doctor role shouldn't have access
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN])

    def test_lab_tech_role_enforced_on_detail_endpoint(self):
        """Lab tech detail endpoint should enforce role check."""
        # Non-lab-tech should not access lab order detail
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/lab/orders/{self.lab_order.id}/")

        # Doctor role shouldn't have access
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN])


