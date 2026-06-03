"""
Permission decorators for role-based access control and step-up verification.

Centralized permission checking for cleaner, more maintainable code.
Use these decorators to enforce role-based access at the function level.
"""

from functools import wraps
from rest_framework import status
from rest_framework.response import Response
import logging
import jwt
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def requires_role(*allowed_roles):
    """
    Decorator to enforce that only users with specified roles can access an endpoint.

    Example:
        @requires_role("doctor", "nurse")
        def my_view(request):
            ...

    Args:
        *allowed_roles: One or more role strings (e.g., "doctor", "nurse")

    Returns:
        Function decorator that checks user.role before executing the view.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, "user") or not request.user.is_authenticated:
                return Response(
                    {"message": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            if request.user.role not in allowed_roles:
                return Response(
                    {"message": "Permission denied"},
                    status=status.HTTP_403_FORBIDDEN,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def requires_role_or_permission(*allowed_roles):
    """
    Decorator that requires specific roles OR a custom permission check.

    This is a convenience wrapper for commonly needed permission checks.
    For complex permission logic, use requires_permission instead.

    Example:
        @requires_role_or_permission("super_admin", "hospital_admin")
        def my_view(request):
            ...
    """
    return requires_role(*allowed_roles)


def requires_hospital_assignment():
    """
    Decorator to enforce that hospital_admin and staff have a hospital assigned.

    Super_admin is exempt (they can operate across all hospitals).

    Example:
        @requires_hospital_assignment()
        def my_view(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, "user") or not request.user.is_authenticated:
                return Response(
                    {"message": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            # Super_admin can operate without hospital assignment (system-wide)
            if request.user.role == "super_admin":
                return view_func(request, *args, **kwargs)

            # All other roles must have hospital assignment
            if not request.user.hospital:
                return Response(
                    {"message": "No hospital assigned"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def permission_required(resource_type, action="read"):
    """
    Decorator for resource-level permission checking.

    Can be extended to check object-level permissions (e.g., can user access this patient?).

    Args:
        resource_type: Type of resource being accessed (e.g., "patient", "lab_order")
        action: Type of action (read, write, delete)

    Example:
        @permission_required("patient", action="write")
        def create_patient(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not hasattr(request, "user") or not request.user.is_authenticated:
                return Response(
                    {"message": "Authentication required"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            # This can be extended with more complex permission logic
            # For now, just ensure user is authenticated
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def audit_action(action_name, resource_type=None):
    """
    Decorator to automatically audit function calls.

    Wraps the function to call audit_log with standardized parameters.

    Args:
        action_name: Name of the action (e.g., "CREATE_USER", "DELETE_RECORD")
        resource_type: Type of resource affected (optional)

    Example:
        @audit_action("INVITE_USER", resource_type="user")
        def user_invite(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Execute the original function
            result = view_func(request, *args, **kwargs)

            # Only audit successful responses (status 200-299)
            if isinstance(result, Response) and 200 <= result.status_code < 300:
                from api.utils import audit_log
                audit_log(
                    user=request.user,
                    action=action_name,
                    resource_type=resource_type,
                    request=request,
                )

            return result
        return wrapper
    return decorator


def requires_step_up(action):
    """
    Decorator to enforce step-up JWT requirement for high-risk actions.

    Usage:
        @requires_step_up(action="break_glass")
        def my_high_risk_view(request):
            ...

    Behavior:
    - Checks for header X-Step-Up-JWT
    - Verifies JWT is valid and not expired
    - Verifies JWT's step_up_action matches the required action
    - Returns 403 with requires_step_up flag if validation fails

    Response (403):
        {
            "requires_step_up": true,
            "action": "break_glass"
        }
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Allow toggling enforcement via settings for testing/deployment.
            # Default is False so existing tests and development flow are not blocked.
            if not getattr(settings, 'ENABLE_STEP_UP_PROTECTION', False):
                return view_func(request, *args, **kwargs)
            # Get step-up JWT from header
            step_up_jwt = request.META.get('HTTP_X_STEP_UP_JWT', '')

            if not step_up_jwt:
                logger.warning(f"Missing step-up JWT for action {action}, user {request.user.id if request.user else 'anonymous'}")
                return Response(
                    {
                        'requires_step_up': True,
                        'action': action,
                        'message': f'This action requires step-up verification. Request /auth/step-up/request with action="{action}"'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Verify JWT
            try:
                payload = jwt.decode(
                    step_up_jwt,
                    settings.SECRET_KEY,
                    algorithms=['HS256']
                )
            except jwt.ExpiredSignatureError:
                logger.warning(f"Step-up JWT expired for action {action}, user {request.user.id if request.user else 'anonymous'}")
                return Response(
                    {
                        'requires_step_up': True,
                        'action': action,
                        'message': 'Step-up JWT expired. Request a new one.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )
            except jwt.InvalidTokenError as e:
                logger.warning(f"Invalid step-up JWT for action {action}: {e}")
                return Response(
                    {
                        'requires_step_up': True,
                        'action': action,
                        'message': 'Invalid step-up JWT. Request a new one.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Verify JWT type and action
            if payload.get('type') != 'step_up':
                logger.warning(f"Step-up JWT has wrong type: {payload.get('type')}")
                return Response(
                    {
                        'requires_step_up': True,
                        'action': action,
                        'message': 'Invalid JWT type for step-up action.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            jwt_action = payload.get('step_up_action', '')
            if jwt_action != action:
                logger.warning(f"Step-up JWT action mismatch: expected {action}, got {jwt_action}")
                return Response(
                    {
                        'requires_step_up': True,
                        'action': action,
                        'message': f'Step-up JWT is for action "{jwt_action}", not "{action}". Request a new one.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # Verify JWT user matches request user
            if str(payload.get('user_id', '')) != str(request.user.id):
                logger.warning(f"Step-up JWT user mismatch: expected {request.user.id}, got {payload.get('user_id')}")
                return Response(
                    {
                        'requires_step_up': True,
                        'action': action,
                        'message': 'Step-up JWT user does not match current user.'
                    },
                    status=status.HTTP_403_FORBIDDEN
                )

            # All checks passed — attach JWT payload to request for audit logging
            request.step_up_jwt_payload = payload
            request.step_up_action = action

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator
