"""
Middleware for request-scoped context used by API views.
"""

from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from api.utils import get_effective_hospital
from core.models import AuditLog
from interop.models import BreakGlassLog


def _rendered_json_response(payload, status_code: int):
    """
    Return a DRF Response that is already rendered to bytes.
    Needed when returning from Django middleware (outside DRF view pipeline).
    """
    resp = Response(payload, status=status_code)
    resp.accepted_renderer = JSONRenderer()
    resp.accepted_media_type = "application/json"
    resp.renderer_context = {}
    resp.render()
    return resp


class ViewAsHospitalMiddleware:
    """
    Reads X-View-As-Hospital header for super_admin users with no facility.
    Validates the header (must be a valid active hospital UUID), sets
    request.effective_hospital for the request, and logs VIEW_AS_HOSPITAL once.
    All hospital-scoped views use get_request_hospital(request) which uses
    this value when set. Must run after AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        get_effective_hospital(request)
        return self.get_response(request)


class ForcedPasswordChangeMiddleware:
    """
    Enforces server-side password change after temporary password login.
    JWT-AWARE: Correctly identifies users even if they are using Bearer tokens.

    If a user has must_change_password_on_login=True, only allows requests to:
    - /api/v1/auth/change-password-on-login
    - /api/v1/auth/logout
    - /api/v1/auth/me
    - /api/v1/auth/refresh

    All other requests are rejected with 403 Forbidden.
    Prevents users from bypassing the frontend flag.
    """

    # Endpoints allowed without password change
    ALLOWED_ENDPOINTS = [
        "/api/v1/auth/change-password-on-login",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/auth/refresh",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # 1. Ensure user is authenticated
        # If request.user is anonymous, it might be because DRF hasn't run yet
        user = request.user
        if not user or not user.is_authenticated:
            # Try to perform manual JWT authentication if Bearer token is present
            auth_header = request.META.get("HTTP_AUTHORIZATION", "")
            if auth_header.startswith("Bearer "):
                from rest_framework_simplejwt.authentication import JWTAuthentication

                try:
                    auth_result = JWTAuthentication().authenticate(request)
                    if auth_result:
                        user, _ = auth_result
                except Exception:
                    pass

        # 2. Check if user MUST change password
        if user and user.is_authenticated and getattr(user, "must_change_password_on_login", False):
            # Check if current path is in allowed list
            is_allowed = any(request.path.startswith(endpoint) for endpoint in self.ALLOWED_ENDPOINTS)

            if not is_allowed:
                return _rendered_json_response(
                    {
                        "detail": "Password change required. Please use POST /api/v1/auth/change-password-on-login",
                        "code": "PASSWORD_CHANGE_REQUIRED",
                    },
                    status_code=403,
                )

        return self.get_response(request)


class BreakGlassExpiryMiddleware:
    """
    Enforces break-glass time-window expiry at request level.

    Checks if any active break-glass log for the user has expired.
    If an expired break-glass log is found, returns 403 Forbidden and audits the attempt.

    This middleware catches expired break-glass access early, before views process the request.
    Must run after AuthenticationMiddleware to ensure request.user is available.
    """

    # Endpoints where break-glass access might be used
    BREAK_GLASS_ENDPOINTS = [
        "/api/v1/global-patient/",
        "/api/v1/break-glass",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only check authenticated users
        if not (request.user and request.user.is_authenticated):
            return self.get_response(request)

        # Only check endpoints where break-glass might be used
        is_protected_endpoint = any(request.path.startswith(endpoint) for endpoint in self.BREAK_GLASS_ENDPOINTS)

        if not is_protected_endpoint:
            return self.get_response(request)

        # Check for expired break-glass logs for this user
        # Get the most recent break-glass log for this user
        recent_log = (
            BreakGlassLog.objects.filter(accessed_by=request.user)
            .select_related("facility", "global_patient")
            .order_by("-created_at")
            .first()
        )

        # If there's a recent break-glass log and it's expired, block the request
        if recent_log and recent_log.is_expired():
            # Log the expired access attempt
            try:
                AuditLog.objects.create(
                    user=request.user,
                    action="BREAK_GLASS_EXPIRED_ACCESS",
                    resource_type="break_glass_log",
                    resource_id=recent_log.id,
                    hospital=recent_log.facility,
                    ip_address=request.META.get("REMOTE_ADDR", "127.0.0.1"),
                    user_agent=request.META.get("HTTP_USER_AGENT", "") or "",
                )
            except Exception:
                # Don't fail the middleware if audit logging fails
                pass

            return _rendered_json_response(
                {
                    "detail": "Break-glass access window expired",
                    "code": "BREAK_GLASS_EXPIRED",
                },
                status_code=403,
            )

        return self.get_response(request)


class RequestLoggingMiddleware:
    """
    PHASE 1 AUDIT FIX: Capture API traffic for observability.
    Logs method, path, status code, and duration for every request.
    Excluded sensitive paths (login, password resets).
    """

    EXCLUDED_PATHS = [
        "/api/v1/auth/login",
        "/api/v1/auth/mfa-verify",
        "/api/v1/auth/password-reset",
    ]

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time

        start_time = time.time()

        response = self.get_response(request)

        duration = time.time() - start_time

        # Avoid logging sensitive payloads by only logging meta info
        if not any(request.path.startswith(p) for p in self.EXCLUDED_PATHS):
            import logging

            logger = logging.getLogger("api.traffic")
            user_id = request.user.id if request.user and request.user.is_authenticated else "anon"
            logger.info(
                f"API_REQUEST | {request.method} {request.path} | "
                f"Status: {response.status_code} | Duration: {duration:.3f}s | User: {user_id}"
            )

        return response


class CSPMiddleware:
    """
    Injects Content-Security-Policy header into every response.
    Reads policy from settings.SECURE_CONTENT_SECURITY_POLICY.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        from django.conf import settings

        csp_config = getattr(settings, "SECURE_CONTENT_SECURITY_POLICY", None)

        if csp_config:
            # Construct CSP string from dictionary
            policies = []
            for directive, sources in csp_config.items():
                policies.append(f"{directive} {' '.join(sources)}")

            csp_string = "; ".join(policies)
            response["Content-Security-Policy"] = csp_string

        return response
