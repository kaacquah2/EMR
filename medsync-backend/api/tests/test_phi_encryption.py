from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase

from core.models import Hospital
from patients.models import Allergy, Patient

User = get_user_model()


class TestPHIFieldEncryption(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Encryption Test Hospital",
            region="Greater Accra",
            nhis_code="ENC001",
        )
        self.user = User.objects.create_user(
            email="enc-test@medsync.local",
            password="testpass123",
            role="doctor",
            full_name="Encryption Tester",
            hospital=self.hospital,
            account_status="active",
        )

    def test_national_id_is_not_stored_as_plaintext(self):
        patient = Patient.objects.create(
            ghana_health_id="GH-ENC-001",
            full_name="Encrypted Patient",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital,
            created_by=self.user,
            national_id="GHA-1234567890",
        )

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT national_id FROM patients_patient WHERE id = %s",
                [str(patient.id)],
            )
            raw_value = cursor.fetchone()[0]

        self.assertNotEqual(
            str(raw_value),
            "GHA-1234567890",
            "national_id is stored as plaintext",
        )

    def test_encrypted_fields_decrypt_correctly_via_orm(self):
        patient = Patient.objects.create(
            ghana_health_id="GH-ENC-002",
            full_name="Encrypted Patient 2",
            date_of_birth="1992-02-02",
            gender="female",
            registered_at=self.hospital,
            created_by=self.user,
            national_id="GHA-0987654321",
            nhis_number="NHIS-111",
            phone="+233201234567",
        )
        Allergy.objects.create(
            patient=patient,
            allergen="Penicillin",
            reaction_type="Anaphylaxis",
            severity="severe",
            recorded_by=self.user,
        )

        fetched = Patient.objects.get(id=patient.id)
        fetched_allergy = Allergy.objects.get(patient=patient)
        self.assertEqual(fetched.national_id, "GHA-0987654321")
        self.assertEqual(fetched.nhis_number, "NHIS-111")
        self.assertEqual(fetched.phone, "+233201234567")
        self.assertEqual(fetched_allergy.allergen, "Penicillin")
        self.assertEqual(fetched_allergy.reaction_type, "Anaphylaxis")


