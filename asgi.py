"""
Vercel Python entrypoint: exposes `app` for the serverless runtime.

Django lives under medsync-backend/; the repo root keeps requirements.txt for deploy.
"""
import os
import sys
from pathlib import Path

_backend = Path(__file__).resolve().parent / "medsync-backend"
sys.path.insert(0, str(_backend))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

from medsync_backend.asgi import application  # noqa: E402

app = application
