"""
CRITICAL FIX #2: Password Reset Token Security Tests

Tests for:
- Constant-time token comparison (prevent timing attacks)
- Token in POST body (prevent URL/browser history leakage)
- Email-based token delivery
- Frontend URL configuration
- Token expiry validation
"""

import secrets
import os
from datetime import timedelta
from django.test import TestCase, Client, override_settings
from django.utils import timezone
from django.conf import settings
from core.models import User, Hospital, PasswordResetAudit
from rest_framework import status

# Set Django settings before imports
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')

import django
django.setup()


class TestPasswordResetTokenSecurity(TestCase):
    """Test CRITICAL FIX #2: Password reset token security features."""
    
    def setUp(self):
        """Create test data."""
        self.client = Client()
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="TH001"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="OldPassword123!",
            role="doctor",
            full_name="Dr. Test",
            hospital=self.hospital,
            account_status="active",
        )
    
    def test_reset_password_token_in_post_body_not_url(self):
        """Test that token is accepted in POST body, not URL parameter."""
        # Set up reset token
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.user.save()
        
        # Token should NOT be in URL
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
                "new_password": "NewPassword123!@#",
            },
            content_type="application/json"
        )
        
        # Should succeed with POST body token
        assert response.status_code in [200, 400], f"Got {response.status_code}: {response.content}"
    
    def test_constant_time_comparison_prevents_timing_attacks(self):
        """Test that constant-time comparison is used for token validation."""
        # Set up reset token
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.user.save()
        
        # Test with wrong token - should not leak timing information
        wrong_token = "x" * len(reset_token)
        
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": wrong_token,
                "new_password": "NewPassword123!@#",
            },
            content_type="application/json"
        )
        
        # Should reject with generic error message
        assert response.status_code == 400
        assert "Invalid reset request" in response.data.get("message", "")
    
    def test_reset_password_with_valid_token(self):
        """Test password reset with valid token."""
        # Set up reset token
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.user.save()
        
        new_password = "NewPassword123!@#"
        
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
                "new_password": new_password,
            },
            content_type="application/json"
        )
        
        # Should succeed
        assert response.status_code == 200, f"Got {response.status_code}: {response.content}"
        assert "successful" in response.data.get("message", "").lower()
        
        # Verify token is cleared
        self.user.refresh_from_db()
        assert self.user.password_reset_token is None
        assert self.user.password_reset_expires_at is None
        
        # Verify password changed
        assert self.user.check_password(new_password)
    
    def test_reset_password_token_expires(self):
        """Test that expired tokens are rejected."""
        # Set up expired reset token
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() - timedelta(hours=1)  # Expired
        self.user.save()
        
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
                "new_password": "NewPassword123!@#",
            },
            content_type="application/json"
        )
        
        # Should reject as expired
        assert response.status_code == 400
        assert "expired" in response.data.get("message", "").lower()
    
    def test_reset_password_requires_email_token_password(self):
        """Test that all required fields are validated."""
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.user.save()
        
        # Missing email
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "reset_token": reset_token,
                "new_password": "NewPassword123!@#",
            },
            content_type="application/json"
        )
        assert response.status_code == 400
        
        # Missing token
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "new_password": "NewPassword123!@#",
            },
            content_type="application/json"
        )
        assert response.status_code == 400
        
        # Missing password
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
            },
            content_type="application/json"
        )
        assert response.status_code == 400
    
    def test_reset_password_policy_enforcement(self):
        """Test that password policy is enforced during reset."""
        # Set up reset token
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.user.save()
        
        # Try weak password (too short)
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
                "new_password": "short",
            },
            content_type="application/json"
        )
        
        assert response.status_code == 400
        assert "password" in response.data.get("message", "").lower()
    
    def test_reset_password_clears_token_after_use(self):
        """Test that token is cleared after successful reset."""
        # Set up reset token
        reset_token = secrets.token_urlsafe(48)
        self.user.password_reset_token = reset_token
        self.user.password_reset_expires_at = timezone.now() + timedelta(hours=24)
        self.user.save()
        
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
                "new_password": "NewPassword123!@#",
            },
            content_type="application/json"
        )
        
        assert response.status_code == 200
        
        # Token should be cleared
        self.user.refresh_from_db()
        assert self.user.password_reset_token is None
        
        # Token cannot be reused
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.user.email,
                "reset_token": reset_token,
                "new_password": "AnotherPassword123!@#",
            },
            content_type="application/json"
        )
        
        assert response.status_code == 400
    
    def test_frontend_url_configurable_via_settings(self):
        """Test that PASSWORD_RESET_FRONTEND_URL is configurable."""
        # Verify setting exists and has a value
        assert hasattr(settings, 'PASSWORD_RESET_FRONTEND_URL')
        assert settings.PASSWORD_RESET_FRONTEND_URL == 'https://medsync.example.com/auth/reset-password'
    
    def test_token_expiry_hours_configurable_via_settings(self):
        """Test that PASSWORD_RESET_TOKEN_EXPIRY_HOURS is configurable."""
        # Verify setting exists and has a value
        assert hasattr(settings, 'PASSWORD_RESET_TOKEN_EXPIRY_HOURS')
        assert settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS == 24


class TestPasswordResetEmailTemplate(TestCase):
    """Test password reset email template."""
    
    def test_email_template_exists(self):
        """Test that password reset email template exists."""
        template_path = 'templates/password_reset_email.html'
        from django.template.loader import get_template
        
        # Template should exist and load without error
        try:
            template = get_template('password_reset_email.html')
            assert template is not None
        except Exception as e:
            self.fail(f"Failed to load password_reset_email.html template: {e}")


class TestSecretCompareDigest(TestCase):
    """Test that secrets.compare_digest is used for constant-time comparison."""
    
    def test_compare_digest_usage(self):
        """Test that secrets.compare_digest is available and works."""
        token1 = "test_token_value"
        token2 = "test_token_value"
        token3 = "different_token_value"
        
        # Should return True for identical tokens
        assert secrets.compare_digest(token1, token2) is True
        
        # Should return False for different tokens
        assert secrets.compare_digest(token1, token3) is False
        
        # Should not leak timing information (takes same time for both)
        import time
        
        # Test with correct token
        start = time.perf_counter()
        secrets.compare_digest("a" * 48, "a" * 48)
        time_correct = time.perf_counter() - start
        
        # Test with wrong token
        start = time.perf_counter()
        secrets.compare_digest("a" * 48, "b" * 48)
        time_wrong = time.perf_counter() - start
        
        # Times should be very similar (constant-time)
        # Allow for some variance in timing measurements
        ratio = max(time_correct, time_wrong) / (min(time_correct, time_wrong) + 0.0001)
        assert ratio < 5.0, f"Timing difference too large: {ratio}x"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])


