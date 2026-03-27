"""Print current TOTP code for dev secret. Use only in local dev to log in when authenticator is missing or out of sync."""
from django.core.management.base import BaseCommand
import pyotp

DEV_TOTP_SECRET = "JBSWY3DPEHPK3PXP"


class Command(BaseCommand):
    help = "Print current 6-digit TOTP code for dev secret (local dev only)."

    def handle(self, *args, **options):
        code = pyotp.TOTP(DEV_TOTP_SECRET).now()
        self.stdout.write(f"Current TOTP code for {DEV_TOTP_SECRET}: {code}")
        self.stdout.write("(Use within 30 seconds; valid for ~60s with server clock skew.)")
