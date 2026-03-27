"""
Manage Super Admin Hospital Access

Production command to grant/revoke hospital access to super admins.
Supports operations like:
  - List all super admins and their hospital access
  - Grant a super admin access to a hospital
  - Revoke a super admin access from a hospital

Usage:
  python manage.py manage_superadmin_access list
  python manage.py manage_superadmin_access list <super_admin_email>
  python manage.py manage_superadmin_access grant <super_admin_email> <hospital_id>
  python manage.py manage_superadmin_access revoke <super_admin_email> <hospital_id>
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from core.models import Hospital, SuperAdminHospitalAccess
import uuid

User = get_user_model()


class Command(BaseCommand):
    help = "Manage super admin hospital access (grant/revoke/list)"

    def add_arguments(self, parser):
        parser.add_argument(
            "operation",
            type=str,
            choices=["list", "grant", "revoke"],
            help="Operation to perform",
        )
        parser.add_argument(
            "email",
            nargs="?",
            default=None,
            help="Super admin email (for grant/revoke, or optional for list)",
        )
        parser.add_argument(
            "hospital_id",
            nargs="?",
            default=None,
            help="Hospital UUID (required for grant/revoke)",
        )

    def handle(self, *args, **options):
        operation = options["operation"]

        if operation == "list":
            self._list_access(options.get("email"))
        elif operation == "grant":
            if not options.get("email") or not options.get("hospital_id"):
                raise CommandError("grant requires email and hospital_id")
            self._grant_access(options["email"], options["hospital_id"])
        elif operation == "revoke":
            if not options.get("email") or not options.get("hospital_id"):
                raise CommandError("revoke requires email and hospital_id")
            self._revoke_access(options["email"], options["hospital_id"])

    def _list_access(self, email=None):
        """List all super admins or access for a specific super admin."""
        super_admins = User.objects.filter(role="super_admin")
        
        if email:
            super_admins = super_admins.filter(email=email)
            if not super_admins.exists():
                raise CommandError(f"Super admin {email} not found")

        if not super_admins.exists():
            self.stdout.write("No super admins found")
            return

        self.stdout.write(self.style.SUCCESS("\n=== Super Admin Hospital Access ===\n"))

        for admin in super_admins:
            access = SuperAdminHospitalAccess.objects.filter(super_admin=admin).select_related("hospital")
            
            self.stdout.write(self.style.SUCCESS(f"📋 {admin.email}"))
            if not access.exists():
                self.stdout.write(self.style.WARNING("   ⚠️  No hospital access granted"))
            else:
                for entry in access:
                    granted_by = entry.granted_by.email if entry.granted_by else "system"
                    self.stdout.write(f"   ✓ {entry.hospital.name} (ID: {entry.hospital.id})")
                    self.stdout.write(f"     Granted by: {granted_by} on {entry.granted_at.strftime('%Y-%m-%d %H:%M:%S')}")
            self.stdout.write("")

    def _grant_access(self, email, hospital_id_str):
        """Grant a super admin access to a hospital."""
        try:
            super_admin = User.objects.get(email=email, role="super_admin")
        except User.DoesNotExist:
            raise CommandError(f"Super admin with email {email} not found")

        try:
            hospital_id = uuid.UUID(hospital_id_str)
        except ValueError:
            raise CommandError(f"Invalid hospital ID format: {hospital_id_str}")

        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            raise CommandError(f"Hospital with ID {hospital_id} not found")

        access, created = SuperAdminHospitalAccess.objects.get_or_create(
            super_admin=super_admin,
            hospital=hospital,
            defaults={"granted_by": None},
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Granted {super_admin.email} access to {hospital.name}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"⏭️  {super_admin.email} already has access to {hospital.name}"
                )
            )

    def _revoke_access(self, email, hospital_id_str):
        """Revoke a super admin access from a hospital."""
        try:
            super_admin = User.objects.get(email=email, role="super_admin")
        except User.DoesNotExist:
            raise CommandError(f"Super admin with email {email} not found")

        try:
            hospital_id = uuid.UUID(hospital_id_str)
        except ValueError:
            raise CommandError(f"Invalid hospital ID format: {hospital_id_str}")

        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            raise CommandError(f"Hospital with ID {hospital_id} not found")

        deleted_count, _ = SuperAdminHospitalAccess.objects.filter(
            super_admin=super_admin,
            hospital=hospital,
        ).delete()

        if deleted_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Revoked {super_admin.email} access from {hospital.name}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"⏭️  {super_admin.email} did not have access to {hospital.name}"
                )
            )
