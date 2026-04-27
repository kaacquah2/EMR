"""
Optimistic locking helpers for concurrent update prevention.

Usage:
    # In view:
    check_version(encounter, request.data.get('version'))
    # ... make changes ...
    increment_version(encounter)
    encounter.save()
"""

from rest_framework import status
from rest_framework.response import Response


class VersionConflictError(Exception):
    """Raised when optimistic locking version mismatch detected."""
    def __init__(self, current_version, provided_version, updated_by=None):
        self.current_version = current_version
        self.provided_version = provided_version
        self.updated_by = updated_by
        super().__init__(
            f"Version conflict: record is at version {current_version}, "
            f"but you provided version {provided_version}"
        )


def check_version(instance, provided_version, updated_by_field='updated_by'):
    """
    Check if the provided version matches the current version.
    
    Args:
        instance: Model instance with version field
        provided_version: Version from client request
        updated_by_field: Field name that stores last updater (optional)
    
    Raises:
        VersionConflictError if versions don't match
    """
    if provided_version is None:
        return  # Version not provided - skip check (backward compatibility)
    
    try:
        provided_version = int(provided_version)
    except (TypeError, ValueError):
        return  # Invalid version format - skip check
    
    current_version = getattr(instance, 'version', 1)
    
    if provided_version != current_version:
        updated_by = None
        if hasattr(instance, updated_by_field):
            updater = getattr(instance, updated_by_field)
            if updater:
                updated_by = getattr(updater, 'full_name', str(updater))
        
        raise VersionConflictError(current_version, provided_version, updated_by)


def increment_version(instance):
    """
    Increment the version field on save.
    Call this before saving after successful validation.
    """
    if hasattr(instance, 'version'):
        instance.version = (instance.version or 0) + 1


def version_conflict_response(error: VersionConflictError):
    """
    Create a 409 Conflict response for version mismatch.
    """
    message = f"This record was updated by another user. Current version: {error.current_version}."
    if error.updated_by:
        message = f"This record was updated by {error.updated_by}. Please review changes and try again."
    
    return Response(
        {
            'message': message,
            'error': 'version_conflict',
            'current_version': error.current_version,
            'your_version': error.provided_version,
        },
        status=status.HTTP_409_CONFLICT
    )
