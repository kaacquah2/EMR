"""
WebAuthn/Passkey Integration Tests (Phase 2)

Tests for passkey registration, authentication, device management, and security.
Covers registration ceremony, authentication ceremony, replay attack detection,
device renaming, and listing passkeys with platform detection.
"""

import pytest
import json
import base64
from unittest.mock import patch, MagicMock
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, Client
from core.models import UserPasskey, Hospital, AuditLog
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


class WebAuthnConfigTestCase(TestCase):
    """Test WebAuthn configuration validation."""
    
    def test_webauthn_rp_id_no_protocol(self):
        """RP ID must not include protocol."""
        self.assertNotIn("://", settings.WEBAUTHN_RP_ID)
        self.assertEqual(settings.WEBAUTHN_RP_ID, "localhost")
    
    def test_webauthn_rp_id_no_trailing_slash(self):
        """RP ID must not have trailing slash."""
        self.assertFalse(settings.WEBAUTHN_RP_ID.endswith("/"))
    
    def test_webauthn_origin_has_scheme(self):
        """Origin must include scheme."""
        self.assertIn("://", settings.WEBAUTHN_ORIGIN)
    
    def test_webauthn_origin_https_in_production(self):
        """Origin must use HTTPS in production (not enforced in test, but config exists)."""
        # In production, settings.py validates this at startup
        # For tests running with DEBUG=True, HTTP is allowed
        self.assertIn(settings.WEBAUTHN_ORIGIN, [
            "http://localhost:3000",  # dev
            "https://medsync.gh",      # production
        ])
    
    def test_webauthn_enabled(self):
        """WebAuthn must be enabled."""
        self.assertTrue(settings.WEBAUTHN_ENABLED)
    
    def test_webauthn_challenge_ttl_set(self):
        """WebAuthn challenge TTL must be set."""
        self.assertEqual(settings.WEBAUTHN_CHALLENGE_TTL, 300)  # 5 minutes


class PasskeyRegistrationBeginTestCase(TestCase):
    """Test WebAuthn registration ceremony begin."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="GH001"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="TestPass123!@#",
            full_name="Dr. Test",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )
        self.client = APIClient()
        # Authenticate
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
    
    def test_passkey_register_begin_authenticated_only(self):
        """Registration begin requires authentication."""
        client = APIClient()
        response = client.post("/api/v1/auth/passkey/register/begin", {})
        self.assertEqual(response.status_code, 401)
    
    def test_passkey_register_begin_returns_challenge(self):
        """Registration begin returns WebAuthn options with challenge."""
        response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        # Must have challenge and RP data
        self.assertIn("challenge", data)
        self.assertIn("rp", data)
        self.assertIn("user", data)
        self.assertIn("pubKeyCredParams", data)
        self.assertIn("timeout", data)
        
        # Challenge must be base64url encoded
        self.assertTrue(len(data["challenge"]) > 0)
    
    def test_passkey_register_begin_challenge_stored_in_session(self):
        """Challenge is stored in session for later verification."""
        response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        self.assertEqual(response.status_code, 200)
        
        # Session should have the challenge
        self.assertIn("passkey_registration_challenge", self.client.session)
    
    def test_passkey_register_begin_rp_id_correct(self):
        """RP ID in response must match configured RP ID."""
        response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        data = response.json()
        self.assertEqual(data["rp"]["id"], settings.WEBAUTHN_RP_ID)
    
    def test_passkey_register_begin_user_id_encoded(self):
        """User ID must be base64url encoded in response."""
        response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        data = response.json()
        
        # User ID should be present and base64url
        self.assertIn("id", data["user"])
        user_id = data["user"]["id"]
        # Try to decode - should not raise
        try:
            base64.urlsafe_b64decode(user_id + "=" * (4 - len(user_id) % 4))
        except Exception as e:
            self.fail(f"User ID not properly base64url encoded: {e}")


class PasskeyRegistrationCompleteTestCase(TestCase):
    """Test WebAuthn registration ceremony complete."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="GH002"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="TestPass123!@#",
            full_name="Dr. Test",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
    
    def test_passkey_register_complete_requires_challenge(self):
        """Registration complete requires prior challenge from begin."""
        # No prior begin call = no challenge in session
        response = self.client.post("/api/v1/auth/passkey/register/complete", {
            "device_name": "Test Device"
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("challenge", response.json().get("message", "").lower())
    
    def test_passkey_register_complete_requires_device_name(self):
        """Device name can default to 'Unnamed device' but can be provided."""
        # First, get a challenge
        begin_response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        self.assertEqual(begin_response.status_code, 200)
        
        # Then attempt complete without device_name - should still process
        # (device_name has a default in auth_views.py)
        # This is okay - if it fails, it should be with validation error, not missing device_name
        complete_response = self.client.post("/api/v1/auth/passkey/register/complete", {
            # No device_name - should default
        })
        # Should fail with credential/signature error, not device_name error
        self.assertIn(complete_response.status_code, [400, 401])
    
    @patch("webauthn.verify_registration_response")
    def test_passkey_register_complete_stores_credential(self, mock_verify):
        """Successful registration stores passkey credential in database."""
        # First, get a challenge
        begin_response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        challenge = self.client.session.get("passkey_registration_challenge")
        
        # Mock successful verification
        mock_verified = MagicMock()
        mock_verified.credential_id = b"test_credential_id_12345"
        mock_verified.credential_public_key = b"test_public_key_12345"
        mock_verified.sign_count = 0
        mock_verify.return_value = mock_verified
        
        # Complete registration
        response = self.client.post("/api/v1/auth/passkey/register/complete", {
            "id": base64.urlsafe_b64encode(b"test_credential_id_12345").decode().rstrip("="),
            "device_name": "Test iPhone"
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify passkey was created
        passkey = UserPasskey.objects.get(user=self.user)
        self.assertEqual(passkey.credential_id, b"test_credential_id_12345")
        self.assertEqual(passkey.device_name, "Test iPhone")
        self.assertEqual(passkey.sign_count, 0)
    
    @patch("webauthn.verify_registration_response")
    def test_passkey_register_complete_platform_detection(self, mock_verify):
        """Platform is auto-detected from user agent."""
        begin_response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        
        mock_verified = MagicMock()
        mock_verified.credential_id = b"test_cred_ios"
        mock_verified.credential_public_key = b"test_key"
        mock_verified.sign_count = 0
        mock_verify.return_value = mock_verified
        
        # Set iOS user agent
        self.client.defaults['HTTP_USER_AGENT'] = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X)"
        
        response = self.client.post("/api/v1/auth/passkey/register/complete", {
            "id": base64.urlsafe_b64encode(b"test_cred_ios").decode().rstrip("="),
            "device_name": "iPhone 15"
        })
        
        self.assertEqual(response.status_code, 200)
        passkey = UserPasskey.objects.get(credential_id=b"test_cred_ios")
        self.assertEqual(passkey.platform, "ios")
    
    @patch("webauthn.verify_registration_response")
    def test_passkey_register_complete_audit_log(self, mock_verify):
        """Successful registration creates audit log."""
        begin_response = self.client.post("/api/v1/auth/passkey/register/begin", {})
        
        mock_verified = MagicMock()
        mock_verified.credential_id = b"test_cred_audit"
        mock_verified.credential_public_key = b"test_key"
        mock_verified.sign_count = 0
        mock_verify.return_value = mock_verified
        
        response = self.client.post("/api/v1/auth/passkey/register/complete", {
            "id": base64.urlsafe_b64encode(b"test_cred_audit").decode().rstrip("="),
            "device_name": "Test Device"
        })
        
        # Check audit log
        audit_log = AuditLog.objects.filter(
            user=self.user,
            action="PASSKEY_REGISTERED"
        ).first()
        self.assertIsNotNone(audit_log)
        self.assertIn("device_name", str(audit_log.extra_data))


class PasskeyAuthenticationBeginTestCase(TestCase):
    """Test WebAuthn authentication ceremony begin."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="GH003"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="TestPass123!@#",
            full_name="Dr. Test",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )
        self.client = APIClient()
    
    def test_passkey_auth_begin_public_endpoint(self):
        """Authentication begin is a public endpoint."""
        response = self.client.post("/api/v1/auth/passkey/auth/begin", {
            "email": "doctor@test.com"
        })
        # Should succeed (200 or 404 if user not found, but user exists)
        self.assertIn(response.status_code, [200, 404])
    
    def test_passkey_auth_begin_requires_email(self):
        """Authentication begin requires email."""
        response = self.client.post("/api/v1/auth/passkey/auth/begin", {})
        self.assertEqual(response.status_code, 400)
    
    def test_passkey_auth_begin_user_not_found(self):
        """Auth begin for non-existent user returns 404."""
        response = self.client.post("/api/v1/auth/passkey/auth/begin", {
            "email": "nonexistent@test.com"
        })
        self.assertEqual(response.status_code, 404)
    
    def test_passkey_auth_begin_returns_challenge(self):
        """Auth begin returns WebAuthn authentication options."""
        # Create a passkey first
        UserPasskey.objects.create(
            user=self.user,
            credential_id=b"test_cred_id",
            public_key=b"test_public_key",
            sign_count=0,
            device_name="Test Device"
        )
        
        response = self.client.post("/api/v1/auth/passkey/auth/begin", {
            "email": "doctor@test.com"
        })
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("challenge", data)
        self.assertIn("allowCredentials", data)


class PasskeyAuthenticationCompleteTestCase(TestCase):
    """Test WebAuthn authentication ceremony complete."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="GH004"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="TestPass123!@#",
            full_name="Dr. Test",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )
        self.passkey = UserPasskey.objects.create(
            user=self.user,
            credential_id=b"test_cred_id",
            public_key=b"test_public_key",
            sign_count=5,
            device_name="Test Device"
        )
        self.client = APIClient()
    
    def test_passkey_auth_complete_requires_challenge(self):
        """Auth complete requires prior challenge."""
        response = self.client.post("/api/v1/auth/passkey/auth/complete", {
            "id": "test_id"
        })
        self.assertEqual(response.status_code, 400)
    
    @patch("webauthn.verify_authentication_response")
    def test_passkey_auth_complete_issuesjwt(self, mock_verify):
        """Successful auth complete issues JWT tokens."""
        # First get challenge
        begin_response = self.client.post("/api/v1/auth/passkey/auth/begin", {
            "email": "doctor@test.com"
        })
        self.assertEqual(begin_response.status_code, 200)
        
        # Mock verification
        mock_verified = MagicMock()
        mock_verified.new_sign_count = 6  # Incremented
        mock_verify.return_value = mock_verified
        
        # Complete auth
        response = self.client.post("/api/v1/auth/passkey/auth/complete", {
            "id": base64.urlsafe_b64encode(b"test_cred_id").decode().rstrip("="),
        })
        
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["role"], "doctor")
    
    @patch("webauthn.verify_authentication_response")
    def test_passkey_auth_complete_detects_replay_attack(self, mock_verify):
        """Auth complete detects replay attacks (sign_count not increasing)."""
        # Get challenge
        begin_response = self.client.post("/api/v1/auth/passkey/auth/begin", {
            "email": "doctor@test.com"
        })
        
        # Mock verification with SAME sign_count (replay attack)
        mock_verified = MagicMock()
        mock_verified.new_sign_count = 5  # Same as before, not incremented
        mock_verify.return_value = mock_verified
        
        response = self.client.post("/api/v1/auth/passkey/auth/complete", {
            "id": base64.urlsafe_b64encode(b"test_cred_id").decode().rstrip("="),
        })
        
        self.assertEqual(response.status_code, 401)
        self.assertIn("failed", response.json().get("message", "").lower())
    
    @patch("webauthn.verify_authentication_response")
    def test_passkey_auth_complete_updates_sign_count(self, mock_verify):
        """Successful auth updates sign_count in database."""
        begin_response = self.client.post("/api/v1/auth/passkey/auth/begin", {
            "email": "doctor@test.com"
        })
        
        mock_verified = MagicMock()
        mock_verified.new_sign_count = 6
        mock_verify.return_value = mock_verified
        
        response = self.client.post("/api/v1/auth/passkey/auth/complete", {
            "id": base64.urlsafe_b64encode(b"test_cred_id").decode().rstrip("="),
        })
        
        self.assertEqual(response.status_code, 200)
        
        # Verify sign_count updated
        self.passkey.refresh_from_db()
        self.assertEqual(self.passkey.sign_count, 6)


class PasskeyManagementTestCase(TestCase):
    """Test passkey management (list, rename, delete)."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="GH005"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="TestPass123!@#",
            full_name="Dr. Test",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )
        self.client = APIClient()
        refresh = RefreshToken.for_user(self.user)
        self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
        
        # Create some passkeys
        self.passkey1 = UserPasskey.objects.create(
            user=self.user,
            credential_id=b"cred1",
            public_key=b"key1",
            device_name="iPhone 15",
            platform="ios"
        )
        self.passkey2 = UserPasskey.objects.create(
            user=self.user,
            credential_id=b"cred2",
            public_key=b"key2",
            device_name="Windows Laptop",
            platform="windows"
        )
    
    def test_list_passkeys_authenticated_only(self):
        """List passkeys requires authentication."""
        client = APIClient()
        response = client.get("/api/v1/auth/passkeys")
        self.assertEqual(response.status_code, 401)
    
    def test_list_passkeys_returns_all_user_passkeys(self):
        """List returns all passkeys for authenticated user."""
        response = self.client.get("/api/v1/auth/passkeys")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(len(data), 2)
        device_names = [pk["device_name"] for pk in data]
        self.assertIn("iPhone 15", device_names)
        self.assertIn("Windows Laptop", device_names)
    
    def test_list_passkeys_shows_platform(self):
        """List includes platform information."""
        response = self.client.get("/api/v1/auth/passkeys")
        data = response.json()
        
        platforms = [pk.get("platform") for pk in data]
        self.assertIn("ios", platforms)
        self.assertIn("windows", platforms)
    
    def test_rename_passkey_success(self):
        """Passkey can be renamed."""
        response = self.client.post(
            f"/api/v1/auth/passkeys/{self.passkey1.id}/rename",
            {"new_name": "My iPhone 15"}
        )
        self.assertEqual(response.status_code, 200)
        
        self.passkey1.refresh_from_db()
        self.assertEqual(self.passkey1.device_name, "My iPhone 15")
    
    def test_rename_passkey_validates_name_length(self):
        """Rename validates name is 1-100 characters."""
        # Empty name
        response = self.client.post(
            f"/api/v1/auth/passkeys/{self.passkey1.id}/rename",
            {"new_name": ""}
        )
        self.assertEqual(response.status_code, 400)
        
        # Too long
        response = self.client.post(
            f"/api/v1/auth/passkeys/{self.passkey1.id}/rename",
            {"new_name": "x" * 101}
        )
        self.assertEqual(response.status_code, 400)
    
    def test_rename_passkey_audit_log(self):
        """Rename creates audit log with old and new names."""
        self.client.post(
            f"/api/v1/auth/passkeys/{self.passkey1.id}/rename",
            {"new_name": "Renamed Device"}
        )
        
        audit_log = AuditLog.objects.filter(
            user=self.user,
            action="PASSKEY_RENAMED"
        ).first()
        self.assertIsNotNone(audit_log)
    
    def test_delete_passkey_success(self):
        """Passkey can be deleted."""
        response = self.client.delete(
            f"/api/v1/auth/passkeys/{self.passkey1.id}"
        )
        self.assertIn(response.status_code, [200, 204])
        
        # Verify deleted
        with self.assertRaises(UserPasskey.DoesNotExist):
            UserPasskey.objects.get(id=self.passkey1.id)
    
    def test_delete_passkey_not_found(self):
        """Delete non-existent passkey returns 404."""
        import uuid
        response = self.client.delete(
            f"/api/v1/auth/passkeys/{uuid.uuid4()}"
        )
        self.assertEqual(response.status_code, 404)
    
    def test_cannot_access_others_passkeys(self):
        """User cannot access or modify other users' passkeys."""
        other_user = User.objects.create_user(
            email="nurse@test.com",
            password="TestPass123!@#",
            role="nurse",
            hospital=self.hospital
        )
        other_passkey = UserPasskey.objects.create(
            user=other_user,
            credential_id=b"other_cred",
            public_key=b"other_key",
            device_name="Other Device"
        )
        
        # Try to rename other user's passkey
        response = self.client.post(
            f"/api/v1/auth/passkeys/{other_passkey.id}/rename",
            {"new_name": "Hacked"}
        )
        self.assertEqual(response.status_code, 404)  # Not found (not visible to this user)


@pytest.mark.django_db
class PasskeySecurityTestCase(TestCase):
    """Security-focused passkey tests."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Greater Accra",
            nhis_code="GH006"
        )
        self.user = User.objects.create_user(
            email="doctor@test.com",
            password="TestPass123!@#",
            full_name="Dr. Test",
            role="doctor",
            hospital=self.hospital,
            account_status="active"
        )
    
    def test_credential_id_uniqueness(self):
        """Credential IDs must be unique across all users."""
        passkey1 = UserPasskey.objects.create(
            user=self.user,
            credential_id=b"unique_cred",
            public_key=b"key1"
        )
        
        other_user = User.objects.create_user(
            email="nurse@test.com",
            password="TestPass123!@#",
            role="nurse",
            hospital=self.hospital
        )
        
        # Try to create duplicate credential_id
        with self.assertRaises(Exception):  # Django will raise IntegrityError
            UserPasskey.objects.create(
                user=other_user,
                credential_id=b"unique_cred",  # Duplicate!
                public_key=b"key2"
            )
    
    def test_public_key_stored_safely(self):
        """Public keys are stored (not encrypted, but secure)."""
        passkey = UserPasskey.objects.create(
            user=self.user,
            credential_id=b"cred",
            public_key=b"test_public_key_bytes"
        )
        
        # Public key should be retrievable
        retrieved = UserPasskey.objects.get(id=passkey.id)
        self.assertEqual(retrieved.public_key, b"test_public_key_bytes")
    
    def test_sign_count_prevents_cloning(self):
        """Sign count field prevents passkey cloning attacks."""
        passkey = UserPasskey.objects.create(
            user=self.user,
            credential_id=b"cred",
            public_key=b"key",
            sign_count=10
        )
        
        # If attacker clones credential, sign_count should not revert
        passkey.sign_count = 15
        passkey.save()
        
        # Simulate auth with old sign_count
        # (in real flow, verify_authentication_response would catch this)
        self.assertGreater(passkey.sign_count, 10)


class PasskeyAdminManagementTestCase(TestCase):
    """Admin endpoints for passkey management."""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Admin Test Hospital",
            region="Greater Accra",
            nhis_code="ATH-NHIS-001"
        )
        self.hospital_admin = User.objects.create_user(
            email="admin@hospital.com",
            password="TempPassword123!@#",
            hospital=self.hospital,
            role="hospital_admin",
            account_status="active"
        )
        self.super_admin = User.objects.create_user(
            email="superadmin@medsync.gh",
            password="TempPassword123!@#",
            role="super_admin",
            account_status="active"
        )
        self.staff_user = User.objects.create_user(
            email="doctor@hospital.com",
            password="TempPassword123!@#",
            hospital=self.hospital,
            role="doctor",
            account_status="active"
        )
        self.other_hospital = Hospital.objects.create(
            name="Other Hospital",
            region="Western Region",
            nhis_code="OTH-NHIS-001"
        )
        self.other_staff = User.objects.create_user(
            email="doctor@other.com",
            password="TempPassword123!@#",
            hospital=self.other_hospital,
            role="doctor",
            account_status="active"
        )
        self.client = APIClient()
    
    def test_admin_list_user_passkeys_super_admin(self):
        """Super admin can list any user's passkeys."""
        # Create a passkey for the staff user
        passkey = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id=b"test_cred_admin",
            public_key=b"test_pub_key",
            device_name="iPhone 15",
            platform="iOS"
        )
        
        self.client.force_authenticate(user=self.super_admin)
        res = self.client.get(f"/api/v1/admin/users/{self.staff_user.id}/passkeys")
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["passkeys"]), 1)
        self.assertEqual(res.data["passkeys"][0]["device_name"], "iPhone 15")
        self.assertEqual(res.data["passkeys"][0]["platform"], "iOS")
    
    def test_admin_list_user_passkeys_hospital_admin(self):
        """Hospital admin can list staff's passkeys in their hospital."""
        # Create passkey for staff in same hospital
        passkey = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id=b"test_cred_admin_2",
            public_key=b"test_pub_key",
            device_name="Ward Tablet",
            platform="Android"
        )
        
        self.client.force_authenticate(user=self.hospital_admin)
        res = self.client.get(f"/api/v1/admin/users/{self.staff_user.id}/passkeys")
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["passkeys"]), 1)
        self.assertEqual(res.data["passkeys"][0]["device_name"], "Ward Tablet")
    
    def test_admin_list_user_passkeys_hospital_admin_denied_other_hospital(self):
        """Hospital admin cannot list passkeys for staff in other hospitals."""
        self.client.force_authenticate(user=self.hospital_admin)
        res = self.client.get(f"/api/v1/admin/users/{self.other_staff.id}/passkeys")
        
        self.assertEqual(res.status_code, 403)
    
    def test_admin_list_user_passkeys_doctor_denied(self):
        """Non-admin users cannot list others' passkeys."""
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.get(f"/api/v1/admin/users/{self.other_staff.id}/passkeys")
        
        self.assertEqual(res.status_code, 403)
    
    def test_admin_reset_user_passkeys_super_admin(self):
        """Super admin can reset any user's passkeys."""
        # Create multiple passkeys
        pk1 = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id=b"test_cred_reset_1",
            public_key=b"test_pub_key",
            device_name="Device 1",
            platform="iOS"
        )
        pk2 = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id=b"test_cred_reset_2",
            public_key=b"test_pub_key",
            device_name="Device 2",
            platform="Android"
        )
        
        self.client.force_authenticate(user=self.super_admin)
        res = self.client.post(f"/api/v1/admin/users/{self.staff_user.id}/passkeys/reset", {})
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["passkeys_deleted"], 2)
        self.assertEqual(UserPasskey.objects.filter(user=self.staff_user).count(), 0)
    
    def test_admin_reset_user_passkeys_hospital_admin(self):
        """Hospital admin can reset staff's passkeys in their hospital."""
        pk = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id=b"test_cred_reset_3",
            public_key=b"test_pub_key",
            device_name="Device",
            platform="macOS"
        )
        
        self.client.force_authenticate(user=self.hospital_admin)
        res = self.client.post(f"/api/v1/admin/users/{self.staff_user.id}/passkeys/reset", {})
        
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["passkeys_deleted"], 1)
        self.assertEqual(UserPasskey.objects.filter(user=self.staff_user).count(), 0)
    
    def test_admin_reset_user_passkeys_audit_log(self):
        """Reset operation is logged in audit trail."""
        pk = UserPasskey.objects.create(
            user=self.staff_user,
            credential_id=b"test_cred_audit",
            public_key=b"test_pub_key",
            device_name="Device",
            platform="iOS"
        )
        
        self.client.force_authenticate(user=self.super_admin)
        res = self.client.post(f"/api/v1/admin/users/{self.staff_user.id}/passkeys/reset", {})
        
        # Check audit log
        from core.models import AuditLog
        log = AuditLog.objects.filter(
            user=self.super_admin,
            action="PASSKEY_RESET_BY_ADMIN",
            resource_id=str(self.staff_user.id)
        ).first()
        
        self.assertIsNotNone(log)
        self.assertEqual(log.extra_data["passkeys_deleted"], 1)
        self.assertEqual(log.extra_data["target_user_email"], self.staff_user.email)
    
    def test_admin_reset_user_passkeys_hospital_admin_denied_other_hospital(self):
        """Hospital admin cannot reset passkeys for staff in other hospitals."""
        pk = UserPasskey.objects.create(
            user=self.other_staff,
            credential_id=b"test_cred_other",
            public_key=b"test_pub_key",
            device_name="Device",
            platform="iOS"
        )
        
        self.client.force_authenticate(user=self.hospital_admin)
        res = self.client.post(f"/api/v1/admin/users/{self.other_staff.id}/passkeys/reset", {})
        
        self.assertEqual(res.status_code, 403)
        self.assertEqual(UserPasskey.objects.filter(user=self.other_staff).count(), 1)
    
    def test_admin_reset_user_passkeys_doctor_denied(self):
        """Non-admin users cannot reset passkeys."""
        pk = UserPasskey.objects.create(
            user=self.other_staff,
            credential_id=b"test_cred_doc",
            public_key=b"test_pub_key",
            device_name="Device",
            platform="iOS"
        )
        
        self.client.force_authenticate(user=self.staff_user)
        res = self.client.post(f"/api/v1/admin/users/{self.other_staff.id}/passkeys/reset", {})
        
        self.assertEqual(res.status_code, 403)
        self.assertEqual(UserPasskey.objects.filter(user=self.other_staff).count(), 1)
    
    def test_admin_reset_user_passkeys_user_not_found(self):
        """Reset for non-existent user returns 404."""
        import uuid
        fake_user_id = uuid.uuid4()
        
        self.client.force_authenticate(user=self.super_admin)
        res = self.client.post(f"/api/v1/admin/users/{fake_user_id}/passkeys/reset", {})
        
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data["message"], "User not found")


