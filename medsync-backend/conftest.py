"""
⚠️  PYTEST CONFIGURATION — Test Only.
This file must never be deployed to production.

All Django settings for the test suite live in medsync_backend/settings_test.py,
which is referenced by pytest.ini (DJANGO_SETTINGS_MODULE = medsync_backend.settings_test).
That module sets required env vars before importing base settings, so there is no
timing issue with pytest-django's early settings import.
"""

pytest_plugins = ["pytest_django"]


