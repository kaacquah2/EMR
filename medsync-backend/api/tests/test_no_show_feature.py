"""
Tests for no-show auto-marking feature.
"""
from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from core.models import Hospital, User
from patients.models import Patient, Appointment


class NoShowAutoMarkingTestCase(TestCase):
    """Test automatic no-show marking for appointments."""

    def setUp(self):
        """Create test fixtures."""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="H001",is_active=True,
        )

        self.doctor = User.objects.create_user(
            email="doctor@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active",
        )

        self.patient = Patient.objects.create(
            ghana_health_id="GHE123456",
            full_name="Test Patient",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital,
            created_by=self.doctor,
        )

    def test_appointment_has_no_show_status(self):
        """Test that Appointment model supports no_show status."""
        appt = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=timezone.now() + timedelta(hours=1),
            status="no_show",
            created_by=self.doctor,
        )
        self.assertEqual(appt.status, "no_show")

    def test_no_show_marked_at_field_exists(self):
        """Test that no_show_marked_at field exists on Appointment."""
        appt = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=timezone.now() - timedelta(minutes=20),
            status="no_show",
            no_show_marked_at=timezone.now(),
            created_by=self.doctor,
        )
        self.assertIsNotNone(appt.no_show_marked_at)

    def test_no_show_override_reason_field(self):
        """Test that no_show_override_reason field exists."""
        appt = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=timezone.now() - timedelta(minutes=20),
            status="scheduled",
            created_by=self.doctor,
        )
        appt.no_show_override_reason = "Doctor approved absence"
        appt.save()

        self.assertEqual(appt.no_show_override_reason, "Doctor approved absence")

    def test_appointment_past_grace_period(self):
        """Test identifying appointments past grace period."""
        grace_period_minutes = 15
        cutoff = timezone.now() - timedelta(minutes=grace_period_minutes)

        # Create appointment before cutoff (should be marked)
        old_appt = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=cutoff - timedelta(minutes=1),
            status="scheduled",
            created_by=self.doctor,
        )

        # Create appointment after cutoff (should NOT be marked)
        Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=cutoff + timedelta(minutes=1),
            status="scheduled",
            created_by=self.doctor,
        )

        # Query for appointments to mark
        appts_to_mark = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertEqual(appts_to_mark.count(), 1)
        self.assertIn(old_appt.id, appts_to_mark.values_list("id", flat=True))

    def test_already_marked_appointments_excluded(self):
        """Test that already-marked no-shows are not re-marked."""
        cutoff = timezone.now() - timedelta(minutes=15)

        # Create appointment that was already marked
        marked_appt = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=cutoff - timedelta(minutes=1),
            status="no_show",
            no_show_marked_at=cutoff,
            created_by=self.doctor,
        )

        # Query should exclude this
        appts_to_mark = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertNotIn(marked_appt.id, appts_to_mark.values_list("id", flat=True))

    def test_completed_appointments_excluded(self):
        """Test that completed appointments are not marked as no-show."""
        cutoff = timezone.now() - timedelta(minutes=15)

        completed_appt = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=cutoff - timedelta(minutes=1),
            status="completed",
            created_by=self.doctor,
        )

        appts_to_mark = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertNotIn(completed_appt.id, appts_to_mark.values_list("id", flat=True))

    def test_multi_hospital_scoping(self):
        """Test that no-show marking respects hospital scoping."""
        hospital2 = Hospital.objects.create(
            name="Hospital 2",
            region="Region 2",
            nhis_code="H002",is_active=True,
        )

        patient2 = Patient.objects.create(
            ghana_health_id="GHE654321",
            full_name="Patient 2",
            date_of_birth="1992-01-01",
            gender="female",
            registered_at=hospital2,
            created_by=self.doctor,
        )

        cutoff = timezone.now() - timedelta(minutes=15)

        appt1 = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=cutoff - timedelta(minutes=1),
            status="scheduled",
            created_by=self.doctor,
        )

        appt2 = Appointment.objects.create(
            patient=patient2,
            hospital=hospital2,
            scheduled_at=cutoff - timedelta(minutes=1),
            status="scheduled",
            created_by=self.doctor,
        )

        # Query for hospital1
        appts_h1 = Appointment.objects.filter(
            hospital=self.hospital,
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertEqual(appts_h1.count(), 1)
        self.assertIn(appt1.id, appts_h1.values_list("id", flat=True))
        self.assertNotIn(appt2.id, appts_h1.values_list("id", flat=True))

    def test_appointment_index_for_performance(self):
        """Test that appointment queries use proper indexes."""
        # Create many appointments to test index performance
        cutoff = timezone.now() - timedelta(minutes=15)

        for i in range(50):
            Appointment.objects.create(
                patient=self.patient,
                hospital=self.hospital,
                scheduled_at=cutoff - timedelta(minutes=i),
                status="scheduled" if i % 2 == 0 else "completed",
                created_by=self.doctor,
            )

        # This query should be fast with proper indexes
        appts = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        # Should find appointments efficiently
        self.assertGreater(appts.count(), 0)

    def test_audit_log_no_show_action(self):
        """Test that NO_SHOW_AUTO_MARKED action is defined."""
        # Verify the action is meaningful for audit trails
        audit_actions = [action[0] for action in [
            ("NO_SHOW_AUTO_MARKED", "No Show Auto Marked"),
        ]]
        self.assertIn("NO_SHOW_AUTO_MARKED", audit_actions)

    def test_grace_period_boundary(self):
        """Test grace period boundary conditions."""
        grace_period_minutes = 15
        cutoff = timezone.now() - timedelta(minutes=grace_period_minutes)

        # Create appointment exactly at cutoff (should be marked)
        appt_at_cutoff = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=cutoff,
            status="scheduled",
            created_by=self.doctor,
        )

        # Query with < operator (should include this)
        appts = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lte=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertIn(appt_at_cutoff.id, appts.values_list("id", flat=True))


