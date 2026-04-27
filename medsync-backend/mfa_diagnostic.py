#!/usr/bin/env python
"""Quick TOTP diagnostic script"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

django.setup()

import pyotp
import time
from django.utils import timezone
from core.models import User

print("=" * 60)
print("MFA TOTP DIAGNOSTIC")
print("=" * 60)

# 1. Check backend time
print("\n1. BACKEND TIME CHECK")
print("-" * 60)
now = timezone.now()
print(f"Backend UTC time: {now}")
print(f"Backend ISO time: {now.isoformat()}")
print(f"Timestamp: {now.timestamp()}")

# 2. Check user TOTP secrets
print("\n2. USER TOTP SECRETS")
print("-" * 60)
users_with_totp = User.objects.filter(totp_secret__isnull=False).count()
users_without_totp = User.objects.filter(totp_secret__isnull=True).count()
print(f"Users WITH TOTP secret: {users_with_totp}")
print(f"Users WITHOUT TOTP secret: {users_without_totp}")

for user in User.objects.filter(totp_secret__isnull=False)[:3]:
    print(f"\n  {user.email} ({user.role})")
    print(f"    Secret: {user.totp_secret[:20]}...")
    print(f"    MFA Enabled: {user.is_mfa_enabled}")

# 3. Test TOTP generation and verification
print("\n3. TOTP GENERATION & VERIFICATION TEST")
print("-" * 60)
test_secret = pyotp.random_base32()
totp = pyotp.TOTP(test_secret)

current_code = totp.now()
print(f"Test secret: {test_secret}")
print(f"Current code: {current_code}")

# Verify with different windows
print(f"\nVerification tests:")
print(f"  valid_window=0: {totp.verify(current_code, valid_window=0)}")
print(f"  valid_window=1: {totp.verify(current_code, valid_window=1)}")
print(f"  valid_window=2: {totp.verify(current_code, valid_window=2)}")

# 4. Check for time skew
print("\n4. TIME SKEW DETECTION")
print("-" * 60)
print("⚠️  If verification fails, check:")
print("  1. System time matches backend time")
print("  2. Authenticator app time is synced")
print("  3. Windows Time service is running")
print("")
print("Fix time skew with:")
print("  PowerShell: w32tm /resync")
print("  Django restart: python manage.py runserver")

# 5. MFA session status
print("\n5. RECENT MFA SESSIONS")
print("-" * 60)
from core.models import MFASession

recent = MFASession.objects.order_by("-created_at")[:5]
if recent:
    for session in recent:
        print(f"\n  {session.user.email}")
        print(f"    Status: {session.status}")
        print(f"    Failed attempts: {session.failed_attempts}")
        print(f"    Created: {session.created_at}")
else:
    print("No MFA sessions found")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
