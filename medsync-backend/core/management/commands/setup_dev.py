"""
Development Setup Management Command
⚠️  FOR LOCAL DEVELOPMENT ONLY - Do not run in production

This command creates seed data (hospitals, wards, test users) for local development.
Dev credentials are deterministic (so local teams can share them) and printed.
"""

from django.core.management.base import BaseCommand
from core.models import Hospital, Ward, User, Department, LabUnit, SuperAdminHospitalAccess
from core.reference_data import GHANA_HOSPITALS
import pyotp


def _generate_totp_secret():
    """Generate a random TOTP secret."""
    return pyotp.random_base32()


def _ensure_wards(hospital, ward_specs):
    for name, wtype in ward_specs:
        Ward.objects.get_or_create(
            hospital=hospital,
            ward_name=name,
            defaults={"ward_type": wtype},
        )


DEFAULT_WARDS = [
    ("Ward A - General", "general"),
    ("Ward B - Surgical", "surgical"),
    ("ICU", "icu"),
    ("Maternity", "maternity"),
    ("Paediatric Ward", "paediatric"),
    ("Emergency", "emergency"),
]


class Command(BaseCommand):
    help = "Create dev hospital, wards, and test users (LOCAL DEV ONLY)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "[WARNING] This command should only run in LOCAL DEVELOPMENT.\n"
            "          Do not run in production or staging environments."
        ))
        
        # Ensure MFA cache table exists (required for login flow)
        from django.core.management import call_command
        try:
            call_command("createcachetable", verbosity=0)
        except Exception as e:
            self.stdout.write(self.style.WARNING(
                f"[WARNING] Could not create cache table (may already exist): {e}"
            ))

        # Create hospitals and wards
        for ref in GHANA_HOSPITALS:
            hospital, created = Hospital.objects.get_or_create(
                nhis_code=ref["nhis_code"],
                defaults={
                    "name": ref["name"],
                    "region": ref["region"],
                    "address": ref.get("address", ""),
                },
            )
            if created:
                _ensure_wards(hospital, DEFAULT_WARDS)
        
        hospital = Hospital.objects.filter(nhis_code="GAC-001").first()
        if not hospital:
            self.stderr.write(self.style.ERROR(
                "No hospital with nhis_code GAC-001 found. Run again after hospitals are created."
            ))
            return

        # Only the super admin account is created in dev setup.
        SUPER_ADMIN_EMAIL = "admin@medsync.gh"
        SUPER_ADMIN_PASSWORD = "Admin123!@#"

        self.stdout.write(self.style.SUCCESS("[OK] Dev Users (1)"))
        u, created = User.objects.get_or_create(
            email=SUPER_ADMIN_EMAIL,
            defaults={
                "role": "super_admin",
                "full_name": "Super Admin",
                "account_status": "active",
                "hospital": None,
            },
        )
        if not getattr(u, "is_superuser", False) or not getattr(u, "is_staff", False):
            u.is_superuser = True
            u.is_staff = True
        u.set_password(SUPER_ADMIN_PASSWORD)
        if not u.totp_secret:
            u.totp_secret = _generate_totp_secret()
        u.is_mfa_enabled = True
        u.account_status = "active"
        u.hospital = None
        u.role = "super_admin"
        u.save()

        # Grant super admin access to all hospitals (dev convenience)
        for h in Hospital.objects.filter(is_active=True):
            SuperAdminHospitalAccess.objects.get_or_create(
                super_admin=u,
                hospital=h,
                defaults={"granted_by": None},
            )

        self.stdout.write(f"     super_admin: {SUPER_ADMIN_EMAIL}")
        self.stdout.write(f"        Password: {SUPER_ADMIN_PASSWORD}")
        self.stdout.write(f"        TOTP Secret: {u.totp_secret}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("[OK] Setup complete!"))
        self.stdout.write("")
        self.stdout.write(self.style.WARNING(
            "[SECURITY] IMPORTANT NOTES:\n"
            "           - Save credentials above securely (password manager, etc.)\n"
            "           - Do not commit these credentials or logs to version control\n"
            "           - In production, use proper credential management\n"
            "           - Users can reset passwords via forgot_password endpoint"
        ))
