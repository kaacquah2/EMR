#!/usr/bin/env python
"""
Test TOTP verification with a running Django server.
Use this to test if your backend time and TOTP secrets are properly configured.

Usage:
    1. Start Django: python manage.py runserver
    2. In another terminal: python test_mfa_endpoint.py
"""

import os
import sys
import django
import json
import requests

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

import pyotp
from django.utils import timezone
from core.models import User, MFASession

API_URL = "http://localhost:8000/api/v1"
TEST_USER_EMAIL = "doctor@medsync.gh"
TEST_PASSWORD = "Doctor123!"

print("=" * 70)
print("MFA TOTP ENDPOINT TEST")
print("=" * 70)

# Get test user
try:
    user = User.objects.get(email=TEST_USER_EMAIL)
    print(f"\n✅ User found: {TEST_USER_EMAIL} ({user.role})")
except User.DoesNotExist:
    print(f"\n❌ User not found: {TEST_USER_EMAIL}")
    sys.exit(1)

# Check TOTP secret
if not user.totp_secret:
    print(f"❌ User has no TOTP secret set")
    print("Fix: python manage.py setup_dev")
    sys.exit(1)

print(f"✅ TOTP secret exists: {user.totp_secret[:20]}...")

# Generate current TOTP code
totp = pyotp.TOTP(user.totp_secret)
current_code = totp.now()
print(f"✅ Current TOTP code: {current_code}")
print(f"   (Code valid for ~{30 - (int(timezone.now().timestamp()) % 30)} more seconds)")

# Try login
print("\n" + "-" * 70)
print("STEP 1: LOGIN (get MFA session)")
print("-" * 70)

login_data = {
    "email": TEST_USER_EMAIL,
    "password": TEST_PASSWORD
}

try:
    response = requests.post(f"{API_URL}/auth/login", json=login_data, timeout=10)
    login_response = response.json()
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print("✅ Login succeeded (no MFA required?)")
        print(json.dumps(login_response, indent=2))
    elif response.status_code == 202:
        print("✅ MFA required (expected)")
        mfa_session_id = login_response.get("mfa_session_id")
        print(f"   MFA Session ID: {mfa_session_id}")
        
        if not mfa_session_id:
            print("❌ No MFA session ID returned")
            print(json.dumps(login_response, indent=2))
            sys.exit(1)
        
        # Try MFA verify
        print("\n" + "-" * 70)
        print("STEP 2: MFA VERIFY (submit TOTP code)")
        print("-" * 70)
        
        mfa_data = {
            "mfa_session_id": mfa_session_id,
            "code": current_code
        }
        
        mfa_response = requests.post(f"{API_URL}/auth/mfa/verify", json=mfa_data, timeout=10)
        mfa_result = mfa_response.json()
        
        print(f"Status: {mfa_response.status_code}")
        print(f"Code submitted: {current_code}")
        
        if mfa_response.status_code == 200:
            print("✅ MFA VERIFICATION SUCCEEDED!")
            print(f"   Access token received: {mfa_result.get('access_token', '???')[:20]}...")
        else:
            print("❌ MFA VERIFICATION FAILED")
            print(f"   Message: {mfa_result.get('message', 'N/A')}")
            print(f"   Failed attempts: {mfa_result.get('failed_attempts', '?')}")
            
            # Suggest troubleshooting
            print("\n" + "!" * 70)
            print("TROUBLESHOOTING:")
            print("!" * 70)
            print("1. Check system time: Your time might be out of sync")
            print("2. Run: w32tm /resync (Windows)")
            print("3. Check authenticator app time settings")
            print("4. Verify TOTP code again - they expire every 30 seconds")
            
    else:
        print(f"❌ Unexpected status: {response.status_code}")
        print(json.dumps(login_response, indent=2))
        
except requests.ConnectionError:
    print("❌ Could not connect to Django server")
    print("   Is it running? python manage.py runserver")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("TEST COMPLETE")
print("=" * 70)
