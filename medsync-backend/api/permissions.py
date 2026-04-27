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
