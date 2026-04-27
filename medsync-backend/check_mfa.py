import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'medsync_backend.settings')
django.setup()

from core.models import User

print("=" * 80)
print("MFA STATUS FOR ALL DEV ACCOUNTS")
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
    print(f"   Role: {u.role}")
    print(f"   MFA Enabled: {u.is_mfa_enabled}")
    print(f"   TOTP Secret: {u.totp_secret[:20]}..." if u.totp_secret else "   TOTP Secret: None")
    print(f"   Backup Codes: {'Set' if u.mfa_backup_codes else 'Not set'}")
    print(f"   Account Status: {u.account_status}")
    
    # Disable MFA for all to allow login without TOTP
    if u.is_mfa_enabled:
        u.is_mfa_enabled = False
        u.save()
        print(f"   ✅ MFA disabled")

print("\n" + "=" * 80)
print("✅ MFA disabled for all accounts - you can log in without TOTP codes")
print("=" * 80)
