import pytest
import bcrypt
import json
from django.utils import timezone
from django.test import RequestFactory
from datetime import timedelta
from core.models import User, Hospital, TrustedDevice, ClientCookie
from api.auth_utils import compute_device_fingerprint, compute_login_risk_tier
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch


@pytest.mark.django_db
class TestRoleBasedRiskTier:
    """Test role-based risk tier computation enforcement"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TEST-ROLE-001",
            region="Ashanti",
            is_active=True,
            ip_subnets=["192.168.1.0/24"]
        )

    def _get_mock_request(self):
        factory = RequestFactory()
        request = factory.post('/api/v1/auth/login')
        request.META['HTTP_USER_AGENT'] = 'Test Agent'
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.data = {
            'screen_resolution': '1920x1080',
            'timezone': 'Africa/Accra'
        }
        return request

    def test_tier_1_role_gets_risk_tier_1(self):
        """Tier 1 roles can bypass MFA if conditions are met"""
        roles = ['nurse', 'lab_technician', 'pharmacy_technician', 'radiology_technician', 'ward_clerk']
        for role in roles:
            user = User.objects.create_user(
                email=f"{role}@test.gh",
                password="Test123!@#$%",
                role=role,
                hospital=self.hospital
            )
            request = self._get_mock_request()
            fp = compute_device_fingerprint(request)
            TrustedDevice.objects.create(
                user=user,
                device_fingerprint=fp,
                is_active=True,
                expires_at=timezone.now() + timedelta(days=30)
            )
            with patch('api.auth_utils.is_within_business_hours', return_value=True):
                result = compute_login_risk_tier(user, request)
            assert result['risk_tier'] == 1, f"Role {role} should have bypassed MFA"

    def test_non_tier_1_roles_get_risk_tier_2(self):
        """Tier 2-5 roles must always trigger MFA (risk_tier=2) even on trusted devices"""
        roles = ['doctor', 'receptionist', 'billing_staff', 'hospital_admin', 'super_admin']
        for role in roles:
            user = User.objects.create_user(
                email=f"{role}@test.gh",
                password="Test123!@#$%",
                role=role,
                hospital=self.hospital
            )
            request = self._get_mock_request()
            fp = compute_device_fingerprint(request)
            TrustedDevice.objects.create(
                user=user,
                device_fingerprint=fp,
                is_active=True,
                expires_at=timezone.now() + timedelta(days=30)
            )
            with patch('api.auth_utils.is_within_business_hours', return_value=True):
                result = compute_login_risk_tier(user, request)
            assert result['risk_tier'] == 2, f"Role {role} must require MFA"


@pytest.mark.django_db
class TestPinEndpoints:
    """Test set-device-pin and session-unlock endpoints"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.client = APIClient()
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TEST-PIN-001",
            region="Ashanti",
            is_active=True
        )
        self.nurse = User.objects.create_user(
            email="nurse@test.gh",
            password="Test123!@#$%",
            role="nurse",
            hospital=self.hospital,
            is_mfa_enabled=True,
            totp_secret="JBSWY3DP"
        )
        self.doctor = User.objects.create_user(
            email="doctor@test.gh",
            password="Test123!@#$%",
            role="doctor",
            hospital=self.hospital
        )

    def test_set_pin_valid_nurse(self):
        """Nurses can set their PIN on trusted device"""
        self.client.force_authenticate(user=self.nurse)
        response = self.client.post(
            '/api/v1/auth/set-device-pin',
            {'pin': '1234'},
            format='json',
            HTTP_USER_AGENT='Test User Agent',
            HTTP_X_SCREEN_RESOLUTION='1920x1080',
            HTTP_X_TIMEZONE='Africa/Accra'
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Verify TrustedDevice is created and has hashed PIN
        from api.auth_utils import compute_device_fingerprint
        factory = RequestFactory()
        req = factory.post('/api/v1/auth/set-device-pin')
        req.META['HTTP_USER_AGENT'] = 'Test User Agent'
        req.data = {
            'screen_resolution': '1920x1080',
            'timezone': 'Africa/Accra'
        }
        fp = compute_device_fingerprint(req)
        
        device = TrustedDevice.objects.get(user=self.nurse, device_fingerprint=fp)
        assert device.pin_hash is not None
        
        # Verify it checks out with bcrypt
        pin_bytes = ('1234' + str(self.nurse.id)).encode('utf-8')
        assert bcrypt.checkpw(pin_bytes, device.pin_hash.encode('utf-8'))

    def test_set_pin_invalid_roles(self):
        """Doctors cannot set a device PIN"""
        self.client.force_authenticate(user=self.doctor)
        response = self.client.post(
            '/api/v1/auth/set-device-pin',
            {'pin': '1234'},
            format='json'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_set_pin_invalid_formats(self):
        """Invalid PIN formats are rejected"""
        self.client.force_authenticate(user=self.nurse)
        invalid_pins = ['123', '12345', 'abcd', '']
        for p in invalid_pins:
            response = self.client.post(
                '/api/v1/auth/set-device-pin',
                {'pin': p},
                format='json'
            )
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_session_unlock_flow(self):
        """Nurses can unlock session using PIN and refresh token"""
        # 1. Set the PIN first
        self.client.force_authenticate(user=self.nurse)
        self.client.post(
            '/api/v1/auth/set-device-pin',
            {'pin': '5678'},
            format='json',
            HTTP_USER_AGENT='Test User Agent',
            HTTP_X_SCREEN_RESOLUTION='1920x1080',
            HTTP_X_TIMEZONE='Africa/Accra'
        )
        
        # 2. Get tokens for the nurse
        from api.views.auth_views import get_tokens_for_user
        factory = RequestFactory()
        req = factory.post('/api/v1/auth/login')
        req.META['HTTP_USER_AGENT'] = 'Test User Agent'
        req.data = {'screen_resolution': '1920x1080', 'timezone': 'Africa/Accra'}
        refresh = get_tokens_for_user(self.nurse, req)
        
        # 3. Call session unlock anonymously with PIN and refresh token
        self.client.force_authenticate(user=None) # Anonymize
        response = self.client.post(
            '/api/v1/auth/session-unlock',
            {
                'pin': '5678',
                'refresh_token': str(refresh)
            },
            format='json',
            HTTP_USER_AGENT='Test User Agent',
            HTTP_X_SCREEN_RESOLUTION='1920x1080',
            HTTP_X_TIMEZONE='Africa/Accra'
        )
        assert response.status_code == status.HTTP_200_OK
        assert 'access_token' in response.json()
        assert 'refresh_token' in response.json()

        # 4. Try with wrong PIN
        response = self.client.post(
            '/api/v1/auth/session-unlock',
            {
                'pin': '0000',
                'refresh_token': str(refresh)
            },
            format='json',
            HTTP_USER_AGENT='Test User Agent',
            HTTP_X_SCREEN_RESOLUTION='1920x1080',
            HTTP_X_TIMEZONE='Africa/Accra'
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
