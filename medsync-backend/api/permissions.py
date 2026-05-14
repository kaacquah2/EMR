"""
Backward-compatible import path for RBAC. Canonical module: ``shared.permissions``.
"""

from shared.permissions import (  # noqa: F401
    ALERT_RESOLVE_ROLES,
    PERMISSION_MAP,
    PERMISSION_MATRIX,
    PermissionEnforcementMiddleware,
    PermissionValidator,
    RequiresRole,
    get_client_ip,
    is_uuid,
    require_role,
)
from rest_framework import permissions


class MustChangePasswordPermission(permissions.BasePermission):
    """
    Enforces that users with must_change_password_on_login=True
    can ONLY access specific password-change related endpoints.

    This replaces the middleware-based enforcement to ensure compatibility
    with DRF's JWT authentication, which populates request.user later
    than standard Django authentication middleware.
    """

    # Endpoints that are ALWAYS allowed even if password change is required
    SAFE_AUTH_PATH_BASENAMES = [
        "change_password_on_login",
        "logout",
        "me",
        "refresh",
    ]

    def has_permission(self, request, view):
        # Allow if user is not authenticated (other permissions will handle this)
        if not request.user or not request.user.is_authenticated:
            return True

        # If user doesn't need to change password, allow everything
        if not getattr(request.user, "must_change_password_on_login", False):
            return True

        # If user MUST change password, check if the current view is allowed
        # We check the view function name or a custom attribute if needed
        view_name = getattr(view, "__name__", "")
        if view_name in self.SAFE_AUTH_PATH_BASENAMES:
            return True

        # Also allow health check
        if view_name == "health":
            return True

        # Deny access to everything else
        return False
