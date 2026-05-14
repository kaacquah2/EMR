"""
ASGI config for medsync_backend (Django Channels + HTTP).

Vercel's Python runtime uses an HTTP-only ASGI adapter (Mangum). The Channels
ProtocolTypeRouter + WebSocket stack is not supported there and can crash at
cold start. On VERCEL=1 we expose plain Django HTTP ASGI only; use Railway for
WebSockets / full Channels.
"""
import os
import sys
from pathlib import Path

# Vercel may use this file as the entrypoint (e.g. medsync-backend/medsync_backend/asgi.py).
# Without the backend root on sys.path, Python cannot resolve the package name
# `medsync_backend` (parent dir of this package must be importable).
_backend_root = Path(__file__).resolve().parent.parent
if str(_backend_root) not in sys.path:
    sys.path.insert(0, str(_backend_root))

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

if os.environ.get("VERCEL") == "1":
    application = get_asgi_application()
else:
    django_asgi_app = get_asgi_application()

    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    from api.routing import websocket_urlpatterns
    from api.middleware.ws_auth import JWTAuthMiddleware

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AllowedHostsOriginValidator(
                JWTAuthMiddleware(URLRouter(websocket_urlpatterns))
            ),
        }
    )
