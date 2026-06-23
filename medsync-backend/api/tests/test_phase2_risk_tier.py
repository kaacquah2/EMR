"""
Test Phase 2: Risk-Aware Adaptive MFA Implementation

Tests for:
1. Device fingerprinting
2. Risk tier computation
3. Step-up endpoints
4. Device trust model
"""

import pytest
from unittest.mock import patch
from django.utils import timezone
from django.test import TestCase, RequestFactory
from datetime import timedelta
from core.models import User, Hospital, TrustedDevice, StepUpSession
from api.auth_utils import compute_device_fingerprint, compute_login_risk_tier, is_within_business_hours, is_ip_in_hospital_subnet
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestDeviceFingerprinting:
    """Test device fingerprint computation"""
    
    def test_device_fingerprint_consistency(self):
        """Same request should produce same fingerprint"""
        factory = RequestFactory()
        request = factory.post('/api/v1/auth/login', data={
            'screen_resolution': '1920x1080',
            'timezone': 'Africa/Accra'
        }, content_type='application/json')
        request.META['HTTP_USER_AGENT'] = 'Mozilla/5.0 Test Browser'
        
        # Parse request data manually since we're using RequestFactory
        import json
        request.data = json.loads(request.body) if request.body else {}
        
        fp1 = compute_device_fingerprint(request)
        fp2 = compute_device_fingerprint(request)
        
        assert fp1 == fp2
        assert len(fp1) == 64  # SHA256 hex digest


@pytest.mark.django_db
class TestRiskTierComputation:
    """Test risk tier computation logic"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test data"""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TEST-001",
            region="Ashanti",
            is_active=True,
            ip_subnets=["192.168.1.0/24"]  # Hospital IP range
        )
        
        self.user = User.objects.create_user(
            email="doctor@test.gh",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital
        )
    
    def test_risk_tier_1_for_known_device_known_ip_business_hours(self):
        """Tier 1: known device + known IP + business hours → no MFA"""
        factory = RequestFactory()
        request = factory.post('/api/v1/auth/login')
        request.META['HTTP_USER_AGENT'] = 'Test Agent'
        request.META['REMOTE_ADDR'] = '192.168.1.100'  # Within hospital subnet
        request.data = {
            'screen_resolution': '1920x1080',
            'timezone': 'Africa/Accra'  # Business hours (06:00-22:00)
        }
        
        # Create trusted device
        fp = compute_device_fingerprint(request)
        TrustedDevice.objects.create(
            user=self.user,
            device_fingerprint=fp,
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        # Patch business-hours check so the test is time-of-day independent
        with patch("api.auth_utils.is_within_business_hours", return_value=True):
            result = compute_login_risk_tier(self.user, request)

        assert result['risk_tier'] == 1
        assert 'device' in result['factors']
        assert 'ip' in result['factors']
        assert 'hours' in result['factors']
    
    def test_risk_tier_2_for_admin_role(self):
        """Tier 2: admin role always requires MFA"""
        admin = User.objects.create_user(
            email="admin@test.gh",
            password="Test123!@#",
            role="super_admin",
        )
        
        factory = RequestFactory()
        request = factory.post('/api/v1/auth/login')
        request.META['HTTP_USER_AGENT'] = 'Test Agent'
        request.META['REMOTE_ADDR'] = '192.168.1.100'
        request.data = {
            'screen_resolution': '1920x1080',
            'timezone': 'Africa/Accra'
        }
        
        # Create trusted device for admin
        fp = compute_device_fingerprint(request)
        TrustedDevice.objects.create(
            user=admin,
            device_fingerprint=fp,
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        result = compute_login_risk_tier(admin, request)
        
        assert result['risk_tier'] == 2  # Admin always gets tier 2


@pytest.mark.django_db
class TestStepUpEndpoints:
    """Test step-up verification endpoints"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test client and user"""
        self.client = APIClient()
        
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TEST-001",
            region="Ashanti",
            is_active=True
        )
        
        self.user = User.objects.create_user(
            email="doctor@test.gh",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital,
            is_mfa_enabled=True,
            totp_secret="JBSWY3DP"  # Dummy TOTP secret
        )
        
        # Force authenticate
        self.client.force_authenticate(user=self.user)
    
    def test_step_up_request_endpoint_exists(self):
        """POST /auth/step-up/request should exist"""
        response = self.client.post(
            '/api/v1/auth/step-up/request',
            {'action': 'cross_facility_access'},
            format='json'
        )
        
        # Should return 200 or 201 (successfully created)
        assert response.status_code in [200, 201]
        assert 'step_up_token' in response.json()
        assert 'expires_in' in response.json()
    
    def test_step_up_request_invalid_action(self):
        """Invalid action should return 400"""
        response = self.client.post(
            '/api/v1/auth/step-up/request',
            {'action': 'invalid_action'},
            format='json'
        )
        
        assert response.status_code == 400
        assert 'error' in response.json()
    
    def test_step_up_verify_endpoint_exists(self):
        """POST /auth/step-up/verify should exist"""
        # First, get a step-up token
        request_response = self.client.post(
            '/api/v1/auth/step-up/request',
            {'action': 'break_glass'},
            format='json'
        )
        
        step_up_token = request_response.json()['step_up_token']
        
        # Try to verify (will fail OTP, but endpoint should exist)
        response = self.client.post(
            '/api/v1/auth/step-up/verify',
            {
                'step_up_token': step_up_token,
                'otp_code': '000000',
                'action': 'break_glass'
            },
            format='json'
        )
        
        # Should return 400 (invalid OTP) not 404
        assert response.status_code != 404


@pytest.mark.django_db
class TestTrustedDeviceModel:
    """Test TrustedDevice model"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up test user"""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TEST-001",
            region="Ashanti",
            is_active=True
        )
        
        self.user = User.objects.create_user(
            email="doctor@test.gh",
            password="Test123!@#",
            role="doctor",
            hospital=self.hospital
        )
    
    def test_trusted_device_creation(self):
        """Can create a TrustedDevice"""
        device = TrustedDevice.objects.create(
            user=self.user,
            device_fingerprint="abc123def456",
            is_active=True,
            expires_at=timezone.now() + timedelta(days=30)
        )
        
        assert device.is_active is True
        assert device.is_expired() is False
    
    def test_trusted_device_expiry(self):
        """Device expires after 30 days"""
        device = TrustedDevice.objects.create(
            user=self.user,
            device_fingerprint="abc123def456",
            is_active=True,
            expires_at=timezone.now() - timedelta(days=1)  # Already expired
        )
        
        assert device.is_expired() is True
    
    def test_refresh_expiry(self):
        """refresh_expiry extends expiration"""
        device = TrustedDevice.objects.create(
            user=self.user,
            device_fingerprint="abc123def456",
            is_active=True,
            expires_at=timezone.now() + timedelta(hours=1)
        )
        
        old_expiry = device.expires_at
        device.refresh_expiry(days=30)
        
        assert device.expires_at > old_expiry


@pytest.mark.django_db
class TestBusinessHoursCheck:
    """Test business hours checking"""
    
    def test_business_hours_detection(self):
        """Should correctly identify business hours"""
        # This test depends on the current time
        # We test the function exists and returns a boolean
        result = is_within_business_hours("Africa/Accra")
        assert isinstance(result, bool)
    
    def test_invalid_timezone(self):
        """Invalid timezone should return False"""
        result = is_within_business_hours("Invalid/Timezone")
        assert result is False


@pytest.mark.django_db
class TestIPSubnetCheck:
    """Test IP subnet checking"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Set up hospital with IP subnets"""
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            nhis_code="TEST-001",
            region="Ashanti",
            is_active=True,
            ip_subnets=["192.168.1.0/24", "10.0.0.0/8"]
        )
    
    def test_ip_in_hospital_subnet(self):
        """IP within hospital subnet should return True"""
        result = is_ip_in_hospital_subnet("192.168.1.100", self.hospital)
        assert result is True
    
    def test_ip_not_in_hospital_subnet(self):
        """IP outside hospital subnet should return False"""
        result = is_ip_in_hospital_subnet("172.16.0.1", self.hospital)
        assert result is False
    
    def test_no_hospital_subnets(self):
        """Hospital with no subnets should return False"""
        hospital_no_subnets = Hospital.objects.create(
            name="Remote Hospital",
            nhis_code="REMOTE-001",
            region="Greater Accra",
            is_active=True,
            ip_subnets=[]
        )
        
        result = is_ip_in_hospital_subnet("192.168.1.100", hospital_no_subnets)
        assert result is False
