import os
import django
import secrets
import hashlib

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
django.setup()

from core.models import User
import pyotp

print("=" * 80)
print("ACTIVATING ALL DEV ACCOUNTS WITH MFA & BACKUP CODES")
print("=" * 80)

users = User.objects.filter(email__in=[
    "admin@medsync.gh",
    "doctor@medsync.gh", 
    "doctor2@medsync.gh",
    "hospital_admin@medsync.gh",
    "nurse@medsync.gh",
    "receptionist@medsync.gh",
    "lab_technician@medsync.gh"
])

for u in users:
    print(f"\n📧 {u.email}")
    
    # Enable MFA
    u.is_mfa_enabled = True
    
    # Ensure TOTP secret exists
    if not u.totp_secret:
        u.totp_secret = pyotp.random_base32()
    
    # Generate backup codes (8 single-use codes)
    backup_codes_plain = [f"{secrets.token_hex(4).upper()}" for _ in range(8)]
    # Hash them for storage
    backup_codes_hashed = [hashlib.sha256(code.encode()).hexdigest() for code in backup_codes_plain]
    u.mfa_backup_codes = backup_codes_hashed
    
    u.account_status = "active"
    u.save()
    
    print(f"   ✅ MFA Enabled")
    print(f"   TOTP Secret: {u.totp_secret}")
    print(f"   Backup Codes (save these!):")
    for i, code in enumerate(backup_codes_plain, 1):
        print(f"      {i}. {code}")

print("\n" + "=" * 80)
print("✅ All accounts activated with MFA & backup codes")
print("=" * 80)
print("\nNOTE: MFA is now REQUIRED for login. Use TOTP codes or backup codes to proceed.")
