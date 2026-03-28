"""Root URL handlers for serverless hosts (e.g. Vercel) that probe `/` and `/favicon.ico`."""

import base64

from django.http import HttpResponse, JsonResponse

# Minimal 1x1 transparent PNG (served as image/png for /favicon.ico).
_FAVICON_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def api_root(request):
    """GET / — identify API and avoid noisy 404s on serverless root URLs."""
    if request.method != "GET":
        return HttpResponse(status=405)
    return JsonResponse(
        {
            "service": "MedSync API",
            "api": "/api/v1/",
            "health": "/api/v1/health",
        }
    )


def favicon(request):
    """GET /favicon.ico — quiet browser default requests."""
    return HttpResponse(_FAVICON_PNG, content_type="image/png")
