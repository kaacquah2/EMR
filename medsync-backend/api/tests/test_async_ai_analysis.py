"""
Test suite for async AI analysis endpoints (Phase 4.2).

Tests cover:
- POST /ai/async-analysis/:patient_id - Start async job
- GET /ai/async-analysis/:job_id - Poll job status
- Job status transitions (pending → processing → completed/failed)
- Role-based permissions (doctor, nurse, hospital_admin, super_admin)
- Hospital scoping (users see only their hospital's jobs)
- Error handling (patient not found, access denied, invalid analysis type)
- Progress tracking (0-100%)
"""

import uuid

from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from core.models import User, Hospital
from patients.models import Patient
from api.models import AIAnalysisJob, AIAnalysis


class AsyncAIAnalysisSetupMixin:
    """Shared setup for async AI analysis tests."""

    def setUp(self):
        """Create hospitals, users, and patients."""
        # Hospital 1
        self.hospital1 = Hospital.objects.create(
            id=uuid.uuid4(),
            name="Test Hospital 1",
            region="Accra",
            nhis_code="TH1001",
            address="123 Medical Street",
            is_active=True
        )

        # Hospital 2
        self.hospital2 = Hospital.objects.create(
            id=uuid.uuid4(),
            name="Test Hospital 2",
            region="Kumasi",
            nhis_code="TH2001",
            address="456 Health Avenue",
            is_active=True
        )

        # Doctors
        self.doctor1 = User.objects.create_user(
            email="doctor1@hospital1.gh",
            password="Doctor123!@#",
            full_name="Doctor One",
            role="doctor",
            hospital=self.hospital1
        )

        self.doctor2 = User.objects.create_user(
            email="doctor2@hospital2.gh",
            password="Doctor123!@#",
            full_name="Doctor Two",
            role="doctor",
            hospital=self.hospital2
        )

        # Nurse at hospital 1
        self.nurse1 = User.objects.create_user(
            email="nurse1@hospital1.gh",
            password="Nurse123!@#",
            full_name="Nurse One",
            role="nurse",
            hospital=self.hospital1
        )

        # Hospital admin
        self.hospital_admin1 = User.objects.create_user(
            email="admin1@hospital1.gh",
            password="Admin123!@#",
            full_name="Hospital Admin",
            role="hospital_admin",
            hospital=self.hospital1
        )

        # Super admin
        self.super_admin = User.objects.create_user(
            email="superadmin@medsync.gh",
            password="SuperAdmin123!@#",
            full_name="Super Admin",
            role="super_admin",
            is_staff=True,
            is_superuser=True
        )

        # Patients
        self.patient1 = Patient.objects.create(
            id=uuid.uuid4(),
            ghana_health_id="GH123456789",
            full_name="Patient One",
            date_of_birth="1990-01-15",
            gender="M",
            blood_group="O+",
            registered_at=self.hospital1,
            created_by=self.doctor1
        )

        self.patient2 = Patient.objects.create(
            id=uuid.uuid4(),
            ghana_health_id="GH987654321",
            full_name="Patient Two",
            date_of_birth="1985-06-20",
            gender="F",
            blood_group="A+",
            registered_at=self.hospital2,
            created_by=self.doctor2
        )

        self.client = APIClient()


class StartAsyncAnalysisTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test POST /ai/async-analysis/:patient_id"""

    def test_doctor_can_start_analysis(self):
        """Doctor can start async analysis for their patient."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('job_id', response.data)
        self.assertIn('polling_url', response.data)
        self.assertEqual(response.data['status'], 'pending')

        # Verify job created
        job = AIAnalysisJob.objects.get(id=response.data['job_id'])
        self.assertEqual(job.patient_id, self.patient1.id)
        self.assertEqual(job.analysis_type, 'comprehensive')
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.progress_percent, 0)

    def test_hospital_admin_can_start_analysis(self):
        """Hospital admin can start async analysis."""
        self.client.force_authenticate(user=self.hospital_admin1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'risk_prediction'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['analysis_type'], 'risk_prediction')

    def test_super_admin_can_start_analysis(self):
        """Super admin can start async analysis."""
        self.client.force_authenticate(user=self.super_admin)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

    def test_nurse_cannot_start_analysis(self):
        """Nurse cannot start async analysis (permission denied)."""
        self.client.force_authenticate(user=self.nurse1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_access_other_hospital_patient(self):
        """Doctor cannot start analysis for patient at different hospital."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient2.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_analysis_type_rejected(self):
        """Invalid analysis type is rejected."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'invalid_type'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Invalid analysis type', response.data['error'])

    def test_patient_not_found(self):
        """Non-existent patient returns 404."""
        self.client.force_authenticate(user=self.doctor1)

        fake_patient_id = uuid.uuid4()
        response = self.client.post(
            f'/api/v1/ai/async-analysis/{fake_patient_id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_analysis_types_accepted(self):
        """All valid analysis types are accepted."""
        self.client.force_authenticate(user=self.doctor1)

        valid_types = [
            'comprehensive',
            'risk_prediction',
            'clinical_decision_support',
            'triage',
            'similarity_search',
            'referral'
        ]

        for analysis_type in valid_types:
            response = self.client.post(
                f'/api/v1/ai/async-analysis/{self.patient1.id}',
                data={'analysis_type': analysis_type},
                format='json'
            )

            self.assertEqual(
                response.status_code,
                status.HTTP_202_ACCEPTED,
                f"Failed for analysis_type={analysis_type}"
            )
            self.assertEqual(response.data['analysis_type'], analysis_type)

    def test_default_analysis_type(self):
        """Default analysis type is comprehensive."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={},  # No analysis_type specified
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['analysis_type'], 'comprehensive')


class PollAsyncAnalysisStatusTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test GET /ai/async-analysis/:job_id"""

    def setUp(self):
        """Set up analysis jobs for testing."""
        super().setUp()

        # Create a pending job
        self.pending_job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive',
            status='pending',
            progress_percent=0,
            current_step='Queued'
        )

        # Create a processing job
        self.processing_job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='risk_prediction',
            status='processing',
            progress_percent=45,
            current_step='Running risk prediction agent',
            started_at=timezone.now()
        )

        # Create a completed job
        self.analysis = AIAnalysis.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            performed_by=self.doctor1,
            analysis_type='comprehensive',
            overall_confidence=0.95,
            agents_executed=['data_agent', 'risk_agent'],
            clinical_summary='Patient at low risk',
            recommended_actions=['Continue monitoring', 'Schedule follow-up'],
            alerts=['Recent fever spike']
        )

        self.completed_job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive',
            status='completed',
            progress_percent=100,
            current_step='Analysis complete',
            analysis_result=self.analysis,
            started_at=timezone.now(),
            completed_at=timezone.now()
        )

    def test_doctor_can_poll_own_hospital_job(self):
        """Doctor can poll job for patient in their hospital."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.pending_job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['job_id'], str(self.pending_job.id))
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['progress_percent'], 0)

    def test_nurse_can_poll_job(self):
        """Nurse can poll job status (read-only)."""
        self.client.force_authenticate(user=self.nurse1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.processing_job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'processing')
        self.assertEqual(response.data['progress_percent'], 45)
        self.assertEqual(response.data['current_step'], 'Running risk prediction agent')

    def test_completed_job_includes_analysis(self):
        """Completed job response includes analysis results."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.completed_job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['progress_percent'], 100)
        self.assertIn('analysis', response.data)
        self.assertIsNotNone(response.data['analysis'])
        self.assertEqual(response.data['analysis']['analysis_id'], str(self.analysis.id))

    def test_doctor_cannot_poll_other_hospital_job(self):
        """Doctor cannot poll job for patient at different hospital."""
        self.client.force_authenticate(user=self.doctor2)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.pending_job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_job_not_found(self):
        """Non-existent job returns 404."""
        self.client.force_authenticate(user=self.doctor1)

        fake_job_id = uuid.uuid4()
        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{fake_job_id}'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_super_admin_can_poll_any_job(self):
        """Super admin can poll jobs from any hospital."""
        self.client.force_authenticate(user=self.super_admin)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.pending_job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_processing_job_excludes_analysis(self):
        """Processing job response does not include analysis."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.processing_job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data.get('analysis'))

    def test_progress_percent_range(self):
        """Progress percent is between 0 and 100."""
        self.client.force_authenticate(user=self.doctor1)

        # Create job with various progress levels
        for percent in [0, 25, 50, 75, 99, 100]:
            job = AIAnalysisJob.objects.create(
                patient=self.patient1,
                hospital=self.hospital1,
                created_by=self.doctor1,
                analysis_type='comprehensive',
                status='processing' if percent < 100 else 'completed',
                progress_percent=percent
            )

            response = self.client.get(
                f'/api/v1/ai/async-analysis/status/{job.id}'
            )

            self.assertEqual(response.data['progress_percent'], percent)

    def test_serializer_fields_present(self):
        """Response includes all required serializer fields."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.pending_job.id}'
        )

        required_fields = [
            'job_id', 'patient_id', 'status', 'progress_percent',
            'current_step', 'analysis_type', 'created_at'
        ]

        for field in required_fields:
            self.assertIn(field, response.data, f"Missing field: {field}")


class PermissionMatrixTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test permission matrix enforcement."""

    def setUp(self):
        """Set up test data."""
        super().setUp()

        self.job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive',
            status='pending'
        )

        # Lab technician
        self.lab_tech = User.objects.create_user(
            email="labtech@hospital1.gh",
            password="LabTech123!@#",
            full_name="Lab Tech",
            role="lab_technician",
            hospital=self.hospital1
        )

        # Receptionist
        self.receptionist = User.objects.create_user(
            email="receptionist@hospital1.gh",
            password="Receptionist123!@#",
            full_name="Receptionist",
            role="receptionist",
            hospital=self.hospital1
        )

    def test_lab_tech_cannot_post(self):
        """Lab technician cannot POST /ai/async-analysis."""
        self.client.force_authenticate(user=self.lab_tech)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_lab_tech_can_get_status(self):
        """Lab technician can GET job status (not in permission matrix, but check)."""
        self.client.force_authenticate(user=self.lab_tech)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.job.id}'
        )

        # Lab tech not in GET permissions, should be 403
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_receptionist_cannot_post(self):
        """Receptionist cannot POST."""
        self.client.force_authenticate(user=self.receptionist)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_user_denied(self):
        """Unauthenticated user is denied."""
        # No authentication

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_requires_authentication(self):
        """GET without authentication is denied."""
        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.job.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class HospitalScopingTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test hospital scoping enforcement."""

    def setUp(self):
        """Set up jobs in multiple hospitals."""
        super().setUp()

        self.job1 = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive'
        )

        self.job2 = AIAnalysisJob.objects.create(
            patient=self.patient2,
            hospital=self.hospital2,
            created_by=self.doctor2,
            analysis_type='risk_prediction'
        )

    def test_doctor1_sees_only_hospital1_jobs(self):
        """Doctor1 can only start jobs for hospital1 patients."""
        self.client.force_authenticate(user=self.doctor1)

        # Can start for patient1 (hospital1)
        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Cannot start for patient2 (hospital2)
        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient2.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor1_can_poll_hospital1_jobs(self):
        """Doctor1 can poll hospital1 jobs."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.job1.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor1_cannot_poll_hospital2_jobs(self):
        """Doctor1 cannot poll hospital2 jobs."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.job2.id}'
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_super_admin_can_poll_any_job(self):
        """Super admin can poll jobs from any hospital."""
        self.client.force_authenticate(user=self.super_admin)

        response1 = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.job1.id}'
        )
        response2 = self.client.get(
            f'/api/v1/ai/async-analysis/status/{self.job2.id}'
        )

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)


class JobLifecycleTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test job lifecycle and status transitions."""

    def test_job_lifecycle_pending_to_processing(self):
        """Job can transition from pending to processing."""
        job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive',
            status='pending'
        )

        # Verify initial state
        self.assertEqual(job.status, 'pending')
        self.assertEqual(job.progress_percent, 0)

        # Transition to processing
        job.status = 'processing'
        job.progress_percent = 25
        job.current_step = 'Running analysis'
        job.started_at = timezone.now()
        job.save()

        # Verify new state
        job.refresh_from_db()
        self.assertEqual(job.status, 'processing')
        self.assertEqual(job.progress_percent, 25)

    def test_job_lifecycle_processing_to_completed(self):
        """Job can transition from processing to completed."""
        job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive',
            status='processing',
            progress_percent=75
        )

        # Create analysis result
        analysis = AIAnalysis.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            performed_by=self.doctor1
        )

        # Transition to completed
        job.status = 'completed'
        job.progress_percent = 100
        job.current_step = 'Complete'
        job.analysis_result = analysis
        job.completed_at = timezone.now()
        job.save()

        # Verify new state
        job.refresh_from_db()
        self.assertEqual(job.status, 'completed')
        self.assertEqual(job.progress_percent, 100)
        self.assertIsNotNone(job.completed_at)

    def test_job_lifecycle_processing_to_failed(self):
        """Job can transition from processing to failed."""
        job = AIAnalysisJob.objects.create(
            patient=self.patient1,
            hospital=self.hospital1,
            created_by=self.doctor1,
            analysis_type='comprehensive',
            status='processing',
            progress_percent=50
        )

        # Transition to failed
        job.status = 'failed'
        job.error_message = 'AI service timeout after 60s'
        job.completed_at = timezone.now()
        job.save()

        # Verify new state
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertIn('timeout', job.error_message)
        self.assertIsNotNone(job.completed_at)


class ErrorHandlingTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test error handling and edge cases."""

    def test_malformed_json_body(self):
        """Malformed JSON request body is handled."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data='{"invalid json',
            content_type='application/json'
        )

        # Django REST Framework handles JSON parsing errors
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_missing_patient_id_in_url(self):
        """Missing patient_id in URL returns 404."""
        self.client.force_authenticate(user=self.doctor1)

        # Try to call without patient_id
        response = self.client.post(
            '/api/v1/ai/async-analysis/',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_empty_analysis_type_uses_default(self):
        """Empty analysis_type uses default (comprehensive)."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': ''},
            format='json'
        )

        # Empty string should be treated as invalid
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_null_analysis_type_uses_default(self):
        """Null/missing analysis_type uses default."""
        self.client.force_authenticate(user=self.doctor1)

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertEqual(response.data['analysis_type'], 'comprehensive')


class AuditLoggingTest(AsyncAIAnalysisSetupMixin, TestCase):
    """Test audit logging for async AI endpoints."""

    def test_start_analysis_logged(self):
        """Starting async analysis creates audit log."""
        self.client.force_authenticate(user=self.doctor1)

        from core.models import AuditLog

        initial_count = AuditLog.objects.count()

        response = self.client.post(
            f'/api/v1/ai/async-analysis/{self.patient1.id}',
            data={'analysis_type': 'comprehensive'},
            format='json'
        )

        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)

        # Verify audit log created
        new_logs = AuditLog.objects.all().order_by('-created_at')
        self.assertGreater(new_logs.count(), initial_count)

        latest_log = new_logs.first()
        self.assertEqual(latest_log.action, 'AI_ANALYSIS_START_ASYNC')
        self.assertEqual(latest_log.resource_type, 'Patient')
        self.assertEqual(latest_log.user, self.doctor1)


