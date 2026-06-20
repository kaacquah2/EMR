"""
PHASE 3: HttpOnly Cookie-Based Authentication Tests

Tests for:
- ClientCookie model lifecycle (creation, expiry, revocation)
- JWT encryption/decryption
- Cookie endpoint (refresh, logout, CSRF)
- Device fingerprinting with cookies
- CSRF token validation
"""

import hashlib
import json
import pytest
from unittest import TestCase
from unittest.mock import patch
from datetime import timedelta
from django.test import TestCase as DjangoTestCase, Client
from django.utils import timezone
from django.conf import settings
from rest_framework.test import APITestCase
from rest_framework import status
from core.models import ClientCookie, User, Hospital, AuditLog, TrustedDevice
from api.encryption import encrypt_jwt, decrypt_jwt
from api.auth_utils import compute_device_fingerprint
from api.utils import audit_log
from rest_framework_simplejwt.tokens import RefreshToken


@pytest.mark.skip(reason="Phase 3 cookie auth not yet deployed on frontend")
class ClientCookieModelTests(DjangoTestCase):
    """Test ClientCookie model functionality"""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Central",
            nhis_code="TH001",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="Password123!@#",
            hospital=self.hospital,
            role="doctor",
        )
    
    def test_client_cookie_creation(self):
        """Test ClientCookie can be created and stored"""
        access_token = "test.access.token"
        refresh_token = "test.refresh.token"
        
        encrypted_access = encrypt_jwt(access_token)
        encrypted_refresh = encrypt_jwt(refresh_token)
        
        cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token=hashlib.sha256(b"cookie_value").hexdigest(),
            access_token_jwt=encrypted_access,
            refresh_token_jwt=encrypted_refresh,
            device_fingerprint="device123",
            client_metadata={"user_agent": "Chrome", "ip_addr": "127.0.0.1"},
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        self.assertEqual(cookie.user, self.user)
        self.assertFalse(cookie.is_revoked)
        self.assertIsNotNone(cookie.created_at)
    
    def test_client_cookie_expiry_check(self):
        """Test ClientCookie expiry detection"""
        # Expired cookie
        expired_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="expired123",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            expires_at=timezone.now() - timedelta(minutes=1),
        )
        
        # Active cookie
        active_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="active123",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        self.assertTrue(expired_cookie.is_expired)
        self.assertFalse(active_cookie.is_expired)
    
    def test_client_cookie_revocation(self):
        """Test ClientCookie soft-delete revocation"""
        cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="revoke123",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        self.assertFalse(cookie.is_revoked)
        
        # Revoke
        cookie.is_revoked = True
        cookie.save()
        
        cookie.refresh_from_db()
        self.assertTrue(cookie.is_revoked)


class EncryptionTests(TestCase):
    """Test JWT encryption/decryption"""
    
    def test_encrypt_decrypt_jwt(self):
        """Test encryption and decryption roundtrip"""
        original_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.payload"
        
        encrypted = encrypt_jwt(original_token)
        self.assertNotEqual(encrypted, original_token)
        
        decrypted = decrypt_jwt(encrypted)
        self.assertEqual(decrypted, original_token)
    
    def test_encrypt_different_each_time(self):
        """Test that Fernet produces different ciphertext each time"""
        token = "test.token.here"
        
        encrypted1 = encrypt_jwt(token)
        encrypted2 = encrypt_jwt(token)
        
        # Different ciphertexts due to Fernet's IV
        self.assertNotEqual(encrypted1, encrypted2)
        
        # But both decrypt to same plaintext
        self.assertEqual(decrypt_jwt(encrypted1), token)
        self.assertEqual(decrypt_jwt(encrypted2), token)
    
    def test_decrypt_invalid_token_raises(self):
        """Test that decrypting invalid token raises exception"""
        with self.assertRaises(ValueError):
            decrypt_jwt("invalid.ciphertext.here")


class CookieAuthEndpointTests(APITestCase):
    """Test cookie-based authentication endpoints"""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Central",
            nhis_code="TH001",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="Password123!@#",
            hospital=self.hospital,
            role="doctor",
            is_mfa_enabled=False,  # Skip MFA for simplicity
        )
    
    def test_refresh_cookie_endpoint_requires_auth(self):
        """Test that refresh-cookie endpoint requires authentication"""
        response = self.client.post('/api/v1/auth/refresh-cookie')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_logout_cookie_endpoint_requires_auth(self):
        """Test that logout-cookie endpoint requires authentication"""
        response = self.client.post('/api/v1/auth/logout-cookie')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_csrf_token_endpoint_requires_auth(self):
        """Test that CSRF token endpoint requires authentication"""
        response = self.client.post('/api/v1/auth/csrf-token')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_refresh_cookie_with_valid_session(self):
        """Test refreshing access token via cookie"""
        # Create a valid ClientCookie session
        refresh_token = RefreshToken.for_user(self.user)
        access_jwt = str(refresh_token.access_token)
        refresh_jwt = str(refresh_token)
        
        cookie_token = "test_cookie_123"
        cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
        
        client_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token=cookie_hash,
            access_token_jwt=encrypt_jwt(access_jwt),
            refresh_token_jwt=encrypt_jwt(refresh_jwt),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        # Login as user with cookie
        self.client.force_authenticate(user=self.user)
        
        # Make request with cookie
        response = self.client.post(
            '/api/v1/auth/refresh-cookie',
            HTTP_COOKIE=f'medsync_session={cookie_token}'
        )
        
        # Should return 200 and new cookie in response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('expires_in', response.json())
        latest_audit = AuditLog.objects.filter(action="TOKEN_REFRESH").latest("timestamp")
        self.assertEqual(latest_audit.risk_tier, 2)
        self.assertEqual(latest_audit.mfa_method, "email_otp")
    
    def test_logout_cookie_revokes_session(self):
        """Test that logout revokes ClientCookie"""
        cookie_token = "logout_test_123"
        cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
        
        client_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token=cookie_hash,
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        self.assertFalse(client_cookie.is_revoked)
        
        # Logout
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            '/api/v1/auth/logout-cookie',
            HTTP_COOKIE=f'medsync_session={cookie_token}'
        )
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify cookie is revoked
        client_cookie.refresh_from_db()
        self.assertTrue(client_cookie.is_revoked)
    
    def test_csrf_token_endpoint_returns_token(self):
        """Test CSRF token endpoint returns valid token"""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.post('/api/v1/auth/csrf-token')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('csrf_token', response.json())
        self.assertIn('header_name', response.json())
        self.assertEqual(response.json()['header_name'], 'X-CSRFToken')

    def test_login_sets_httponly_cookie_and_audit_context(self):
        """Test trusted login sets the HttpOnly cookie and records auth context"""
        hospital = Hospital.objects.create(
            name="Cookie Login Hospital",
            region="Central",
            nhis_code="CLH001",
            ip_subnets=["192.168.10.0/24"],
        )
        user = User.objects.create_user(
            email="cookie-login@test.gh",
            password="Password123!@#",
            hospital=hospital,
            role="nurse",
        )
        from django.test import RequestFactory

        factory = RequestFactory()
        fingerprint_request = factory.post(
            '/api/v1/auth/login',
            {
                'screen_resolution': '1920x1080',
                'timezone': 'Africa/Accra',
            },
            content_type='application/json',
        )
        fingerprint_request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        fingerprint_request.META['REMOTE_ADDR'] = '192.168.10.25'
        fingerprint_request.data = {
            'screen_resolution': '1920x1080',
            'timezone': 'Africa/Accra',
        }
        TrustedDevice.objects.create(
            user=user,
            device_fingerprint=compute_device_fingerprint(fingerprint_request),
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30),
        )

        with patch("api.auth_utils.is_within_business_hours", return_value=True):
            response = self.client.post(
                '/api/v1/auth/login',
                {
                    'email': user.email,
                    'password': 'Password123!@#',
                    'screen_resolution': '1920x1080',
                    'timezone': 'Africa/Accra',
                },
                format='json',
                HTTP_USER_AGENT='Mozilla/5.0 Test Browser',
                REMOTE_ADDR='192.168.10.25',
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('medsync_session', response.cookies)
        self.assertTrue(response.cookies['medsync_session']['httponly'])
        # LOGIN_SUCCESS was renamed to LOGIN (the valid AuditLog.ACTIONS value).
        latest_audit = AuditLog.objects.filter(action="LOGIN").latest("timestamp")
        self.assertEqual(latest_audit.risk_tier, 1)
        self.assertEqual(latest_audit.mfa_method, "none")


class CookieSecurityTests(DjangoTestCase):
    """Test security properties of cookie-based auth"""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Central",
            nhis_code="TH001",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="Password123!@#",
            hospital=self.hospital,
            role="doctor",
        )
    
    def test_cookie_token_is_opaque(self):
        """Test that cookie_token is opaque hash, not JWT"""
        refresh = RefreshToken.for_user(self.user)
        access_jwt = str(refresh.access_token)
        
        cookie_token = "opaque_test_123"
        cookie_hash = hashlib.sha256(cookie_token.encode()).hexdigest()
        
        client_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token=cookie_hash,
            access_token_jwt=encrypt_jwt(access_jwt),
            refresh_token_jwt=encrypt_jwt(str(refresh)),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        # Cookie token is hash, not JWT
        self.assertFalse("." in client_cookie.cookie_token)  # No JWT structure
        self.assertEqual(len(client_cookie.cookie_token), 64)  # SHA256 hex length
    
    def test_jwt_encrypted_in_database(self):
        """Test that JWTs are encrypted when stored"""
        refresh = RefreshToken.for_user(self.user)
        access_jwt = str(refresh.access_token)
        
        client_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="test123",
            access_token_jwt=encrypt_jwt(access_jwt),
            refresh_token_jwt=encrypt_jwt(str(refresh)),
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        # Stored value is encrypted (not plain JWT)
        self.assertNotEqual(client_cookie.access_token_jwt, access_jwt)
        self.assertNotIn(".", client_cookie.access_token_jwt)  # No JWT structure visible
    
    def test_expired_cookie_not_valid(self):
        """Test that expired cookies cannot be used"""
        expired_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="expired123",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            expires_at=timezone.now() - timedelta(seconds=1),  # Expired
        )
        
        # Verify it's considered expired
        self.assertTrue(expired_cookie.is_expired)
        
        # Query should not find it
        found = ClientCookie.objects.filter(
            cookie_token=expired_cookie.cookie_token,
            is_revoked=False,
            expires_at__gt=timezone.now()
        ).exists()
        
        self.assertFalse(found)
    
    def test_revoked_cookie_not_valid(self):
        """Test that revoked cookies cannot be used"""
        revoked_cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="revoked123",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            is_revoked=True,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        # Query should not find revoked cookies
        found = ClientCookie.objects.filter(
            cookie_token=revoked_cookie.cookie_token,
            is_revoked=False,
        ).exists()
        
        self.assertFalse(found)

    def test_audit_log_records_step_up_context(self):
        """Step-up actions should record tier 3 and the step-up action name."""
        from django.test import RequestFactory

        factory = RequestFactory()
        request = factory.post('/api/v1/cross-facility-records/1')
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        request.META['REMOTE_ADDR'] = '127.0.0.1'
        request.auth = {"risk_tier": 2, "mfa_method": "email_otp"}
        request.step_up_jwt_payload = {"step_up_action": "cross_facility_access"}

        audit_log(
            self.user,
            "VIEW_CROSS_FACILITY_RECORD",
            request=request,
            extra_data={"patient_id": "1"},
        )

        entry = AuditLog.objects.latest("timestamp")
        self.assertEqual(entry.risk_tier, 3)
        self.assertEqual(entry.mfa_method, "step_up")
        self.assertEqual(entry.extra_data["step_up_action"], "cross_facility_access")


class CookieMetadataTests(DjangoTestCase):
    """Test device metadata tracking in cookies"""
    
    def setUp(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            region="Central",
            nhis_code="TH001",
        )
        self.user = User.objects.create_user(
            email="test@example.com",
            password="Password123!@#",
            hospital=self.hospital,
            role="doctor",
        )
    
    def test_client_metadata_stored_correctly(self):
        """Test that client metadata is stored in JSON"""
        metadata = {
            "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "ip_addr": "192.168.1.1",
            "device_name": "Office Desktop"
        }
        
        cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="metadata_test",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            client_metadata=metadata,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        # Verify metadata is stored and retrievable
        self.assertEqual(cookie.client_metadata['user_agent'], metadata['user_agent'])
        self.assertEqual(cookie.client_metadata['ip_addr'], metadata['ip_addr'])
        self.assertEqual(cookie.client_metadata['device_name'], metadata['device_name'])
    
    def test_device_fingerprint_tracking(self):
        """Test that device fingerprint is stored"""
        fingerprint = hashlib.sha256(b"Chrome|1920x1080|UTC").hexdigest()
        
        cookie = ClientCookie.objects.create(
            user=self.user,
            cookie_token="fingerprint_test",
            access_token_jwt=encrypt_jwt("token"),
            refresh_token_jwt=encrypt_jwt("token"),
            device_fingerprint=fingerprint,
            expires_at=timezone.now() + timedelta(minutes=15),
        )
        
        self.assertEqual(cookie.device_fingerprint, fingerprint)
        self.assertEqual(len(cookie.device_fingerprint), 64)  # SHA256 hex
