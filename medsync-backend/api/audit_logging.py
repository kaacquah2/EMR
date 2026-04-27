"""
PHASE 2-3: Enhanced Audit Logging

Expands audit logging to capture:
- All sensitive operations (not just CREATE/UPDATE/DELETE)
- Context information (IP, user agent, hospital, department)
- Failed operations and security events
- Rate limiting and throttling events
- Object-level access attempts (allowed and denied)
"""

from core.models import AuditLog, User
from django.utils import timezone
from api.utils import sanitize_audit_resource_id, get_client_ip
import json
import re


# ============================================================================
# ENHANCED AUDIT LOG ACTIONS
# ============================================================================

# Extend AuditLog.ACTIONS to include Phase 2-3 events
EXTENDED_AUDIT_ACTIONS = [
    # Authentication events
    ('LOGIN', 'Login Successful'),
    ('LOGIN_FAILED', 'Login Failed'),
    ('LOGOUT', 'Logout'),
    ('MFA_VERIFY', 'MFA Code Verified'),
    ('MFA_FAILED', 'MFA Code Failed'),
    ('PASSWORD_RESET_REQUEST', 'Password Reset Requested'),
    ('PASSWORD_RESET', 'Password Reset Completed'),
    ('PASSWORD_RESET_FAILED', 'Password Reset Failed'),

    # Account security
    ('ACCOUNT_LOCKED', 'Account Locked'),
    ('ACCOUNT_UNLOCKED', 'Account Unlocked'),
    ('ACCOUNT_ACTIVATED', 'Account Activated'),
    ('MFA_ENABLED', 'MFA Enabled'),
    ('MFA_DISABLED', 'MFA Disabled'),

    # Data access
    ('VIEW', 'View Record'),
    ('VIEW_PATIENT_RECORD', 'View Patient Record'),
    ('VIEW_CROSS_FACILITY_RECORD', 'View Cross-Facility Record'),
    ('SEARCH_PATIENT', 'Patient Search'),
    ('EXPORT_DATA', 'Data Export'),
    ('VIEW_AUDIT_LOG', 'Audit Log Accessed'),

    # Data modification
    ('CREATE', 'Create Record'),
    ('UPDATE', 'Update Record'),
    ('DELETE', 'Delete Record'),
    ('BULK_IMPORT', 'Bulk Import'),

    # Sensitive operations
    ('BREAK_GLASS_ACCESS', 'Emergency Break-Glass Access'),
    ('CROSS_FACILITY_ACCESS', 'Cross-Facility Data Access'),
    ('ROLE_CHANGE', 'User Role Changed'),
    ('HOSPITAL_CHANGE', 'Hospital Assignment Changed'),
    ('PERMISSIONS_MODIFIED', 'Permissions Modified'),

    # Admin actions
    ('USER_CREATED', 'User Created'),
    ('USER_DEACTIVATED', 'User Deactivated'),
    ('USER_REACTIVATED', 'User Reactivated'),
    ('HOSPITAL_CREATED', 'Hospital Created'),
    ('HOSPITAL_UPDATED', 'Hospital Updated'),

    # Security events
    ('RATE_LIMIT_HIT', 'Rate Limit Exceeded'),
    ('PERMISSION_DENIED', 'Permission Denied'),
    ('SUSPICIOUS_ACTIVITY', 'Suspicious Activity Detected'),
    ('FAILED_OBJECT_ACCESS', 'Object Access Denied'),
    ('VIEW_AS_HOSPITAL', 'View As Hospital'),

    # Error logging
    ('ERROR', 'Application Error'),
]


# ============================================================================
# ENHANCED AUDIT LOG HELPER
# ============================================================================

def _contains_phi(text: str) -> bool:
    """Detect common PHI patterns in text to prevent accidental logging."""
    if not isinstance(text, str):
        return False

    phi_patterns = [
        r"\b\d{3}-\d{2}-\d{4}\b",          # SSN-like patterns
        r"\b\d{10,}\b",                    # Long numeric identifiers (phone, IDs)
        r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b",  # Simple First Last name pattern
        r"[A-Z][a-z]+@",                   # Name in email prefix
    ]

    for pattern in phi_patterns:
        if re.search(pattern, text):
            return True
    return False


def audit_log_extended(
    user,
    action,
    resource_type=None,
    resource_id=None,
    hospital=None,
    request=None,
    extra_data=None,
    status_code=None,
    error_message=None,
):
    """
    PHASE 2-3: Enhanced audit logging with context information and PHI sanitization.

    This implementation enforces a strict whitelist for extra_data keys and
    performs lightweight PHI pattern checks on free-text fields to avoid
    accidentally persisting PHI in audit logs.
    """
    if not user or not action:
        return None

    # Sanitize resource_id to avoid logging PHI or tokens
    resource_id = sanitize_audit_resource_id(resource_id)

    # Extract request context if provided
    ip_address = None
    user_agent = None

    if request:
        ip_address = get_client_ip(request)
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:500]

    # Use hospital from request if available (for view-as scoping)
    if not hospital and request and hasattr(request, "effective_hospital"):
        hospital = request.effective_hospital

    # Use user's hospital as fallback
    if not hospital and user and user.hospital:
        hospital = user.hospital

    # Whitelist allowed extra_data keys
    ALLOWED_EXTRA_DATA_KEYS = {
        "action_type",              # Administrative reason
        "view_as_hospital_id",      # Super admin scoping
        "view_as_hospital_name",    # For context (not PHI)
        "access_denied",            # Boolean
        "reason",                   # Action reason (must be generic)
        "ip_address",               # Safe context
        "user_agent",               # Safe context
        "http_status",              # Status code
        "error_message",            # Must NOT contain PHI
        "failed_attempts",          # Counters
        "locked_until",
        "item_count",
    }

    sanitized_extra = {}
    if extra_data:
        for key, value in extra_data.items():
            if key not in ALLOWED_EXTRA_DATA_KEYS:
                # Reject unknown keys to avoid PHI leakage
                import logging

                logger = logging.getLogger(__name__)
                logger.warning(f"Rejected extra_data key in audit log: {key} (not whitelisted)")
                continue

            if key == "reason":
                if isinstance(value, str) and len(value) < 200:
                    if not _contains_phi(value):
                        sanitized_extra[key] = value
                    else:
                        sanitized_extra[key] = "[REDACTED: contains PHI]"
                continue

            sanitized_extra[key] = value

    # Add context automatically (overrides any caller-supplied values)
    if ip_address:
        sanitized_extra["ip_address"] = ip_address
    if user_agent:
        sanitized_extra["user_agent"] = user_agent
    if status_code:
        sanitized_extra["http_status"] = status_code
    if error_message:
        # Ensure error_message does not accidentally contain PHI
        if isinstance(error_message, str) and _contains_phi(error_message):
            sanitized_extra["error_message"] = "[REDACTED: contains PHI]"
        else:
            sanitized_extra["error_message"] = error_message

    try:
        audit = AuditLog.objects.create(
            user=user,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            hospital=hospital,
            ip_address=ip_address,
            user_agent=user_agent,
            extra_data=sanitized_extra or None,
        )
        return audit
    except Exception as e:
        # Prevent audit logging failures from breaking application
        print(f"Failed to create audit log: {e}")
        return None


# ============================================================================
# SENSITIVE OPERATION LOGGING
# ============================================================================

def log_authentication_event(user_email, success, request, error_reason=None):
    """
    PHASE 2: Log login attempts (successful and failed).

    Args:
        user_email: Email address attempting login
        success: Boolean - was login successful
        request: HTTP request object
        error_reason: If failed, reason (invalid credentials, locked, etc.)
    """
    try:
        user = User.objects.get(email=user_email) if success else None
    except User.DoesNotExist:
        user = None

    action = 'LOGIN' if success else 'LOGIN_FAILED'

    extra_data = {}
    if not success and error_reason:
        extra_data['reason'] = error_reason

    audit_log_extended(
        user=user,
        action=action,
        resource_type='User',
        resource_id=user.id if user else user_email,
        request=request,
        extra_data=extra_data,
    )


def log_mfa_event(user, success, request, error_reason=None, extra_data=None):
    """
    PHASE 2: Log MFA verification attempts.
    """
    action = 'MFA_VERIFY' if success else 'MFA_FAILED'

    ed = dict(extra_data or {})
    if not success and error_reason:
        ed['reason'] = error_reason

    audit_log_extended(
        user=user,
        action=action,
        resource_type='User',
        resource_id=user.id,
        request=request,
        extra_data=ed,
    )


def log_rate_limit_exceeded(request, action_type):
    """
    PHASE 2: Log rate limiting events.

    Args:
        request: HTTP request
        action_type: What action was rate-limited (login, mfa, password_reset, etc.)
    """
    user = request.user if request.user and request.user.is_authenticated else None

    extra_data = {
        'action_type': action_type,
        'ip_address': get_client_ip(request),
    }

    audit_log_extended(
        user=user,
        action='RATE_LIMIT_HIT',
        resource_type='System',
        request=request,
        extra_data=extra_data,
        status_code=429,
    )


def log_permission_denied(user, action, resource_type, resource_id, reason, request):
    """
    PHASE 2: Log failed access attempts (for security monitoring).

    Args:
        user: User attempting access
        action: What they tried to do
        resource_type: Type of resource
        resource_id: Resource ID
        reason: Why they were denied
        request: HTTP request
    """
    extra_data = {'denied_reason': reason}

    audit_log_extended(
        user=user,
        action='FAILED_OBJECT_ACCESS',
        resource_type=resource_type,
        resource_id=resource_id,
        request=request,
        extra_data=extra_data,
        status_code=403,
        error_message=reason,
    )


def log_sensitive_operation(user, operation, resource_type, resource_id, request, details=None):
    """
    PHASE 2-3: Log sensitive operations (break-glass, cross-facility, role changes, etc.).

    Args:
        user: User performing operation
        operation: Type (BREAK_GLASS_ACCESS, ROLE_CHANGE, etc.)
        resource_type: Type of resource
        resource_id: Resource ID
        request: HTTP request
        details: Additional context dict
    """
    extra_data = details or {}

    # Always include IP for sensitive ops
    extra_data['ip_address'] = get_client_ip(request)

    audit_log_extended(
        user=user,
        action=operation,
        resource_type=resource_type,
        resource_id=resource_id,
        request=request,
        extra_data=extra_data,
    )


def log_bulk_operation(user, operation_type, resource_type, count, request, details=None):
    """
    PHASE 2: Log bulk operations (imports, exports, deletions).

    Args:
        user: User performing operation
        operation_type: BULK_IMPORT, EXPORT_DATA, etc.
        resource_type: What type of bulk operation
        count: Number of items affected
        request: HTTP request
        details: Additional context
    """
    extra_data = details or {}
    extra_data['item_count'] = count

    audit_log_extended(
        user=user,
        action=operation_type,
        resource_type=resource_type,
        request=request,
        extra_data=extra_data,
    )


# ============================================================================
# COMPLIANCE HELPERS
# ============================================================================

def get_user_activity_summary(user, days=30):
    """
    PHASE 3: Generate user activity report for compliance.

    Returns:
        dict with user's actions over past N days
    """
    from datetime import timedelta

    cutoff = timezone.now() - timedelta(days=days)

    logs = AuditLog.objects.filter(
        user=user,
        timestamp__gte=cutoff,
    )

    actions = {}
    for log in logs:
        action = log.action
        actions[action] = actions.get(action, 0) + 1

    return {
        'user_id': str(user.id),
        'email': user.email,
        'days': days,
        'total_actions': logs.count(),
        'actions_by_type': actions,
        'period_start': cutoff.isoformat(),
        'period_end': timezone.now().isoformat(),
    }


def detect_suspicious_activity(user, request):
    """
    PHASE 3: Detect suspicious patterns (multiple failed logins, rapid actions, etc.).

    Returns:
        bool: True if suspicious activity detected
    """
    from datetime import timedelta

    # Check for multiple failed logins in last 30 minutes
    recent_failures = AuditLog.objects.filter(
        user=user,
        action='LOGIN_FAILED',
        timestamp__gte=timezone.now() - timedelta(minutes=30),
    ).count()

    if recent_failures >= 3:
        log_sensitive_operation(
            user=user,
            operation='SUSPICIOUS_ACTIVITY',
            resource_type='User',
            resource_id=user.id,
            request=request,
            details={'activity': 'multiple_failed_logins', 'count': recent_failures},
        )
        return True

    # Check for rapid API calls (more than 100 in 5 minutes)
    rapid_calls = AuditLog.objects.filter(
        user=user,
        timestamp__gte=timezone.now() - timedelta(minutes=5),
    ).count()

    if rapid_calls > 100:
        log_sensitive_operation(
            user=user,
            operation='SUSPICIOUS_ACTIVITY',
            resource_type='System',
            resource_id=user.id,
            request=request,
            details={'activity': 'rapid_api_calls', 'count': rapid_calls},
        )
        return True

    return False


def export_audit_logs_for_compliance(hospital=None, days=90):
    """
    PHASE 3: Export audit logs for compliance/HIPAA reporting.

    Args:
        hospital: Optional hospital to filter (None = all)
        days: Number of days to include (default 90 for HIPAA quarterly)

    Returns:
        CSV-formatted string of audit logs
    """
    from datetime import timedelta
    import csv
    from io import StringIO

    cutoff = timezone.now() - timedelta(days=days)

    logs = AuditLog.objects.filter(timestamp__gte=cutoff)

    if hospital:
        logs = logs.filter(hospital=hospital)

    # Build CSV
    output = StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Timestamp',
        'User Email',
        'Action',
        'Resource Type',
        'Resource ID',
        'Hospital',
        'IP Address',
        'Status',
        'Notes',
    ])

    # Data rows
    for log in logs:
        notes = ''
        if log.extra_data:
            notes = json.dumps(log.extra_data)[:200]  # Truncate for CSV

        writer.writerow([
            log.timestamp.isoformat(),
            log.user.email if log.user else 'SYSTEM',
            log.action,
            log.resource_type or '',
            log.resource_id or '',
            log.hospital.name if log.hospital else '',
            log.ip_address or '',
            'OK',
            notes,
        ])

    return output.getvalue()
