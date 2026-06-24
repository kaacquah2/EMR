"""
Test settings — used exclusively by the pytest suite.
Switch via pytest.ini: DJANGO_SETTINGS_MODULE = medsync_backend.settings_test

This module sets required env vars BEFORE importing base settings so the
import succeeds even in CI where no .env file is present.  It then overrides
DATABASES and CACHES to in-memory so the test suite runs without Postgres.
"""

import base64
import os
import secrets

# ── Required secrets (generate ephemeral values for each test run in CI) ──────
os.environ.setdefault("SECRET_KEY", f"test-only-{secrets.token_hex(32)}")
os.environ.setdefault("AUDIT_LOG_SIGNING_KEY", secrets.token_hex(32))
os.environ.setdefault(
    "FIELD_ENCRYPTION_KEY",
    base64.urlsafe_b64encode(secrets.token_bytes(32)).decode(),
)

# ── Database: tell base settings to allow in-memory SQLite ───────────────────
os.environ["MEDSYNC_TEST_SQLITE"] = "1"
os.environ.setdefault("DATABASE_URL", "")   # cleared so settings falls to _TEST_SQLITE branch

# ── Misc settings expected by base settings.py ───────────────────────────────
os.environ.setdefault("DEBUG", "True")      # skips production-only checks (CORS, WebAuthn, etc.)

# ── Import and re-export everything from base settings ───────────────────────
from medsync_backend.settings import *  # noqa: F401, F403, E402

# ── Test-only overrides ───────────────────────────────────────────────────────
# Use in-memory SQLite (fast, no Postgres required, no schema migration cost).
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

# Use in-memory cache so MFA and rate-limit state doesn't bleed between tests.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "test-cache",
    }
}

# Expose a flag tests can check to assert they're running under the test config.
TESTING = True
