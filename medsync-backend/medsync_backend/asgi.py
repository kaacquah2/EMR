"""
ASGI config for medsync_backend.

Channels/WebSockets have been removed; this is a standard Django ASGI application
suitable for Uvicorn or Daphne. For production we use gunicorn WSGI (wsgi.py).
"""
import os
import sys
from pathlib import Path

_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

application = get_asgi_application()
