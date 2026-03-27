"""
One-off: record patients.0001 and records.0001 as applied so migration history
is consistent when interop.0001 was applied before these were added.

Run once when you see:
  InconsistentMigrationHistory: Migration interop.0001_initial is applied
  before its dependency patients.0001_blueprint_alerts_encounters

Then run: python manage.py migrate
"""

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.migrations.recorder import MigrationRecorder


class Command(BaseCommand):
    help = "Record patients.0001 and records.0001 as applied to fix inconsistent migration history (existing DB)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Only show what would be recorded.",
        )

    def handle(self, *args, **options):
        recorder = MigrationRecorder(connection)
        applied = recorder.applied_migrations()  # method, returns dict
        # Order matters: record dependencies first (core.0003 before patients/records.0001)
        to_record = [
            ("core", "0003_blueprint_alerts_encounters"),
            ("patients", "0001_blueprint_alerts_encounters"),
            ("records", "0001_blueprint_alerts_encounters"),
        ]
        if options["dry_run"]:
            for app, name in to_record:
                if (app, name) in applied:
                    self.stdout.write(f"Already applied: {app}.{name}")
                else:
                    self.stdout.write(f"Would record: {app}.{name}")
            return
        for app, name in to_record:
            if (app, name) in applied:
                self.stdout.write(f"Already applied: {app}.{name}")
                continue
            recorder.record_applied(app, name)
            self.stdout.write(self.style.SUCCESS(f"Recorded as applied: {app}.{name}"))
        self.stdout.write("Run: python manage.py migrate")
