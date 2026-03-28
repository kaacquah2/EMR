"""
ASGI config for medsync_backend (Django Channels + HTTP).

Vercel's Python runtime uses an HTTP-only ASGI adapter (Mangum). The Channels
ProtocolTypeRouter + WebSocket stack is not supported there and can crash at
cold start. On VERCEL=1 we expose plain Django HTTP ASGI only; use Railway for
WebSockets / full Channels.
"""
import os

from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medsync_backend.settings")

if os.environ.get("VERCEL") == "1":
    application = get_asgi_application()
else:
    django_asgi_app = get_asgi_application()

    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    from api.routing import websocket_urlpatterns

    application = ProtocolTypeRouter(
        {
            "http": django_asgi_app,
            "websocket": AllowedHostsOriginValidator(URLRouter(websocket_urlpatterns)),
        }
    )
