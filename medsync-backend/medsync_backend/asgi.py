"""
ASGI config for medsync_backend.

MedSync runs as a standard WSGI application via Gunicorn.
This ASGI entrypoint is provided for compatibility (e.g. Railway, Render)
but uses the plain Django ASGI handler — no WebSocket support required.
"""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

from django.core.asgi import get_asgi_application  # noqa: E402

application = get_asgi_application()
