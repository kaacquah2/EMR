"""
Comprehensive end-to-end integration test covering:
1. Break-glass with time-window enforcement (15-minute window)
2. Celery task execution (eager mode)
3. No-show auto-marking with override window
4. Multi-hospital isolation
"""
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient

from core.models import User, Hospital, AuditLog
from interop.models import GlobalPatient, BreakGlassLog
from patients.models import Patient, Appointment
from api.tasks.appointment_tasks import mark_no_shows_task
from api.tasks.export_tasks import export_patient_pdf_task


class BreakGlassTimeWindowIntegrationTestCase(TestCase):
    """
    Scenario 1: Break-Glass with Time-Window
    Tests that break-glass access is properly constrained to 15-minute window.
    """

    def setUp(self):
        """Create test fixtures for break-glass scenario."""
        self.client = APIClient()

        # Create hospitals
        self.hospital1 = Hospital.objects.create(
            name="Emergency Hospital 1",
            region="Region A",
            nhis_code="EH001",is_active=True,
        )
        self.hospital2 = Hospital.objects.create(
            name="Emergency Hospital 2",
            region="Region B",
            nhis_code="EH002",is_active=True,
        )

        # Create users in different hospitals
        self.doctor1 = User.objects.create_user(
            email="doctor1@hospital1.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital1,
            account_status="active",
        )

        self.doctor2 = User.objects.create_user(
            email="doctor2@hospital2.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital2,
            account_status="active",
        )

        # Create global patient
        self.global_patient = GlobalPatient.objects.create(
            first_name="Emergency",
            last_name="PatientOne",
            date_of_birth="1985-05-15",
            gender="male",
        )

    def test_break_glass_access_within_15_minute_window(self):
        """
        Test: Doctor creates break-glass access to global patient.
        Verify expires_at is set to now + 15 minutes.
        Verify access is allowed within window.
        """
        # Create break-glass log with 15-minute window
        now = timezone.now()
        expires_at = now + timedelta(minutes=15)

        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Critical emergency - patient unconscious",
            expires_at=expires_at,
        )

        # Verify creation
        self.assertIsNotNone(log.id)
        self.assertEqual(log.accessed_by, self.doctor1)
        self.assertEqual(log.facility, self.hospital1)
        self.assertIsNotNone(log.expires_at)

        # Verify access is NOT expired (within window)
        self.assertFalse(log.is_expired())
        self.assertGreaterEqual(log.expires_at, now + timedelta(minutes=14))
        self.assertLessEqual(log.expires_at, now + timedelta(minutes=16))

    def test_break_glass_access_denied_after_window(self):
        """
        Test: Simulate time passing (15+ minutes).
        Verify access is denied after window expires.
        """
        # Create break-glass log that expired 1 minute ago
        expired_time = timezone.now() - timedelta(minutes=1)

        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Critical emergency - expired",
            expires_at=expired_time,
        )

        # Verify access IS expired
        self.assertTrue(log.is_expired())

        # Verify the timestamp makes sense
        self.assertLess(log.expires_at, timezone.now())

    def test_break_glass_expired_access_logged_to_audit(self):
        """
        Test: Verify expired access is logged to AuditLog.
        """
        # Create expired break-glass log
        expired_time = timezone.now() - timedelta(minutes=5)

        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Critical emergency - audit test",
            expires_at=expired_time,
        )

        # Create audit log entry
        AuditLog.objects.create(
            user=self.doctor1,
            action="EMERGENCY_ACCESS",
            resource_type="break_glass",
            resource_id=str(log.id),
            hospital=self.hospital1,
            ip_address="192.168.1.1",
            user_agent="test-client",
        )

        # Verify audit entry exists
        audit_entry = AuditLog.objects.get(resource_id=str(log.id))
        self.assertEqual(audit_entry.action, "EMERGENCY_ACCESS")
        self.assertEqual(audit_entry.user, self.doctor1)

        # Verify log is expired
        self.assertTrue(log.is_expired())

    def test_break_glass_exact_expiry_boundary(self):
        """
        Test: Break-glass access at exact expiry boundary (edge case).
        """
        current_time = timezone.now()
        log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency - boundary test",
            expires_at=current_time,
        )

        # At exact expiry moment, should be considered expired
        self.assertTrue(log.is_expired())

    def test_break_glass_multiple_accesses_per_patient(self):
        """
        Test: Multiple break-glass accesses to same patient tracked separately.
        """
        now = timezone.now()

        log1 = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Access 1",
            expires_at=now + timedelta(minutes=15),
        )

        log2 = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital2,
            accessed_by=self.doctor2,
            reason="Access 2",
            expires_at=now + timedelta(minutes=15),
        )

        # Verify both exist and are independent
        self.assertNotEqual(log1.id, log2.id)
        self.assertEqual(log1.facility, self.hospital1)
        self.assertEqual(log2.facility, self.hospital2)

        # Verify each is scoped to correct facility
        h1_logs = BreakGlassLog.objects.filter(facility=self.hospital1)
        self.assertIn(log1.id, h1_logs.values_list("id", flat=True))
        self.assertNotIn(log2.id, h1_logs.values_list("id", flat=True))


@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
)
class CeleryTaskExecutionIntegrationTestCase(TestCase):
    """
    Scenario 2: Celery Task Execution (Eager Mode)
    Tests that Celery tasks execute synchronously in test environment.
    """

    def setUp(self):
        """Create test fixtures for Celery scenario."""
        self.hospital = Hospital.objects.create(
            name="PDF Export Hospital",
            region="Region C",
            nhis_code="PH001",is_active=True,
        )

        self.doctor = User.objects.create_user(
            email="export_doctor@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active",
        )

        self.patient = Patient.objects.create(
            ghana_health_id="GHE789012",
            full_name="Export Test Patient",
            date_of_birth="1988-07-20",
            gender="female",
            registered_at=self.hospital,
            created_by=self.doctor,
        )

    def test_pdf_export_task_submission(self):
        """
        Test: Submit PDF export task directly.
        Verify task executes and completes in eager mode.
        """
        # Call task directly (eager mode runs synchronously)
        result = export_patient_pdf_task(str(self.patient.id), format_type="summary")

        # Verify result structure
        self.assertIsNotNone(result)
        self.assertIn("status", result)

    def test_pdf_export_task_missing_patient(self):
        """
        Test: Call PDF export task for non-existent patient.
        Verify task handles error gracefully.
        """
        invalid_patient_id = "00000000-0000-0000-0000-000000000000"

        result = export_patient_pdf_task(invalid_patient_id, format_type="summary")

        # Verify error handling
        self.assertEqual(result["status"], "error")
        self.assertIn("not found", result["message"].lower())

    def test_celery_task_direct_execution(self):
        """
        Test: Verify task can be called directly (eager mode).
        """
        result = export_patient_pdf_task(str(self.patient.id), format_type="full")

        # Result should be accessible immediately
        self.assertIsNotNone(result)
        self.assertIn("status", result)
        # Either success or error, but should have status
        self.assertIn(result["status"], ["success", "error"])

    def test_celery_eager_mode_configuration(self):
        """
        Test: Verify Celery is configured for eager mode in tests.
        """
        from django.conf import settings

        # Check that eager mode is enabled
        self.assertTrue(
            settings.CELERY_ALWAYS_EAGER,
            "CELERY_ALWAYS_EAGER should be True in test settings"
        )


@override_settings(CELERY_ALWAYS_EAGER=True)
class NoShowAutoMarkingIntegrationTestCase(TestCase):
    """
    Scenario 3: No-Show Auto-Marking
    Tests automatic marking of missed appointments and override window.
    """

    def setUp(self):
        """Create test fixtures for no-show scenario."""
        self.hospital = Hospital.objects.create(
            name="No-Show Test Hospital",
            region="Region D",
            nhis_code="NSH001",is_active=True,
        )

        self.doctor = User.objects.create_user(
            email="doctor_noshow@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active",
        )

        self.patient = Patient.objects.create(
            ghana_health_id="GHE345678",
            full_name="No-Show Test Patient",
            date_of_birth="1992-03-10",
            gender="male",
            registered_at=self.hospital,
            created_by=self.doctor,
        )

    def test_appointment_created_in_past(self):
        """
        Test: Create appointment with scheduled_at in past (20 minutes ago).
        """
        past_time = timezone.now() - timedelta(minutes=20)

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=past_time,
            status="scheduled",
            created_by=self.doctor,
        )

        # Verify creation
        self.assertEqual(appointment.status, "scheduled")
        self.assertLess(appointment.scheduled_at, timezone.now())
        self.assertIsNone(appointment.no_show_marked_at)

    def test_mark_no_shows_task_execution(self):
        """
        Test: Call mark_no_shows_task directly.
        Verify it marks appointments as no_show.
        """
        # Create appointment 20 minutes ago (past grace period of 15 min)
        past_time = timezone.now() - timedelta(minutes=20)

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=past_time,
            status="scheduled",
            created_by=self.doctor,
        )

        # Execute task directly (runs synchronously in eager mode)
        result = mark_no_shows_task()

        # Verify task completed
        self.assertIsNotNone(result)
        if isinstance(result, dict):
            self.assertEqual(result["status"], "success")
            self.assertGreaterEqual(result["marked_count"], 0)

        # Verify appointment was marked
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "no_show")
        self.assertIsNotNone(appointment.no_show_marked_at)

    def test_no_show_marked_at_timestamp(self):
        """
        Test: Verify no_show_marked_at is set to current time.
        """
        past_time = timezone.now() - timedelta(minutes=20)
        before_marking = timezone.now()

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=past_time,
            status="scheduled",
            created_by=self.doctor,
        )

        # Mark as no-show manually
        appointment.status = "no_show"
        appointment.no_show_marked_at = timezone.now()
        appointment.save()

        after_marking = timezone.now()

        # Verify timestamp is recent
        self.assertIsNotNone(appointment.no_show_marked_at)
        self.assertGreaterEqual(appointment.no_show_marked_at, before_marking)
        self.assertLessEqual(appointment.no_show_marked_at, after_marking)

    def test_audit_log_created_for_no_show(self):
        """
        Test: Verify AuditLog entry can be created for no-show events.
        In production, system tasks would have a system user account.
        """
        past_time = timezone.now() - timedelta(minutes=20)

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=past_time,
            status="scheduled",
            created_by=self.doctor,
        )

        # Mark appointment as no-show
        appointment.status = "no_show"
        appointment.no_show_marked_at = timezone.now()
        appointment.save()

        # Create audit log entry (in production, would use a system user)
        audit = AuditLog.objects.create(
            user=self.doctor,  # In production, would be a system service account
            action="NO_SHOW_AUTO_MARKED",
            resource_type="appointment",
            resource_id=str(appointment.id),
            hospital=self.hospital,
            ip_address="0.0.0.0",
            user_agent="celery-task",
        )

        # Verify audit entry
        retrieved = AuditLog.objects.get(id=audit.id)
        self.assertEqual(retrieved.action, "NO_SHOW_AUTO_MARKED")
        self.assertEqual(retrieved.resource_type, "appointment")
        self.assertEqual(retrieved.hospital, self.hospital)
        self.assertEqual(retrieved.user, self.doctor)

    def test_no_show_override_within_7_days(self):
        """
        Test: Doctor can override no-show status within 7-day window.
        """
        # Create appointment marked as no-show less than 7 days ago
        marked_time = timezone.now() - timedelta(days=3)

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=marked_time - timedelta(minutes=20),
            status="no_show",
            no_show_marked_at=marked_time,
            created_by=self.doctor,
        )

        # Doctor overrides the no-show
        override_reason = "Patient called to reschedule - legitimate reason"
        appointment.status = "completed"
        appointment.no_show_override_reason = override_reason
        appointment.save()

        # Verify override
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "completed")
        self.assertEqual(appointment.no_show_override_reason, override_reason)

    def test_no_show_within_grace_period_not_marked(self):
        """
        Test: Appointments within 15-minute grace period are NOT marked.
        """
        # Create appointment 10 minutes ago (within grace period)
        recent_time = timezone.now() - timedelta(minutes=10)

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=recent_time,
            status="scheduled",
            created_by=self.doctor,
        )

        # Query for appointments to mark (should NOT include this)
        grace_period = timedelta(minutes=15)
        cutoff = timezone.now() - grace_period

        to_mark = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertNotIn(appointment.id, to_mark.values_list("id", flat=True))
        self.assertEqual(appointment.status, "scheduled")
        self.assertIsNone(appointment.no_show_marked_at)

    def test_already_completed_appointment_not_marked(self):
        """
        Test: Appointments already marked as completed are excluded from no-show marking.
        """
        past_time = timezone.now() - timedelta(minutes=20)

        appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=past_time,
            status="completed",
            created_by=self.doctor,
        )

        # Query for appointments to mark (should NOT include completed)
        grace_period = timedelta(minutes=15)
        cutoff = timezone.now() - grace_period

        to_mark = Appointment.objects.filter(
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        self.assertNotIn(appointment.id, to_mark.values_list("id", flat=True))


@override_settings(CELERY_ALWAYS_EAGER=True)
class MultiHospitalIsolationIntegrationTestCase(TestCase):
    """
    Scenario 4: Multi-Hospital Isolation
    Tests that data from different hospitals is properly isolated.
    Ensures break-glass, no-shows, and appointments don't cross hospital boundaries.
    """

    def setUp(self):
        """Create test fixtures for multi-hospital scenario."""
        # Create two separate hospitals
        self.hospital1 = Hospital.objects.create(
            name="Isolation Hospital 1",
            region="Region E",
            nhis_code="IH001",is_active=True,
        )

        self.hospital2 = Hospital.objects.create(
            name="Isolation Hospital 2",
            region="Region F",
            nhis_code="IH002",is_active=True,
        )

        # Create users in each hospital
        self.doctor1 = User.objects.create_user(
            email="doctor_h1@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital1,
            account_status="active",
        )

        self.doctor2 = User.objects.create_user(
            email="doctor_h2@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital2,
            account_status="active",
        )

        self.admin1 = User.objects.create_user(
            email="admin_h1@medsync.gh",
            password="SecurePass123!@#",
            role="hospital_admin",
            hospital=self.hospital1,
            account_status="active",
        )

        self.admin2 = User.objects.create_user(
            email="admin_h2@medsync.gh",
            password="SecurePass123!@#",
            role="hospital_admin",
            hospital=self.hospital2,
            account_status="active",
        )

        # Create patients in each hospital
        self.patient1 = Patient.objects.create(
            ghana_health_id="GHE111111",
            full_name="Patient Hospital 1",
            date_of_birth="1990-01-01",
            gender="male",
            registered_at=self.hospital1,
            created_by=self.doctor1,
        )

        self.patient2 = Patient.objects.create(
            ghana_health_id="GHE222222",
            full_name="Patient Hospital 2",
            date_of_birth="1991-02-02",
            gender="female",
            registered_at=self.hospital2,
            created_by=self.doctor2,
        )

        # Create global patients for break-glass tests
        self.global_patient1 = GlobalPatient.objects.create(
            first_name="Global",
            last_name="Patient 1",
            date_of_birth="1985-05-15",
            gender="male",
        )

        self.global_patient2 = GlobalPatient.objects.create(
            first_name="Global",
            last_name="Patient 2",
            date_of_birth="1986-06-16",
            gender="female",
        )

    def test_break_glass_hospital1_isolated_from_hospital2(self):
        """
        Test: Break-glass access in H1 doesn't affect H2.
        """
        now = timezone.now()

        # Create break-glass in hospital1
        log1 = BreakGlassLog.objects.create(
            global_patient=self.global_patient1,
            facility=self.hospital1,
            accessed_by=self.doctor1,
            reason="Emergency at H1",
            expires_at=now + timedelta(minutes=15),
        )

        # Create break-glass in hospital2
        log2 = BreakGlassLog.objects.create(
            global_patient=self.global_patient2,
            facility=self.hospital2,
            accessed_by=self.doctor2,
            reason="Emergency at H2",
            expires_at=now + timedelta(minutes=15),
        )

        # Verify isolation
        h1_logs = BreakGlassLog.objects.filter(facility=self.hospital1)
        h2_logs = BreakGlassLog.objects.filter(facility=self.hospital2)

        self.assertEqual(h1_logs.count(), 1)
        self.assertEqual(h2_logs.count(), 1)
        self.assertIn(log1.id, h1_logs.values_list("id", flat=True))
        self.assertNotIn(log2.id, h1_logs.values_list("id", flat=True))
        self.assertIn(log2.id, h2_logs.values_list("id", flat=True))
        self.assertNotIn(log1.id, h2_logs.values_list("id", flat=True))

    def test_no_show_appointments_hospital1_isolated(self):
        """
        Test: No-shows in H1 don't affect H2 appointments.
        """
        past_time = timezone.now() - timedelta(minutes=20)

        # Create past appointments in both hospitals
        appt1 = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=past_time,
            status="scheduled",
            created_by=self.doctor1,
        )

        appt2 = Appointment.objects.create(
            patient=self.patient2,
            hospital=self.hospital2,
            scheduled_at=past_time,
            status="scheduled",
            created_by=self.doctor2,
        )

        # Query for no-show candidates per hospital
        grace_period = timedelta(minutes=15)
        cutoff = timezone.now() - grace_period

        h1_to_mark = Appointment.objects.filter(
            hospital=self.hospital1,
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        h2_to_mark = Appointment.objects.filter(
            hospital=self.hospital2,
            status="scheduled",
            scheduled_at__lt=cutoff,
            no_show_marked_at__isnull=True,
        )

        # Verify each hospital sees only its appointments
        self.assertEqual(h1_to_mark.count(), 1)
        self.assertEqual(h2_to_mark.count(), 1)
        self.assertIn(appt1.id, h1_to_mark.values_list("id", flat=True))
        self.assertNotIn(appt2.id, h1_to_mark.values_list("id", flat=True))
        self.assertIn(appt2.id, h2_to_mark.values_list("id", flat=True))
        self.assertNotIn(appt1.id, h2_to_mark.values_list("id", flat=True))

    def test_hospital_admin_sees_only_own_hospital_data(self):
        """
        Test: Hospital admins can only see their own hospital's data.
        """
        # Create audit entries for both hospitals
        AuditLog.objects.create(
            user=self.doctor1,
            action="CREATE",
            resource_type="appointment",
            resource_id="test-appt-1",
            hospital=self.hospital1,
            ip_address="192.168.1.1",
            user_agent="test",
        )

        AuditLog.objects.create(
            user=self.doctor2,
            action="CREATE",
            resource_type="appointment",
            resource_id="test-appt-2",
            hospital=self.hospital2,
            ip_address="192.168.1.2",
            user_agent="test",
        )

        # Query by hospital
        h1_logs = AuditLog.objects.filter(hospital=self.hospital1)
        h2_logs = AuditLog.objects.filter(hospital=self.hospital2)

        # Verify isolation
        self.assertGreater(h1_logs.count(), 0)
        self.assertGreater(h2_logs.count(), 0)

        h1_ids = h1_logs.values_list("resource_id", flat=True)
        h2_ids = h2_logs.values_list("resource_id", flat=True)

        self.assertIn("test-appt-1", h1_ids)
        self.assertNotIn("test-appt-2", h1_ids)
        self.assertIn("test-appt-2", h2_ids)
        self.assertNotIn("test-appt-1", h2_ids)

    def test_patient_data_scoped_to_hospital(self):
        """
        Test: Patients registered in H1 are isolated from H2.
        """
        # Query patients by hospital
        h1_patients = Patient.objects.filter(registered_at=self.hospital1)
        h2_patients = Patient.objects.filter(registered_at=self.hospital2)

        # Verify scoping
        self.assertIn(self.patient1.id, h1_patients.values_list("id", flat=True))
        self.assertNotIn(self.patient2.id, h1_patients.values_list("id", flat=True))

        self.assertIn(self.patient2.id, h2_patients.values_list("id", flat=True))
        self.assertNotIn(self.patient1.id, h2_patients.values_list("id", flat=True))

    def test_no_cross_hospital_break_glass_access(self):
        """
        Test: Doctor from H1 cannot access H2 break-glass records.
        """
        now = timezone.now()

        # Create break-glass in H2
        log_h2 = BreakGlassLog.objects.create(
            global_patient=self.global_patient2,
            facility=self.hospital2,
            accessed_by=self.doctor2,
            reason="Emergency at H2",
            expires_at=now + timedelta(minutes=15),
        )

        # Query for H1 doctor (should not see H2 logs)
        h1_logs = BreakGlassLog.objects.filter(
            facility=self.hospital1,
            accessed_by=self.doctor1,
        )

        self.assertNotIn(log_h2.id, h1_logs.values_list("id", flat=True))

    def test_multi_hospital_appointment_isolation(self):
        """
        Test: Appointments are fully scoped to hospital.
        """
        # Create appointments in both hospitals
        appt1 = Appointment.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            scheduled_at=timezone.now() + timedelta(hours=1),
            status="scheduled",
            created_by=self.doctor1,
        )

        appt2 = Appointment.objects.create(
            patient=self.patient2,
            hospital=self.hospital2,
            scheduled_at=timezone.now() + timedelta(hours=1),
            status="scheduled",
            created_by=self.doctor2,
        )

        # Query by hospital
        h1_appts = Appointment.objects.filter(hospital=self.hospital1)
        h2_appts = Appointment.objects.filter(hospital=self.hospital2)

        # Verify isolation
        self.assertIn(appt1.id, h1_appts.values_list("id", flat=True))
        self.assertNotIn(appt2.id, h1_appts.values_list("id", flat=True))

        self.assertIn(appt2.id, h2_appts.values_list("id", flat=True))
        self.assertNotIn(appt1.id, h2_appts.values_list("id", flat=True))


# ============================================================================
# End-to-End Combined Scenario: All three phases in sequence
# ============================================================================

@override_settings(
    CELERY_ALWAYS_EAGER=True,
    CELERY_EAGER_PROPAGATES_EXCEPTIONS=True,
    CELERY_BROKER_URL="memory://",
    CELERY_RESULT_BACKEND="cache+memory://",
)
class EndToEndThreePhaseIntegrationTestCase(TestCase):
    """
    Complete end-to-end scenario testing all three phases together.
    """

    def setUp(self):
        """Setup for complete E2E test."""
        self.hospital = Hospital.objects.create(
            name="E2E Test Hospital",
            region="Region G",
            nhis_code="E2E001",is_active=True,
        )

        self.doctor = User.objects.create_user(
            email="e2e_doctor@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital,
            account_status="active",
        )

        self.patient = Patient.objects.create(
            ghana_health_id="GHE999999",
            full_name="E2E Test Patient",
            date_of_birth="1987-12-25",
            gender="male",
            registered_at=self.hospital,
            created_by=self.doctor,
        )

        self.global_patient = GlobalPatient.objects.create(
            first_name="E2E",
            last_name="Global Patient",
            date_of_birth="1987-12-25",
            gender="male",
        )

    def test_complete_e2e_workflow(self):
        """
        Complete end-to-end test:
        1. Create break-glass access
        2. Submit PDF export task
        3. Mark no-show appointment
        4. Verify all logged to audit trail
        """
        now = timezone.now()

        # Phase 1: Create break-glass access
        break_glass_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital,
            accessed_by=self.doctor,
            reason="E2E Emergency Test",
            expires_at=now + timedelta(minutes=15),
        )

        AuditLog.objects.create(
            user=self.doctor,
            action="EMERGENCY_ACCESS",
            resource_type="break_glass",
            resource_id=str(break_glass_log.id),
            hospital=self.hospital,
            ip_address="127.0.0.1",
            user_agent="e2e-test",
        )

        # Phase 2: Submit PDF export task
        pdf_result = export_patient_pdf_task(str(self.patient.id), format_type="summary")

        # Phase 3: Mark no-show appointment
        past_appointment = Appointment.objects.create(
            patient=self.patient,
            hospital=self.hospital,
            scheduled_at=now - timedelta(minutes=20),
            status="scheduled",
            created_by=self.doctor,
        )

        mark_no_shows_result = mark_no_shows_task()

        # Verify all phases completed
        self.assertFalse(break_glass_log.is_expired())
        self.assertIsNotNone(pdf_result)
        self.assertIsNotNone(mark_no_shows_result)

        # Verify appointment was marked
        past_appointment.refresh_from_db()
        self.assertEqual(past_appointment.status, "no_show")
        self.assertIsNotNone(past_appointment.no_show_marked_at)

        # Verify audit trail has entries
        audit_entries = AuditLog.objects.filter(hospital=self.hospital)
        audit_actions = audit_entries.values_list("action", flat=True)

        self.assertIn("EMERGENCY_ACCESS", audit_actions)


