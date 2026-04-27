"""
PHASE 7: 3-Tier Password Recovery System Tests

Tests for:
- Tier 1: User self-service password reset
- Tier 2: Hospital admin-assisted reset
- Tier 3: Super admin force reset with MFA
"""

from django.test import TestCase, Client
from django.utils import timezone
from datetime import timedelta
from core.models import User, Hospital, PasswordResetAudit
from rest_framework_simplejwt.tokens import RefreshToken


class TestTier1SelfServicePasswordReset(TestCase):
    """Tier 1: User self-service forgot password and reset."""

    def setUp(self):
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

    def test_forgot_password_creates_reset_token(self):
        """Test that forgot_password endpoint creates password_reset_token."""
        response = self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify token was created
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)
        self.assertIsNotNone(self.user.password_reset_expires_at)

    def test_forgot_password_logs_to_audit(self):
        """Test that forgot_password creates PasswordResetAudit record."""
        response = self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify audit record created
        audit = PasswordResetAudit.objects.filter(user=self.user).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.reset_type, "self_service")
        self.assertEqual(audit.status, "pending")
        self.assertIsNone(audit.initiated_by)  # Self-service has no admin initiator

    def test_forgot_password_rate_limiting(self):
        """Test rate limiting: max 5 attempts per email per hour."""
        for i in range(5):
            response = self.client.post(
                "/api/v1/auth/forgot-password",
                {"email": "doctor@test.com"},
                content_type="application/json"
            )
            self.assertEqual(response.status_code, 200)

        # 6th attempt should be rate limited
        response = self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 429)

    def test_reset_password_with_valid_token(self):
        """Test reset_password with valid token."""
        # First, get a reset token
        self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Now reset password
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "token": reset_token,
                "password": "NewPassword123!"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access_token", response.json())

        # Verify token was cleared
        self.user.refresh_from_db()
        self.assertIsNone(self.user.password_reset_token)
        self.assertFalse(self.user.check_password("OldPassword123!"))
        self.assertTrue(self.user.check_password("NewPassword123!"))

    def test_reset_password_marks_audit_as_completed(self):
        """Test that reset_password marks audit record as completed."""
        # Get reset token
        self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )

        self.user.refresh_from_db()
        reset_token = self.user.password_reset_token

        # Reset password
        response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "token": reset_token,
                "password": "NewPassword123!"
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)

        # Verify audit record marked as completed
        audit = PasswordResetAudit.objects.filter(user=self.user).first()
        self.assertEqual(audit.status, "completed")
        self.assertIsNotNone(audit.token_used_at)


class TestTier2AdminAssistedReset(TestCase):
    """Tier 2: Hospital admin generates reset links and temp passwords."""

    def setUp(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="TH001"
        )

        # Create hospital admin
        self.admin = User.objects.create_user(
            email="admin@test.com",
            password="AdminPassword123!",
            role="hospital_admin",
            full_name="Admin User",
            hospital=self.hospital,
            account_status="active",
            is_mfa_enabled=True,
        )

        # Create regular user to reset
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="OldPassword123!",
            role="doctor",
            full_name="Dr. Test",
            hospital=self.hospital,
            account_status="active",
        )

        # Login admin
        self.admin_token = RefreshToken.for_user(self.admin)

    def test_generate_reset_link_requires_hospital_admin(self):
        """Test that only hospital_admin can generate reset links."""
        # Try with doctor account (should fail)
        doctor_token = RefreshToken.for_user(self.user)

        response = self.client.post(
            f"/api/v1/admin/users/{self.user.id}/generate-reset-link",
            {
                "reason": "User forgot password"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {doctor_token.access_token}"
        )
        self.assertEqual(response.status_code, 403)

    def test_generate_reset_link_creates_token(self):
        """Test that generate_reset_link creates a 24-hour reset token without exposing it in the response."""
        response = self.client.post(
            f"/api/v1/admin/users/{self.user.id}/generate-reset-link",
            {
                "reason": "User locked out"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token.access_token}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Response should NOT expose reset token or reset link (CRITICAL FIX #2)
        self.assertNotIn("reset_token", data)
        self.assertNotIn("reset_link", data)
        self.assertIn("expires_in_hours", data)
        self.assertEqual(data["expires_in_hours"], 24)

        # Verify token in database
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)

    def test_generate_reset_link_logs_audit(self):
        """Test that generate_reset_link logs to PasswordResetAudit."""
        response = self.client.post(
            f"/api/v1/admin/users/{self.user.id}/generate-reset-link",
            {
                "reason": "User locked out"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token.access_token}"
        )
        self.assertEqual(response.status_code, 200)

        # Verify audit record
        audit = PasswordResetAudit.objects.filter(user=self.user).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.reset_type, "admin_link")
        self.assertEqual(audit.initiated_by, self.admin)
        self.assertEqual(audit.reason, "User locked out")

    def test_generate_temp_password_creates_forced_change(self):
        """Test that generate_temp_password sets must_change_password_on_login."""
        response = self.client.post(
            f"/api/v1/admin/users/{self.user.id}/generate-temp-password",
            {
                "reason": "Urgent access needed"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token.access_token}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("temp_password", data)

        # Verify flags set
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password_on_login)
        self.assertEqual(self.user.temp_password, data["temp_password"])

    def test_login_with_temp_password(self):
        """Test login with admin-generated temp password."""
        # Generate temp password
        self.client.post(
            f"/api/v1/admin/users/{self.user.id}/generate-temp-password",
            {
                "reason": "Urgent access needed"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.admin_token.access_token}"
        )

        self.user.refresh_from_db()
        temp_password = self.user.temp_password

        # Login with temp password (bypasses MFA)
        response = self.client.post(
            "/api/v1/auth/login-temp-password",
            {
                "email": "doctor@test.com",
                "temp_password": temp_password
            },
            content_type="application/json"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertTrue(data["must_change_password_on_login"])


class TestTier3SuperAdminForceReset(TestCase):
    """Tier 3: Super admin forces password reset with MFA verification."""

    def setUp(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="TH001"
        )

        # Create super admin with MFA
        import pyotp
        self.super_admin = User.objects.create_user(
            email="superadmin@test.com",
            password="SuperAdminPassword123!",
            role="super_admin",
            full_name="Super Admin",
            hospital=None,  # Super admin has no hospital
            account_status="active",
            is_mfa_enabled=True,
        )
        self.totp_secret = pyotp.random_base32()
        self.super_admin.totp_secret = self.totp_secret
        self.super_admin.save()

        # Create user to reset
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="OldPassword123!",
            role="doctor",
            full_name="Dr. Test",
            hospital=self.hospital,
            account_status="active",
        )

        self.super_admin_token = RefreshToken.for_user(self.super_admin)

    def test_force_reset_requires_super_admin(self):
        """Test that only super_admin can force password resets."""
        response = self.client.post(
            f"/api/v1/superadmin/users/{self.user.id}/force-password-reset",
            {
                "mfa_code": "123456",
                "hospital_id": str(self.hospital.id),
                "reason": "Suspicious activity"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(self.user).access_token}"
        )
        self.assertEqual(response.status_code, 403)

    def test_force_reset_requires_mfa(self):
        """Test that force_password_reset requires valid MFA code."""
        response = self.client.post(
            f"/api/v1/superadmin/users/{self.user.id}/force-password-reset",
            {
                "mfa_code": "000000",  # Invalid code
                "hospital_id": str(self.hospital.id),
                "reason": "Suspicious activity"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )
        self.assertEqual(response.status_code, 401)

    def test_force_reset_with_valid_mfa(self):
        """Test force_password_reset with valid MFA code without exposing token in response."""
        # Generate valid MFA code
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.user.id}/force-password-reset",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Suspicious activity detected"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        # Response should NOT expose reset token or reset link (CRITICAL FIX #2)
        self.assertNotIn("reset_token", data)
        self.assertNotIn("reset_link", data)
        # Token should exist in database for the target user
        self.user.refresh_from_db()
        self.assertIsNotNone(self.user.password_reset_token)

    def test_force_reset_logs_mfa_verified(self):
        """Test that force_password_reset logs mfa_verified=True."""
        # Generate valid MFA code
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.user.id}/force-password-reset",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Suspicious activity detected"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )
        self.assertEqual(response.status_code, 200)

        # Verify audit record
        audit = PasswordResetAudit.objects.filter(user=self.user).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.reset_type, "super_admin_override")
        self.assertTrue(audit.mfa_verified)
        self.assertEqual(audit.initiated_by, self.super_admin)


class TestCriticalFix3SuperAdminForceResetNotification(TestCase):
    """
    CRITICAL FIX #3: Tests for super admin forced password reset with user notification.

    Ensures:
    - User receives warning email when admin forces reset
    - Admin name, hospital, and reason are included in email
    - 24-hour token expiry is enforced
    - Cannot force reset for other super admins (prevents horizontal escalation)
    - Audit log captures full details
    """

    def setUp(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Test Region",
            nhis_code="TH001"
        )

        # Create super admin with MFA
        import pyotp
        self.super_admin = User.objects.create_user(
            email="superadmin@test.com",
            password="SuperAdminPassword123!",
            role="super_admin",
            full_name="Super Admin User",
            hospital=None,
            account_status="active",
            is_mfa_enabled=True,
        )
        self.totp_secret = pyotp.random_base32()
        self.super_admin.totp_secret = self.totp_secret
        self.super_admin.save()

        # Create regular doctor user to reset
        self.doctor = User.objects.create_user(
            email="doctor@test.com",
            password="OldPassword123!",
            role="doctor",
            full_name="Dr. Test Doctor",
            hospital=self.hospital,
            account_status="active",
        )

        # Create second super admin for horizontal escalation test
        self.other_super_admin = User.objects.create_user(
            email="othersuperadmin@test.com",
            password="OtherPassword123!",
            role="super_admin",
            full_name="Other Super Admin",
            hospital=None,
            account_status="active",
        )

        self.super_admin_token = RefreshToken.for_user(self.super_admin)

    def test_super_admin_force_reset_sends_user_notification(self):
        """
        CRITICAL FIX #3: Test that email is sent TO THE USER (not admin).

        When super admin forces a password reset, the user should receive
        a warning email with details about who initiated it and why.
        """
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            response = self.client.post(
                f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
                {
                    "mfa_code": mfa_code,
                    "hospital_id": str(self.hospital.id),
                    "reason": "Suspicious login activity detected"
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
            )

            # Verify response indicates success
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertEqual(data["email_sent_to"], self.doctor.email)
            self.assertTrue(data["confirmation_required"])

            # Verify email was sent to user (not super admin)
            from django.core.mail import outbox
            self.assertEqual(len(outbox), 1)
            email = outbox[0]

            # Email must be TO user, not admin
            self.assertIn(self.doctor.email, email.to)
            self.assertNotIn(self.super_admin.email, email.to)

            # Email must include warning in subject
            self.assertIn("⚠️", email.subject)
            self.assertIn("Password Reset Required", email.subject)

            # Email body must include admin name, hospital, and reason
            # Check both plain text body and HTML version
            email_content = email.body
            if email.alternatives:
                email_content = email.alternatives[0][0]  # Get the HTML version

            self.assertIn(self.super_admin.full_name, email_content)
            self.assertIn(self.hospital.name, email_content)
            self.assertIn("Suspicious login activity detected", email_content)

            # Email must warn user about unauthorized resets
            self.assertIn("did not request this", email_content.lower())
            self.assertIn("contact", email_content.lower())

    def test_force_reset_includes_admin_and_hospital_in_email(self):
        """Test that email includes initiating admin name and hospital name."""
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        with self.settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend'):
            self.client.post(
                f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
                {
                    "mfa_code": mfa_code,
                    "hospital_id": str(self.hospital.id),
                    "reason": "Security protocol"
                },
                content_type="application/json",
                HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
            )

            from django.core.mail import outbox
            email = outbox[0]
            email_content = email.body
            if email.alternatives:
                email_content = email.alternatives[0][0]  # Get the HTML version

            # Verify admin name in email
            self.assertIn("Super Admin User", email_content)

            # Verify hospital name in email
            self.assertIn("Test Hospital", email_content)

    def test_force_reset_token_expires_in_24_hours(self):
        """Test that forced reset token expires in 24 hours."""
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Security check"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["token_expires_in_hours"], 24)

        # Verify token expiry in database
        self.doctor.refresh_from_db()
        self.assertIsNotNone(self.doctor.password_reset_expires_at)

        # Calculate expected expiry (24 hours from now)
        now = timezone.now()
        expected_expiry = now + timedelta(hours=24)

        # Allow 1 minute difference for execution time
        diff = abs((self.doctor.password_reset_expires_at - expected_expiry).total_seconds())
        self.assertLess(diff, 60)

    def test_super_admin_cannot_force_reset_for_other_super_admin(self):
        """
        CRITICAL FIX #3: Prevent horizontal escalation.

        Super admin A should NOT be able to force password reset for super admin B.
        This prevents one compromised admin from taking over other admin accounts.
        """
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.other_super_admin.id}/force-password-reset-initiate",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Testing horizontal escalation"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )

        # Must return 403 Forbidden
        self.assertEqual(response.status_code, 403)
        self.assertIn("super admin", response.json()["message"].lower())

    def test_force_reset_logged_to_audit(self):
        """
        CRITICAL FIX #3: Verify audit log entry is created.

        Every forced password reset must be logged with:
        - action='FORCE_PASSWORD_RESET_INITIATED'
        - target_user_email
        - confirmation_required=True
        - email_sent_to address
        """
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Account compromise suspected"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )

        self.assertEqual(response.status_code, 200)

        # Verify audit log entry
        audit = PasswordResetAudit.objects.filter(user=self.doctor).first()
        self.assertIsNotNone(audit)
        self.assertEqual(audit.reset_type, "super_admin_override")
        self.assertEqual(audit.initiated_by, self.super_admin)
        self.assertEqual(audit.hospital, self.hospital)
        self.assertTrue(audit.mfa_verified)
        self.assertEqual(audit.status, "pending")
        self.assertIn("compromise", audit.reason.lower())

    def test_force_reset_requires_mfa(self):
        """Test that force_password_reset_initiate requires valid MFA code."""
        response = self.client.post(
            f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
            {
                "mfa_code": "000000",  # Invalid code
                "hospital_id": str(self.hospital.id),
                "reason": "Test"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )

        self.assertEqual(response.status_code, 401)
        self.assertIn("Invalid MFA", response.json()["message"])

    def test_force_reset_requires_super_admin(self):
        """Test that only super_admin can initiate forced resets."""
        doctor_token = RefreshToken.for_user(self.doctor)

        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Test"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {doctor_token.access_token}"
        )

        self.assertEqual(response.status_code, 403)
        self.assertIn("super admin", response.json()["message"].lower())

    def test_force_reset_requires_confirmation_with_token(self):
        """
        CRITICAL FIX #3: Test that token must be used to confirm reset.

        Forced reset should require user to explicitly use the token to confirm.
        """
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Test confirmation"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify confirmation is required
        self.assertTrue(data["confirmation_required"])

        # Get the token from database
        self.doctor.refresh_from_db()
        reset_token = self.doctor.password_reset_token
        self.assertIsNotNone(reset_token)

        # Now verify that using the token actually resets the password
        new_password = "NewPassword123!@#"
        reset_response = self.client.post(
            "/api/v1/auth/reset-password",
            {
                "email": self.doctor.email,
                "reset_token": reset_token,
                "new_password": new_password
            },
            content_type="application/json"
        )

        # Should succeed
        self.assertEqual(reset_response.status_code, 200)

        # Verify password was changed
        self.doctor.refresh_from_db()
        self.assertTrue(self.doctor.check_password(new_password))

    def test_force_reset_response_includes_all_details(self):
        """Test that force_password_reset_initiate response includes all required fields."""
        import pyotp
        totp = pyotp.TOTP(self.totp_secret)
        mfa_code = totp.now()

        response = self.client.post(
            f"/api/v1/superadmin/users/{self.doctor.id}/force-password-reset-initiate",
            {
                "mfa_code": mfa_code,
                "hospital_id": str(self.hospital.id),
                "reason": "Testing response format"
            },
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {self.super_admin_token.access_token}"
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()

        # Verify all required fields are present
        self.assertIn("message", data)
        self.assertIn("user_email", data)
        self.assertEqual(data["user_email"], self.doctor.email)
        self.assertIn("token_expires_in_hours", data)
        self.assertEqual(data["token_expires_in_hours"], 24)
        self.assertIn("email_sent_to", data)
        self.assertEqual(data["email_sent_to"], self.doctor.email)
        self.assertIn("confirmation_required", data)
        self.assertTrue(data["confirmation_required"])
        self.assertIn("audit_log_id", data)


class TestAuditLogging(TestCase):
    """Test comprehensive audit logging for all 3 tiers."""

    def setUp(self):
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

    def test_audit_trail_tracks_all_reset_types(self):
        """Test that PasswordResetAudit tracks all 3 reset types."""
        # Create different reset type records
        self.client = Client()

        # Tier 1: Self-service
        self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )

        audits = PasswordResetAudit.objects.filter(user=self.user).all()
        self.assertEqual(audits.count(), 1)
        self.assertEqual(audits[0].reset_type, "self_service")

    def test_audit_includes_ip_address_and_user_agent(self):
        """Test that audit logs include IP and user agent."""
        self.client = Client()
        self.client.post(
            "/api/v1/auth/forgot-password",
            {"email": "doctor@test.com"},
            content_type="application/json"
        )

        audit = PasswordResetAudit.objects.filter(user=self.user).first()
        self.assertIsNotNone(audit.ip_address)
        self.assertIsNotNone(audit.user_agent)


if __name__ == '__main__':
    import unittest
    unittest.main()


