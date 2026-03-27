"""Enable MFA for an existing user (e.g. created with createsuperuser) using the dev TOTP secret.
Use when you see 'MFA not configured' at login.
Add secret JBSWY3DPEHPK3PXP to your authenticator app, then log in with this user and the 6-digit code.
"""
from django.core.management.base import BaseCommand
from core.models import User

DEV_TOTP_SECRET = "JBSWY3DPEHPK3PXP"


class Command(BaseCommand):
    help = "Enable MFA for a user by email (dev TOTP secret). Use with createsuperuser accounts."

    def add_arguments(self, parser):
        parser.add_argument("email", type=str, help="User email to enable MFA for")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            self.stderr.write(self.style.ERROR(f"User with email '{email}' not found."))
            return
        user.totp_secret = DEV_TOTP_SECRET
        user.is_mfa_enabled = True
        user.save()
        self.stdout.write(
            self.style.SUCCESS(
                f"MFA enabled for {email}. Add secret {DEV_TOTP_SECRET} to your authenticator app, then log in with your password and the 6-digit code."
            )
        )
