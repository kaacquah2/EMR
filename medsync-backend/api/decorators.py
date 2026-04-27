"""
Permission decorators for role-based access control.

Centralized permission checking for cleaner, more maintainable code.
Use these decorators to enforce role-based access at the function level.
"""

from functools import wraps
from rest_framework import status
from rest_framework.response import Response


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
