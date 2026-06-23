"""
Production bootstrap — run once per deploy or in CI pre-deploy.

Validates required secrets, runs migrations, warms cache table, and collects static files.
"""

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = "Validate production configuration and apply database/static setup"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-collectstatic",
            action="store_true",
            help="Skip collectstatic (e.g. when static assets are built in Docker)",
        )
        parser.add_argument(
            "--check-only",
            action="store_true",
            help="Only validate settings and connectivity; do not migrate",
        )

    def handle(self, *args, **options):
        self._validate_production_settings()
        self._check_database()

        if options["check_only"]:
            self.stdout.write(self.style.SUCCESS("Production checks passed (check-only mode)."))
            return

        self.stdout.write("Running migrations...")
        call_command("migrate", "--noinput", verbosity=1)

        try:
            call_command("createcachetable", verbosity=0)
        except Exception as exc:
            self.stdout.write(self.style.WARNING(f"createcachetable: {exc}"))

        if not options["skip_collectstatic"]:
            self.stdout.write("Collecting static files...")
            call_command("collectstatic", "--noinput", verbosity=1)

        self.stdout.write(self.style.SUCCESS("Production setup complete."))

    def _validate_production_settings(self):
        if settings.DEBUG:
            raise CommandError("Refusing setup_production while DEBUG=True.")

        for name in ("SECRET_KEY", "FIELD_ENCRYPTION_KEY", "AUDIT_LOG_SIGNING_KEY"):
            if not getattr(settings, name, None):
                raise CommandError(f"{name} must be set in production.")

        if getattr(settings, "LLM_MODE", "") == "mock" and getattr(settings, "ENV", "").lower() == "production":
            raise CommandError("LLM_MODE=mock is not permitted when ENV=production.")

        if "sqlite" in (settings.DATABASES.get("default", {}).get("ENGINE", "") or ""):
            raise CommandError("SQLite is not allowed for production setup.")

    def _check_database(self):
        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        except Exception as exc:
            raise CommandError(f"Database connectivity failed: {exc}") from exc

