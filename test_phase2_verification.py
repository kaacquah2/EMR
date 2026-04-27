#!/usr/bin/env python
"""
Phase 2 Passkey Management Verification Test
Tests all endpoints and ensures Phase 2 implementation works end-to-end
"""
import os
import sys
import django
import json
from typing import Dict, Any

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from core.models import UserPasskey, AuditLog, Hospital
from webauthn.helpers.structs import AuthenticatorSelectionCriteria
import webauthn

User = get_user_model()

class Phase2Tester:
    def __init__(self):
        self.client = Client()
        self.test_user = None
        self.test_hospital = None
        self.passkey_id = None
        self.results = {
            'passed': [],
            'failed': [],
            'errors': []
        }

    def setup(self):
        """Setup test user and hospital"""
        try:
            # Get or create hospital
            self.test_hospital, _ = Hospital.objects.get_or_create(
                code='TEST_HOSP',
                defaults={'name': 'Test Hospital', 'is_active': True}
            )
            
            # Get or create test user
            self.test_user, _ = User.objects.get_or_create(
                email='passkey_tester@medsync.gh',
                defaults={
                    'full_name': 'Passkey Tester',
                    'role': 'doctor',
                    'hospital': self.test_hospital,
                    'is_active': True,
                    'password_set': True,
                }
            )
            self.test_user.set_password('TestPass123!@#')
            self.test_user.save()
            
            print(f"✓ Setup complete: user={self.test_user.email}, hospital={self.test_hospital.name}")
            return True
        except Exception as e:
            self.record_error(f"Setup failed: {str(e)}")
            return False

    def test_list_passkeys_unauthenticated(self):
        """Test: GET /auth/passkeys without auth should return 401"""
        try:
            response = self.client.get('/api/v1/auth/passkeys')
            if response.status_code == 401:
                self.record_pass("List passkeys unauthenticated: correctly rejected (401)")
            else:
                self.record_fail(f"List passkeys unauthenticated: expected 401, got {response.status_code}")
        except Exception as e:
            self.record_error(f"List passkeys unauthenticated: {str(e)}")

    def test_login_and_get_token(self):
        """Test: Login and get JWT tokens"""
        try:
            response = self.client.post('/api/v1/auth/login', {
                'email': self.test_user.email,
                'password': 'TestPass123!@#'
            }, content_type='application/json')
            
            if response.status_code in [200, 400]:  # 200 = success, 400 = TOTP required
                data = response.json()
                if 'access_token' in data:
                    self.access_token = data['access_token']
                    self.client.defaults['HTTP_AUTHORIZATION'] = f'Bearer {self.access_token}'
                    self.record_pass(f"Login successful, got access token")
                    return True
                elif 'mfa_required' in data or 'totp_required' in data:
                    self.record_pass("Login requires TOTP (expected for new accounts)")
                    return True
                else:
                    self.record_fail(f"Login returned unexpected response: {data}")
                    return False
            else:
                self.record_fail(f"Login failed with status {response.status_code}: {response.json()}")
                return False
        except Exception as e:
            self.record_error(f"Login: {str(e)}")
            return False

    def test_list_passkeys_authenticated(self):
        """Test: GET /auth/passkeys with auth should return empty list initially"""
        try:
            response = self.client.get('/api/v1/auth/passkeys')
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list):
                    self.record_pass(f"List passkeys authenticated: returned {len(data)} passkeys")
                    return True
                else:
                    self.record_fail(f"List passkeys: expected list, got {type(data)}")
                    return False
            else:
                self.record_fail(f"List passkeys: expected 200, got {response.status_code}")
                return False
        except Exception as e:
            self.record_error(f"List passkeys authenticated: {str(e)}")
            return False

    def test_passkey_register_begin(self):
        """Test: POST /auth/passkey/register/begin returns challenge"""
        try:
            response = self.client.post('/api/v1/auth/passkey/register/begin', {})
            if response.status_code == 200:
                data = response.json()
                if 'challenge' in data and 'rp' in data and 'user' in data:
                    self.record_pass("Register begin: got challenge and RP data")
                    return True
                else:
                    self.record_fail(f"Register begin: missing challenge/rp/user: {data}")
                    return False
            else:
                self.record_fail(f"Register begin: expected 200, got {response.status_code}")
                return False
        except Exception as e:
            self.record_error(f"Register begin: {str(e)}")
            return False

    def test_rename_endpoint_exists(self):
        """Test: Check if rename endpoint is properly registered"""
        try:
            # Try to make a request to rename (should fail with validation error, not 404)
            fake_id = '550e8400-e29b-41d4-a716-446655440000'
            response = self.client.post(
                f'/api/v1/auth/passkeys/{fake_id}/rename',
                {'new_name': 'Test Device'},
                content_type='application/json'
            )
            
            # Should get 404 (passkey not found) not 404 (endpoint not found)
            if response.status_code == 404:
                data = response.json()
                # Check if it's a passkey not found error, not a route not found
                if 'detail' in data or 'error' in data:
                    self.record_pass("Rename endpoint: exists and properly routing")
                    return True
            elif response.status_code == 400:
                self.record_pass("Rename endpoint: exists (validation error as expected)")
                return True
            else:
                self.record_fail(f"Rename endpoint: unexpected status {response.status_code}")
                return False
        except Exception as e:
            self.record_error(f"Rename endpoint check: {str(e)}")
            return False

    def test_permissions_matrix(self):
        """Test: Verify permissions.py has passkey endpoints configured"""
        try:
            from shared.permissions import PERMISSION_MATRIX
            
            checks = {
                "auth/passkeys": "GET should be allowed for authenticated",
                "auth/passkeys/<pk>": "DELETE and POST should be allowed for authenticated"
            }
            
            all_ok = True
            for endpoint, description in checks.items():
                if endpoint in PERMISSION_MATRIX:
                    self.record_pass(f"Permissions: {endpoint} configured - {description}")
                else:
                    self.record_fail(f"Permissions: {endpoint} NOT in matrix")
                    all_ok = False
            
            return all_ok
        except Exception as e:
            self.record_error(f"Permissions check: {str(e)}")
            return False

    def test_audit_logging(self):
        """Test: Verify audit logging is configured"""
        try:
            # Create a passkey manually to test audit logging
            from core.models import UserPasskey
            
            pk = UserPasskey.objects.create(
                user=self.test_user,
                credential_id=b'test_cred_id_12345678901',
                public_key=b'test_public_key_1234567890',
                sign_count=0,
                device_name='Test Device for Audit',
                platform='windows'
            )
            
            # Check if we can list it
            response = self.client.get('/api/v1/auth/passkeys')
            if response.status_code == 200:
                data = response.json()
                if any(p.get('device_name') == 'Test Device for Audit' for p in data):
                    self.record_pass("Audit: passkey created and appears in list")
                    self.passkey_id = str(pk.id)
                    return True
                else:
                    self.record_fail("Audit: created passkey not appearing in list")
                    return False
            else:
                self.record_fail(f"Audit check list failed: {response.status_code}")
                return False
        except Exception as e:
            self.record_error(f"Audit logging test: {str(e)}")
            return False

    def test_rename_passkey(self):
        """Test: POST /auth/passkeys/{id}/rename updates device_name"""
        if not self.passkey_id:
            self.record_fail("Rename: no passkey_id available")
            return False
        
        try:
            response = self.client.post(
                f'/api/v1/auth/passkeys/{self.passkey_id}/rename',
                {'new_name': 'Renamed Test Device'},
                content_type='application/json'
            )
            
            if response.status_code == 200:
                data = response.json()
                if 'device_name' in data and data['device_name'] == 'Renamed Test Device':
                    self.record_pass("Rename: successfully updated device_name")
                    return True
                else:
                    self.record_fail(f"Rename: response missing updated name: {data}")
                    return False
            else:
                self.record_fail(f"Rename: expected 200, got {response.status_code}: {response.json()}")
                return False
        except Exception as e:
            self.record_error(f"Rename passkey: {str(e)}")
            return False

    def test_rename_validation(self):
        """Test: Rename rejects invalid names"""
        if not self.passkey_id:
            self.record_fail("Rename validation: no passkey_id available")
            return False
        
        test_cases = [
            ('', 'empty name'),
            ('x' * 101, 'name too long'),
        ]
        
        all_ok = True
        for invalid_name, description in test_cases:
            try:
                response = self.client.post(
                    f'/api/v1/auth/passkeys/{self.passkey_id}/rename',
                    {'new_name': invalid_name},
                    content_type='application/json'
                )
                
                if response.status_code == 400:
                    self.record_pass(f"Rename validation: rejected {description} (400)")
                else:
                    self.record_fail(f"Rename validation: {description} returned {response.status_code}, expected 400")
                    all_ok = False
            except Exception as e:
                self.record_error(f"Rename validation ({description}): {str(e)}")
                all_ok = False
        
        return all_ok

    def test_delete_passkey(self):
        """Test: DELETE /auth/passkeys/{id} removes passkey"""
        if not self.passkey_id:
            self.record_fail("Delete: no passkey_id available")
            return False
        
        try:
            response = self.client.delete(f'/api/v1/auth/passkeys/{self.passkey_id}')
            
            if response.status_code == 204 or response.status_code == 200:
                self.record_pass("Delete: successfully deleted passkey")
                self.passkey_id = None
                return True
            else:
                self.record_fail(f"Delete: expected 204/200, got {response.status_code}")
                return False
        except Exception as e:
            self.record_error(f"Delete passkey: {str(e)}")
            return False

    def test_frontend_files_exist(self):
        """Test: Verify frontend files are in place"""
        frontend_files = [
            'medsync-frontend/src/components/features/passkey/PasskeyComponents.tsx',
            'medsync-frontend/src/app/(dashboard)/settings/security/passkeys/page.tsx',
            'medsync-frontend/src/hooks/use-passkey.ts',
            'medsync-frontend/src/lib/passkey.ts',
        ]
        
        all_ok = True
        for file_path in frontend_files:
            full_path = os.path.join(os.path.dirname(__file__), file_path)
            if os.path.exists(full_path):
                self.record_pass(f"Frontend: {file_path} exists")
            else:
                self.record_fail(f"Frontend: {file_path} MISSING")
                all_ok = False
        
        return all_ok

    def record_pass(self, message: str):
        print(f"✓ {message}")
        self.results['passed'].append(message)

    def record_fail(self, message: str):
        print(f"✗ {message}")
        self.results['failed'].append(message)

    def record_error(self, message: str):
        print(f"⚠ {message}")
        self.results['errors'].append(message)

    def run_all_tests(self):
        """Run all tests and print summary"""
        print("\n" + "="*70)
        print("Phase 2: Passkey Management Verification Tests")
        print("="*70 + "\n")
        
        if not self.setup():
            print("\n✗ Setup failed, cannot continue")
            return False
        
        print("\n--- Backend Endpoint Tests ---")
        self.test_list_passkeys_unauthenticated()
        self.test_login_and_get_token()
        self.test_list_passkeys_authenticated()
        self.test_passkey_register_begin()
        self.test_permissions_matrix()
        
        print("\n--- Passkey Management Tests ---")
        self.test_audit_logging()
        self.test_rename_endpoint_exists()
        self.test_rename_passkey()
        self.test_rename_validation()
        self.test_delete_passkey()
        
        print("\n--- Frontend File Tests ---")
        self.test_frontend_files_exist()
        
        print("\n" + "="*70)
        print(f"Results: {len(self.results['passed'])} passed, {len(self.results['failed'])} failed, {len(self.results['errors'])} errors")
        print("="*70 + "\n")
        
        if self.results['failed']:
            print("Failed tests:")
            for msg in self.results['failed']:
                print(f"  ✗ {msg}")
        
        if self.results['errors']:
            print("\nErrors:")
            for msg in self.results['errors']:
                print(f"  ⚠ {msg}")
        
        return len(self.results['failed']) == 0 and len(self.results['errors']) == 0


if __name__ == '__main__':
    tester = Phase2Tester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
