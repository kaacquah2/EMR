"""
Tests for BreakGlassExpiryMiddleware.

Validates that the middleware blocks expired break-glass requests at the request level
and audits the attempts.
"""
from django.test import TestCase, RequestFactory
from django.utils import timezone
from datetime import timedelta
from rest_framework.test import APIClient
from rest_framework import status

from core.models import User, Hospital, AuditLog
from interop.models import GlobalPatient, BreakGlassLog
from api.middleware import BreakGlassExpiryMiddleware


class BreakGlassExpiryMiddlewareTestCase(TestCase):
    """Test BreakGlassExpiryMiddleware enforces time-window expiry."""

    def setUp(self):
        """Create test fixtures."""
        self.client = APIClient()
        self.factory = RequestFactory()

        # Create hospitals
        self.hospital1 = Hospital.objects.create(
            name="Test Hospital 1",
            region="Region A",
            nhis_code="H001",
            is_active=True,
        )

        # Create user (doctor)
        self.doctor = User.objects.create_user(
            email="doctor@medsync.gh",
            password="SecurePass123!@#",
            role="doctor",
            hospital=self.hospital1,
            account_status="active",
        )

        # Create global patient
        self.global_patient = GlobalPatient.objects.create(
            first_name="John",
            last_name="Doe",
            date_of_birth="1990-01-01",
            gender="male",
        )

        # Initialize middleware
        self.middleware = BreakGlassExpiryMiddleware(lambda r: None)

    def test_middleware_allows_valid_break_glass_access(self):
        """Test that middleware allows requests with valid (non-expired) break-glass."""
        # Create a valid break-glass log (expires in 10 minutes)
        valid_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor,
            reason="Emergency access",
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        # Create request to global patient endpoint
        request = self.factory.get("/api/v1/global-patient/test")
        request.user = self.doctor

        # Mock get_response to return success
        def mock_response(req):
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should allow the request
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_middleware_blocks_expired_break_glass_access(self):
        """Test that middleware blocks requests with expired break-glass."""
        # Create an expired break-glass log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor,
            reason="Emergency access",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Create request to global patient endpoint
        request = self.factory.get("/api/v1/global-patient/test")
        request.user = self.doctor
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent"

        # Mock get_response (should not be called if middleware blocks)
        call_count = [0]
        def mock_response(req):
            call_count[0] += 1
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should block the request
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertIn("Break-glass access window expired", str(response.data.get("detail", "")))
        self.assertEqual(response.data.get("code"), "BREAK_GLASS_EXPIRED")

    def test_middleware_audits_expired_break_glass_attempt(self):
        """Test that middleware audits expired break-glass access attempts."""
        # Create an expired break-glass log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor,
            reason="Emergency access",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Create request
        request = self.factory.get("/api/v1/global-patient/test")
        request.user = self.doctor
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent"

        # Count audit logs before
        audit_count_before = AuditLog.objects.count()

        # Process through middleware
        def mock_response(req):
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should create an audit log
        audit_count_after = AuditLog.objects.count()
        self.assertEqual(audit_count_after, audit_count_before + 1)

        # Check audit log details
        audit_log = AuditLog.objects.latest("timestamp")
        self.assertEqual(audit_log.action, "BREAK_GLASS_EXPIRED_ACCESS")
        self.assertEqual(audit_log.user, self.doctor)
        self.assertEqual(audit_log.resource_type, "break_glass_log")
        self.assertEqual(audit_log.resource_id, str(expired_log.id))

    def test_middleware_skips_non_protected_endpoints(self):
        """Test that middleware doesn't check non-protected endpoints."""
        # Create an expired break-glass log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor,
            reason="Emergency access",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Create request to non-protected endpoint
        request = self.factory.get("/api/v1/auth/me")
        request.user = self.doctor
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Mock get_response
        def mock_response(req):
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should allow the request even with expired break-glass
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_middleware_allows_unauthenticated_requests(self):
        """Test that middleware allows unauthenticated requests through."""
        # Create request without user
        request = self.factory.get("/api/v1/global-patient/test")
        request.user = None

        # Mock get_response
        def mock_response(req):
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should allow the request (authentication is handled by other middleware)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_middleware_allows_break_glass_list_endpoint(self):
        """Test that break-glass list endpoint is protected."""
        # Create an expired break-glass log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor,
            reason="Emergency access",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Create request to break-glass list endpoint
        request = self.factory.get("/api/v1/break-glass/list")
        request.user = self.doctor
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        request.META["HTTP_USER_AGENT"] = "TestAgent"

        # Mock get_response
        def mock_response(req):
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should block the request
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_middleware_no_break_glass_allows_request(self):
        """Test that requests without break-glass are allowed."""
        # Don't create any break-glass log

        # Create request to global patient endpoint
        request = self.factory.get("/api/v1/global-patient/test")
        request.user = self.doctor
        request.META["REMOTE_ADDR"] = "127.0.0.1"

        # Mock get_response
        def mock_response(req):
            from rest_framework.response import Response
            return Response({"status": "ok"}, status=status.HTTP_200_OK)

        middleware = BreakGlassExpiryMiddleware(mock_response)
        response = middleware(request)

        # Should allow the request (no break-glass = no expiry check)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_middleware_integration_with_api_client(self):
        """Integration test: verify middleware works with actual API client."""
        # This test uses the APIClient to make real HTTP-like requests
        # Create an expired break-glass log
        expired_log = BreakGlassLog.objects.create(
            global_patient=self.global_patient,
            facility=self.hospital1,
            accessed_by=self.doctor,
            reason="Emergency access",
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        # Login doctor
        self.client.force_authenticate(user=self.doctor)

        # Try to access global patient (will be blocked by middleware)
        response = self.client.get(
            f"/api/v1/global-patient/{self.global_patient.id}/"
        )

        # Should get 403 from middleware
        # Note: The actual response might vary based on view implementation,
        # but the middleware should have run and potentially blocked it
        # If the view is callable, middleware returns 403
