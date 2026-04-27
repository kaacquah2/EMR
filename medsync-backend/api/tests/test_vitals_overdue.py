"""
Test suite for vitals overdue tracking functionality (Phase 4.4).
Tests utility functions, dashboard endpoints, and nurse access controls.
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone
from django.contrib.auth import get_user_model

from patients.models import Hospital, Ward, Patient, PatientAdmission, Bed
from records.models import MedicalRecord, Vital
from api.vitals_utils import (
    is_vitals_overdue,
    get_vitals_overdue_priority,
    is_critical_vital,
    get_latest_vital,
)

User = get_user_model()


class VitalsOverdueUtilityTests(TestCase):
    """Test the vitals_utils utility functions."""

    def setUp(self):
        """Create test data: hospital, ward, patients, users."""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TH-001",
            region="Greater Accra"
        )
        self.ward = Ward.objects.create(
            hospital=self.hospital,
            ward_name="ICU",
            ward_type="intensive_care"
        )
        self.bed = Bed.objects.create(
            ward=self.ward,
            bed_code="3A-01",
            status="occupied"
        )

        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital
        )

        self.patient = Patient.objects.create(
            full_name="John Doe",
            ghana_health_id="GHC-001",
            date_of_birth="1980-01-15",
            gender="male",
            phone="+233555555555",
            registered_at=self.hospital,
            created_by=self.doctor
        )

        # Create admission 6 hours ago (so it's overdue at 4-hour threshold)
        admission_time = timezone.now() - timedelta(hours=6)
        self.admission = PatientAdmission.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            ward=self.ward,
            bed=self.bed,
            admitted_at=admission_time,
            admitted_by=self.doctor
        )

    def test_vitals_overdue_with_no_recorded_vitals(self):
        """Test overdue detection when no vitals have been recorded."""
        is_overdue, hours_overdue = is_vitals_overdue(self.admission)

        self.assertTrue(is_overdue)
        self.assertIsNotNone(hours_overdue)
        self.assertGreaterEqual(hours_overdue, 5)  # Admitted 6 hours ago

    def test_vitals_not_overdue_within_threshold(self):
        """Test that recent vitals (2h old) are not marked as overdue (4h threshold)."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor,
            created_at=timezone.now() - timedelta(hours=2)
        )
        Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        is_overdue, hours_overdue = is_vitals_overdue(self.admission)

        self.assertFalse(is_overdue)
        self.assertIsNone(hours_overdue)

    def test_vitals_overdue_exactly_at_threshold(self):
        """Test boundary condition: vital recorded exactly 4 hours ago."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor,
            created_at=timezone.now() - timedelta(hours=4)
        )
        Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        is_overdue, hours_overdue = is_vitals_overdue(self.admission)

        # At exactly 4 hours, should still be within threshold
        self.assertFalse(is_overdue)

    def test_vitals_overdue_past_threshold(self):
        """Test that vitals older than 4 hours are marked overdue."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor,
            created_at=timezone.now() - timedelta(hours=5)
        )
        Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        is_overdue, hours_overdue = is_vitals_overdue(self.admission)

        self.assertTrue(is_overdue)
        self.assertIsNotNone(hours_overdue)
        self.assertGreaterEqual(hours_overdue, 0.5)  # At least 0.5 hours overdue

    def test_vitals_overdue_custom_threshold(self):
        """Test overdue detection with custom hours threshold."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor,
            created_at=timezone.now() - timedelta(hours=6)
        )
        Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        # With 4-hour threshold: overdue
        is_overdue, _ = is_vitals_overdue(self.admission, hours_threshold=4)
        self.assertTrue(is_overdue)

        # With 8-hour threshold: not overdue
        is_overdue, _ = is_vitals_overdue(self.admission, hours_threshold=8)
        self.assertFalse(is_overdue)

    def test_vitals_overdue_priority_critical(self):
        """Test priority classification for critically overdue vitals (>8h)."""
        priority = get_vitals_overdue_priority(hours_overdue=9.5)
        self.assertEqual(priority, "critical")

    def test_vitals_overdue_priority_high(self):
        """Test priority classification for high overdue vitals (4-8h)."""
        priority = get_vitals_overdue_priority(hours_overdue=6.0)
        self.assertEqual(priority, "high")

    def test_vitals_overdue_priority_medium(self):
        """Test priority classification for medium overdue vitals (<4h)."""
        priority = get_vitals_overdue_priority(hours_overdue=2.5)
        self.assertEqual(priority, "medium")

    def test_critical_vital_spo2_below_threshold(self):
        """Test critical vital detection: SpO2 < 88%."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor
        )
        critical_vital = Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=85,  # Below 88 threshold
            recorded_by=self.doctor
        )

        self.assertTrue(is_critical_vital(critical_vital))

    def test_critical_vital_bp_systolic_above_threshold(self):
        """Test critical vital detection: BP systolic > 180."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor
        )
        critical_vital = Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=185,  # Above 180 threshold
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        self.assertTrue(is_critical_vital(critical_vital))

    def test_critical_vital_normal_readings(self):
        """Test that normal vitals are not marked as critical."""
        record = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor
        )
        normal_vital = Vital.objects.create(
            record=record,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        self.assertFalse(is_critical_vital(normal_vital))

    def test_critical_vital_none_input(self):
        """Test that None vital is not critical."""
        self.assertFalse(is_critical_vital(None))

    def test_get_latest_vital_object(self):
        """Test retrieving the latest Vital object."""
        # Create two vitals (older and newer)
        record1 = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor,
            created_at=timezone.now() - timedelta(hours=4)
        )
        Vital.objects.create(
            record=record1,
            temperature_c=37.0,
            pulse_bpm=80,
            resp_rate=16,
            bp_systolic=120,
            bp_diastolic=80,
            spo2_percent=98,
            recorded_by=self.doctor
        )

        record2 = MedicalRecord.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            record_type="vital_signs",
            created_by=self.doctor,
            created_at=timezone.now() - timedelta(hours=2)
        )
        vital2 = Vital.objects.create(
            record=record2,
            temperature_c=37.5,
            pulse_bpm=85,
            resp_rate=17,
            bp_systolic=125,
            bp_diastolic=82,
            spo2_percent=97,
            recorded_by=self.doctor
        )

        latest = get_latest_vital(self.patient)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.id, vital2.id)
        self.assertEqual(latest.pulse_bpm, 85)


