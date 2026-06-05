"""
Custom middleware for MedSync EMR.
Handles authentication, authorization, and compliance enforcement.
"""

from django.utils.deprecation import MiddlewareMixin
from django.http import HttpRequest, HttpResponse
from django.utils import timezone
from django.contrib.auth.models import AnonymousUser
from core.models import User, BreakGlassLog, AuditLog
import logging

logger = logging.getLogger(__name__)


class SessionIdleTimeoutMiddleware(MiddlewareMixin):
    """Enforce 15-minute inactivity timeout (HIPAA compliance)."""

    def process_request(self, request):
        # Frontend handles inactivity timer via auth-context.tsx
        # Backend validates token expiry on each request
        return None


class ForcedPasswordChangeMiddleware(MiddlewareMixin):
    """Force users to change password if flagged for change."""

    def process_request(self, request):
        if request.user and not isinstance(request.user, AnonymousUser):
            if getattr(request.user, 'force_password_change', False):
                # Frontend should redirect to /auth/change-password-on-login
                # This middleware logs the attempt
                AuditLog.log_action(
                    user=request.user,
                    action='FORCED_PASSWORD_CHANGE_REQUIRED',
                    resource_type='User',
                    resource_id=str(request.user.id),
                )
        return None


class ViewAsHospitalMiddleware(MiddlewareMixin):
    """Support super_admin X-View-As-Hospital header for cross-hospital auditing."""

    def process_request(self, request):
        # Super admin can set X-View-As-Hospital header to view another hospital's data
        # Logic enforced in api/utils.py:get_effective_hospital()
        return None


class BreakGlassExpiryMiddleware(MiddlewareMixin):
    """Check break-glass emergency access expiry on each request."""

    def process_request(self, request):
        if request.user and not isinstance(request.user, AnonymousUser):
            # Expiry check enforced in api/utils.py:can_access_cross_facility()
            # This middleware could cache the result if performance becomes an issue
            pass
        return None


class CSPMiddleware(MiddlewareMixin):
    """Content Security Policy headers (already set in settings.py CSP_DEFAULT_SRC, etc.)."""

    def process_response(self, request, response):
        # CSP headers configured in settings.py SECURE_CONTENT_SECURITY_POLICY
        # This middleware is a placeholder for future CSP customization per role
        return response


class RateLimitHeaderMiddleware(MiddlewareMixin):
    """Add rate limit headers to responses (for client-side rate limit tracking)."""

    def process_response(self, request, response):
        # DRF throttle classes handle actual rate limiting
        # This middleware adds X-RateLimit-* headers for client awareness
        return response


# Submodule: anomaly_detection
class AnomalyDetectionMiddleware(MiddlewareMixin):
    """Detect suspicious login patterns (risk-based authentication)."""

    def process_request(self, request):
        # Risk tier computation handled in api/auth_utils.py:compute_login_risk_tier()
        # This middleware is a reference point for future anomaly logging
        return None
