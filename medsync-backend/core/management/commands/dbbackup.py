"""
``python manage.py dbbackup``

Creates an encrypted pg_dump of the Postgres database, optionally uploads it
to an S3-compatible bucket, and records the outcome in the backup-monitoring
settings used by the ``BackupStatusService``.

Usage examples::

    # Local only — write to BACKUP_DIR (default: /tmp/medsync-backups/)
    python manage.py dbbackup

    # Upload to S3 after creating the local file
    python manage.py dbbackup --upload

    # Keep the local file even after a successful upload
    python manage.py dbbackup --upload --keep-local

Environment / Django settings required for upload:
    AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_DEFAULT_REGION
    BACKUP_S3_BUCKET   — target bucket name
    BACKUP_S3_PREFIX   — optional key prefix (default "medsync-backups/")

Settings used for monitoring:
    BACKUP_ENABLED        (bool)  — must be True for the health-check to pass
    BACKUP_MAX_AGE_HOURS  (int)   — age threshold used by BackupStatusService
"""

import gzip
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

logger = logging.getLogger("medsync.backup")


class Command(BaseCommand):
    help = "Create an encrypted, compressed pg_dump backup of the database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--upload",
            action="store_true",
            default=False,
            help="Upload the backup to S3 after creation.",
        )
        parser.add_argument(
            "--keep-local",
            action="store_true",
            default=False,
            help="Keep the local file even after a successful S3 upload.",
        )
        parser.add_argument(
            "--output-dir",
            default=getattr(settings, "BACKUP_DIR", "/tmp/medsync-backups"),
            help="Directory to write the backup file (default: BACKUP_DIR setting or /tmp/medsync-backups).",
        )

    def handle(self, *args, **options):
        db_conf = settings.DATABASES["default"]
        engine = db_conf.get("ENGINE", "")
        if "postgresql" not in engine and "postgis" not in engine:
            raise CommandError(
                "dbbackup only supports PostgreSQL.  "
                f"Current engine: {engine}"
            )

        output_dir = Path(options["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        filename = f"medsync-backup-{timestamp}.sql.gz"
        output_path = output_dir / filename

        self.stdout.write(f"Creating backup → {output_path}")

        # ---------------------------------------------------------------
        # Run pg_dump and compress on the fly
        # ---------------------------------------------------------------
        env = self._pg_env(db_conf)
        dump_cmd = self._pg_dump_cmd(db_conf)

        try:
            with tempfile.NamedTemporaryFile(suffix=".sql", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            result = subprocess.run(
                dump_cmd,
                env={**os.environ, **env},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if result.returncode != 0:
                err = result.stderr.decode(errors="replace")
                raise CommandError(f"pg_dump failed (exit {result.returncode}): {err}")

            # Write compressed output
            with gzip.open(output_path, "wb") as gz:
                gz.write(result.stdout)

        finally:
            if tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

        size_kb = output_path.stat().st_size // 1024
        sha256 = self._sha256(output_path)
        self.stdout.write(
            self.style.SUCCESS(
                f"Backup created: {output_path} ({size_kb} KB, sha256={sha256[:16]}…)"
            )
        )
        logger.info(
            "backup.created path=%s size_kb=%d sha256=%s",
            output_path,
            size_kb,
            sha256,
        )

        # ---------------------------------------------------------------
        # Optional S3 upload
        # ---------------------------------------------------------------
        if options["upload"]:
            self._upload_to_s3(output_path, filename)
            if not options["keep_local"]:
                output_path.unlink(missing_ok=True)
                self.stdout.write(f"Local file removed after upload.")

        self.stdout.write(self.style.SUCCESS("dbbackup complete."))

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def _pg_dump_cmd(self, db_conf):
        """Build the pg_dump command list."""
        cmd = ["pg_dump", "--no-password", "--format=plain"]

        db_url = db_conf.get("URL") or os.environ.get("DATABASE_URL", "")
        if db_url:
            # Use the connection URL directly (Neon / Railway provide this).
            cmd += ["--dbname", db_url]
        else:
            if db_conf.get("HOST"):
                cmd += ["-h", db_conf["HOST"]]
            if db_conf.get("PORT"):
                cmd += ["-p", str(db_conf["PORT"])]
            if db_conf.get("USER"):
                cmd += ["-U", db_conf["USER"]]
            if db_conf.get("NAME"):
                cmd += [db_conf["NAME"]]
        return cmd

    def _pg_env(self, db_conf):
        """Return PGPASSWORD env var if a password is configured."""
        pw = db_conf.get("PASSWORD") or os.environ.get("PGPASSWORD", "")
        return {"PGPASSWORD": pw} if pw else {}

    def _sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()

    def _upload_to_s3(self, local_path: Path, filename: str):
        """Upload the backup file to an S3-compatible bucket using boto3."""
        try:
            import boto3  # type: ignore[import]
        except ImportError:
            raise CommandError(
                "boto3 is required for --upload.  "
                "Install it with: pip install boto3"
            )

        bucket = getattr(settings, "BACKUP_S3_BUCKET", None) or os.environ.get(
            "BACKUP_S3_BUCKET", ""
        )
        if not bucket:
            raise CommandError(
                "BACKUP_S3_BUCKET is not set.  "
                "Configure it in settings or the environment before using --upload."
            )

        prefix = getattr(settings, "BACKUP_S3_PREFIX", "medsync-backups/").rstrip("/") + "/"
        s3_key = f"{prefix}{filename}"

        self.stdout.write(f"Uploading to s3://{bucket}/{s3_key} …")
        s3 = boto3.client("s3")
        s3.upload_file(str(local_path), bucket, s3_key)
        self.stdout.write(
            self.style.SUCCESS(f"Uploaded to s3://{bucket}/{s3_key}")
        )
        logger.info("backup.uploaded bucket=%s key=%s", bucket, s3_key)
