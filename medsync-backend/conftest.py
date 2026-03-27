"""
⚠️  PYTEST CONFIGURATION - Test Only
This file should NEVER be deployed to production.
If conftest.py is loaded in production, settings below will force insecure behavior.
"""

import os
import django
import secrets

# Only run during pytest
if "pytest" not in os.sys.modules and "py.test" not in os.sys.argv:
    import warnings
    warnings.warn(
        "conftest.py was loaded outside pytest context. "
        "This should only happen during testing.",
        RuntimeWarning,
    )

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

# Force SQLite for tests so pytest works without Postgres (no test_neondb create/drop).
# Override .env so config("DATABASE_URL", default="") sees empty and settings use SQLite.
os.environ["DATABASE_URL"] = ""
os.environ["DEBUG"] = "True"
# Do NOT set SECRET_KEY here if not set - let the block below generate one

# Generate unique SECRET_KEY for each test run (prevents key reuse issues)
if "SECRET_KEY" not in os.environ:
    os.environ["SECRET_KEY"] = f"test-{secrets.token_hex(32)}"

django.setup()

pytest_plugins = ["pytest_django"]
