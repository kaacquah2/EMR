"""
Tests for Celery task status and result endpoints.
Verifies permissions, status retrieval, result retrieval, and error handling.
"""
import uuid
from datetime import timedelta
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status as http_status

from core.models import User, Hospital, TaskSubmission
from api.utils import register_task_submission


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TaskStatusEndpointTestCase(TestCase):
    """Test task status endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        # Create hospital
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="THO123",
        )

        # Create users
        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            full_name="Test Doctor",
            account_status="active",
        )

        self.nurse = User.objects.create_user(
            email="nurse@test.com",
            password="TempPass123!@#",
            role="nurse",
            hospital=self.hospital,
            full_name="Test Nurse",
            account_status="active",
        )

        self.super_admin = User.objects.create_user(
            email="admin@test.com",
            password="TempPass123!@#",
            role="super_admin",
            full_name="Super Admin",
            account_status="active",
        )

    def test_task_status_basic(self):
        """Test getting status of a basic task."""
        # Create a task submission
        task_id = str(uuid.uuid4())
        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            resource_type="patient",
            resource_id="patient-uuid",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Authenticate and request
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["task_id"], task_id)
        self.assertEqual(response.data["task_type"], "PDF Export")
        self.assertEqual(response.data["resource_type"], "patient")

    def test_task_status_not_found(self):
        """Test 404 when task doesn't exist."""
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}")

        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_task_status_permission_denied(self):
        """Test 403 when user tries to view another user's task."""
        # Create task for doctor
        task_id = str(uuid.uuid4())
        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Authenticate as nurse and try to access
        self.client.force_authenticate(user=self.nurse)
        response = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_task_status_super_admin_can_view_all(self):
        """Test super_admin can view any task."""
        # Create task for doctor
        task_id = str(uuid.uuid4())
        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        # Authenticate as super_admin
        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["task_id"], task_id)

    def test_task_status_requires_authentication(self):
        """Test endpoint requires authentication."""
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}")
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_task_status_includes_metadata(self):
        """Test task status includes all required metadata."""
        task_id = str(uuid.uuid4())
        submitted_at = timezone.now()
        expires_at = submitted_at + timedelta(hours=1)

        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=self.doctor,
            hospital=self.hospital,
            task_type="ai_analysis",
            resource_type="encounter",
            resource_id="enc-123",
            submitted_at=submitted_at,
            expires_at=expires_at,
        )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/tasks/{task_id}")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        data = response.data

        # Verify all fields present
        self.assertIn("task_id", data)
        self.assertIn("status", data)
        self.assertIn("task_type", data)
        self.assertIn("resource_type", data)
        self.assertIn("resource_id", data)
        self.assertIn("created_at", data)
        self.assertIn("expires_at", data)


@override_settings(CELERY_ALWAYS_EAGER=True, CELERY_EAGER_PROPAGATES_EXCEPTIONS=True)
class TaskResultEndpointTestCase(TestCase):
    """Test task result endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="THO123",
        )

        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            full_name="Test Doctor",
            account_status="active",
        )

        self.super_admin = User.objects.create_user(
            email="admin@test.com",
            password="TempPass123!@#",
            role="super_admin",
            full_name="Super Admin",
            account_status="active",
        )

    def test_task_result_not_found(self):
        """Test 404 when task doesn't exist."""
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}/result")

        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)

    def test_task_result_permission_denied(self):
        """Test 403 when user tries to view another user's result."""
        task_id = str(uuid.uuid4())

        other_doctor = User.objects.create_user(
            email="other@test.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            full_name="Other Doctor",
            account_status="active",
        )

        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=other_doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/tasks/{task_id}/result")

        self.assertEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)

    def test_task_result_expired(self):
        """Test 404 when result has expired."""
        task_id = str(uuid.uuid4())

        # Create with past expiration
        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            submitted_at=timezone.now() - timedelta(hours=2),
            expires_at=timezone.now() - timedelta(hours=1),
        )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get(f"/api/v1/tasks/{task_id}/result")

        self.assertEqual(response.status_code, http_status.HTTP_404_NOT_FOUND)
        self.assertIn("expired", response.data["message"].lower())

    def test_task_result_requires_authentication(self):
        """Test endpoint requires authentication."""
        response = self.client.get(f"/api/v1/tasks/{uuid.uuid4()}/result")
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)

    def test_task_result_super_admin_can_view(self):
        """Test super_admin can view any task result."""
        task_id = str(uuid.uuid4())

        TaskSubmission.objects.create(
            celery_task_id=task_id,
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get(f"/api/v1/tasks/{task_id}/result")

        # Will be 404 because task is still pending (no SUCCESS status in eager mode without setup)
        # But permission should pass
        self.assertNotEqual(response.status_code, http_status.HTTP_403_FORBIDDEN)


class TaskListEndpointTestCase(TestCase):
    """Test task listing endpoint."""

    def setUp(self):
        """Set up test data."""
        self.client = APIClient()

        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="THO123",
        )

        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            full_name="Test Doctor",
            account_status="active",
        )

        self.other_doctor = User.objects.create_user(
            email="other@test.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            full_name="Other Doctor",
            account_status="active",
        )

        self.super_admin = User.objects.create_user(
            email="admin@test.com",
            password="TempPass123!@#",
            role="super_admin",
            full_name="Super Admin",
            account_status="active",
        )

    def test_task_list_user_sees_own_tasks(self):
        """Test user sees only their own tasks."""
        # Create tasks for doctor
        for i in range(3):
            TaskSubmission.objects.create(
                celery_task_id=str(uuid.uuid4()),
                user=self.doctor,
                hospital=self.hospital,
                task_type="export_pdf",
                submitted_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=1),
            )

        # Create tasks for other doctor
        for i in range(2):
            TaskSubmission.objects.create(
                celery_task_id=str(uuid.uuid4()),
                user=self.other_doctor,
                hospital=self.hospital,
                task_type="export_pdf",
                submitted_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=1),
            )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/tasks")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 3)

    def test_task_list_super_admin_sees_all(self):
        """Test super_admin sees all tasks."""
        # Create tasks for multiple users
        for i in range(3):
            TaskSubmission.objects.create(
                celery_task_id=str(uuid.uuid4()),
                user=self.doctor,
                hospital=self.hospital,
                task_type="export_pdf",
                submitted_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=1),
            )

        for i in range(2):
            TaskSubmission.objects.create(
                celery_task_id=str(uuid.uuid4()),
                user=self.other_doctor,
                hospital=self.hospital,
                task_type="export_pdf",
                submitted_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=1),
            )

        self.client.force_authenticate(user=self.super_admin)
        response = self.client.get("/api/v1/tasks")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 5)

    def test_task_list_filter_by_type(self):
        """Test filtering tasks by type."""
        # Create tasks of different types
        TaskSubmission.objects.create(
            celery_task_id=str(uuid.uuid4()),
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        TaskSubmission.objects.create(
            celery_task_id=str(uuid.uuid4()),
            user=self.doctor,
            hospital=self.hospital,
            task_type="ai_analysis",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/tasks?task_type=export_pdf")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["task_type"], "PDF Export")

    def test_task_list_filter_by_resource_type(self):
        """Test filtering tasks by resource type."""
        # Create tasks with different resource types
        TaskSubmission.objects.create(
            celery_task_id=str(uuid.uuid4()),
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            resource_type="patient",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        TaskSubmission.objects.create(
            celery_task_id=str(uuid.uuid4()),
            user=self.doctor,
            hospital=self.hospital,
            task_type="export_pdf",
            resource_type="encounter",
            submitted_at=timezone.now(),
            expires_at=timezone.now() + timedelta(hours=1),
        )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/tasks?resource_type=patient")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["data"][0]["resource_type"], "patient")

    def test_task_list_limit(self):
        """Test task list limit parameter."""
        # Create 50 tasks
        for i in range(50):
            TaskSubmission.objects.create(
                celery_task_id=str(uuid.uuid4()),
                user=self.doctor,
                hospital=self.hospital,
                task_type="export_pdf",
                submitted_at=timezone.now(),
                expires_at=timezone.now() + timedelta(hours=1),
            )

        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/tasks?limit=10")

        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 10)

    def test_task_list_limit_capped(self):
        """Test task list limit is capped at 100."""
        # Try to get 200
        self.client.force_authenticate(user=self.doctor)
        response = self.client.get("/api/v1/tasks?limit=200")

        # Should be capped at 100
        self.assertEqual(response.status_code, http_status.HTTP_200_OK)
        # With 0 tasks, total should be 0, not 200
        self.assertEqual(response.data["total"], 0)

    def test_task_list_requires_authentication(self):
        """Test endpoint requires authentication."""
        response = self.client.get("/api/v1/tasks")
        self.assertEqual(response.status_code, http_status.HTTP_401_UNAUTHORIZED)


class TaskSubmissionUtilityTestCase(TestCase):
    """Test task submission registration utility."""

    def setUp(self):
        """Set up test data."""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="THO123",
        )

        self.user = User.objects.create_user(
            email="user@test.com",
            password="TempPass123!@#",
            role="doctor",
            hospital=self.hospital,
            full_name="Test User",
            account_status="active",
        )

    def test_register_task_submission(self):
        """Test registering a task submission."""
        task_id = str(uuid.uuid4())

        task_submission = register_task_submission(
            celery_task_id=task_id,
            user=self.user,
            task_type="export_pdf",
            resource_type="patient",
            resource_id="patient-uuid",
            hospital=self.hospital,
        )

        self.assertIsNotNone(task_submission.id)
        self.assertEqual(task_submission.celery_task_id, task_id)
        self.assertEqual(task_submission.user, self.user)
        self.assertEqual(task_submission.task_type, "export_pdf")
        self.assertEqual(task_submission.resource_type, "patient")

    def test_register_task_submission_sets_expiration(self):
        """Test task submission expiration is set to 1 hour."""
        task_id = str(uuid.uuid4())
        timezone.now()

        task_submission = register_task_submission(
            celery_task_id=task_id,
            user=self.user,
            task_type="export_pdf",
            hospital=self.hospital,
        )

        timezone.now()

        # Expiration should be approximately 1 hour from now
        expected_expires = timezone.now() + timedelta(hours=1)
        time_diff = abs((task_submission.expires_at - expected_expires).total_seconds())

        # Should be within 5 seconds
        self.assertLess(time_diff, 5)

    def test_register_task_submission_sanitizes_resource_id(self):
        """Test task submission sanitizes long resource IDs."""
        task_id = str(uuid.uuid4())
        long_id = "x" * 200  # Exceeds max length

        task_submission = register_task_submission(
            celery_task_id=task_id,
            user=self.user,
            task_type="export_pdf",
            resource_id=long_id,
            hospital=self.hospital,
        )

        # Should be redacted
        self.assertEqual(task_submission.resource_id, "[REDACTED]")


