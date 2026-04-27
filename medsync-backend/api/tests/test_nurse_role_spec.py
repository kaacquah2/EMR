from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from core.models import Hospital, Ward
from patients.models import Patient, PatientAdmission, ClinicalAlert
from records.models import MedicalRecord, Prescription, NursingNote

User = get_user_model()


class NurseRoleSpecTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(name="Spec Hospital", region="GA", nhis_code="NS001")
        self.ward_a = Ward.objects.create(hospital=self.hospital, ward_name="Ward A")
        self.ward_b = Ward.objects.create(hospital=self.hospital, ward_name="Ward B")
        self.doctor = User.objects.create_user(
            email="doctor@nurse-spec.test",
            password="pass12345",
            role="doctor",
            full_name="Doctor",
            hospital=self.hospital,
            account_status="active",
        )
        self.nurse_a = User.objects.create_user(
            email="nurse-a@nurse-spec.test",
            password="pass12345",
            role="nurse",
            full_name="Nurse A",
            hospital=self.hospital,
            ward=self.ward_a,
            account_status="active",
        )
        self.nurse_b = User.objects.create_user(
            email="nurse-b@nurse-spec.test",
            password="pass12345",
            role="nurse",
            full_name="Nurse B",
            hospital=self.hospital,
            ward=self.ward_b,
            account_status="active",
        )
        self.patient_a = Patient.objects.create(
            ghana_health_id="NURSE-A-001",
            full_name="Patient A",
            date_of_birth="1991-01-01",
            gender="male",
            registered_at=self.hospital,
            created_by=self.doctor,
        )
        self.patient_b = Patient.objects.create(
            ghana_health_id="NURSE-B-001",
            full_name="Patient B",
            date_of_birth="1992-01-01",
            gender="female",
            registered_at=self.hospital,
            created_by=self.doctor,
        )
        PatientAdmission.objects.create(
            patient=self.patient_a,
            ward=self.ward_a,
            hospital=self.hospital,
            admitted_by=self.doctor,
        )
        PatientAdmission.objects.create(
            patient=self.patient_b,
            ward=self.ward_b,
            hospital=self.hospital,
            admitted_by=self.doctor,
        )

    def test_nurse_dashboard_is_ward_scoped(self):
        self.client.force_authenticate(user=self.nurse_a)
        resp = self.client.get("/api/v1/nurse/dashboard")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["admitted_count"], 1)
        self.assertEqual(str(resp.data["ward_id"]), str(self.ward_a.id))

    def test_nurse_cannot_read_other_ward_patient(self):
        self.client.force_authenticate(user=self.nurse_a)
        resp = self.client.get(f"/api/v1/patients/{self.patient_b.id}")
        self.assertEqual(resp.status_code, 404)

    def test_nurse_diagnosis_endpoint_allowed(self):
        self.client.force_authenticate(user=self.nurse_a)
        resp = self.client.get(f"/api/v1/patients/{self.patient_a.id}/diagnoses")
        self.assertEqual(resp.status_code, 200)

    def test_critical_vitals_confirmed_audit_flow(self):
        self.client.force_authenticate(user=self.nurse_a)
        resp = self.client.post(
            "/api/v1/records/vitals",
            {
                "patient_id": str(self.patient_a.id),
                "spo2_percent": 82,
                "critical_action_confirmed": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, 201)
        record_id = resp.data["record_id"]
        self.assertTrue(
            ClinicalAlert.objects.filter(
                patient=self.patient_a,
                resource_id=record_id,
                status="active",
            ).exists()
        )

    def test_nurse_handover_acknowledge_requires_incoming(self):
        self.client.force_authenticate(user=self.nurse_a)
        record = MedicalRecord.objects.create(
            patient=self.patient_a,
            hospital=self.hospital,
            record_type="nursing_note",
            created_by=self.nurse_a,
        )
        note = NursingNote.objects.create(
            record=record,
            content="SBAR content",
            note_type="handover",
            incoming_nurse=self.nurse_b,
        )
        forbidden = self.client.post(f"/api/v1/nurse/handover/{note.id}/acknowledge", format="json")
        self.assertEqual(forbidden.status_code, 404)
        self.client.force_authenticate(user=self.nurse_b)
        ok = self.client.post(f"/api/v1/nurse/handover/{note.id}/acknowledge", format="json")
        self.assertEqual(ok.status_code, 200)
        note.refresh_from_db()
        self.assertIsNotNone(note.acknowledged_at)

    def test_nurse_dispense_restricted_to_ward(self):
        record_a = MedicalRecord.objects.create(
            patient=self.patient_a,
            hospital=self.hospital,
            record_type="prescription",
            created_by=self.doctor,
        )
        Prescription.objects.create(
            record=record_a,
            drug_name="Metformin",
            dosage="500mg",
            frequency="daily",
            route="oral",
        )
        record_b = MedicalRecord.objects.create(
            patient=self.patient_b,
            hospital=self.hospital,
            record_type="prescription",
            created_by=self.doctor,
        )
        Prescription.objects.create(
            record=record_b,
            drug_name="Amlodipine",
            dosage="10mg",
            frequency="daily",
            route="oral",
        )
        self.client.force_authenticate(user=self.nurse_a)
        ok = self.client.post(f"/api/v1/records/prescription/{record_a.id}/dispense-by-nurse", format="json")
        self.assertEqual(ok.status_code, 200)
        forbidden = self.client.post(f"/api/v1/records/prescription/{record_b.id}/dispense-by-nurse", format="json")
        self.assertEqual(forbidden.status_code, 403)


