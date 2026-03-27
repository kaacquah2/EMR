"""
PHASE 2: Endpoint-Specific Rate Limiting

Implements per-endpoint rate limiting to protect against:
- Brute-force attacks on login/MFA
- Password reset spam
- API enumeration
- Denial of service
"""

from rest_framework.throttling import BaseThrottle, UserRateThrottle, AnonRateThrottle
from rest_framework.exceptions import Throttled
from django.core.cache import cache
from django.utils import timezone
from datetime import timedelta
import json


def _parse_rate(rate):
    """
    Parse rate string. Supports DRF style (num/m, num/h), numeric seconds (num/900s),
    and numeric+unit (num/15m, num/5m). Returns (num_requests, duration_seconds).
    """
    if rate is None:
        return (None, None)
    num, period = rate.split("/")
    num_requests = int(num.strip())
    period = period.strip().lower()
    if period.endswith("s") and period[:-1].isdigit():
        duration = int(period[:-1])
    elif len(period) >= 2 and period[-1] in "mhd" and period[:-1].isdigit():
        # e.g. 15m, 5m, 2h, 1d
        mult = {"m": 60, "h": 3600, "d": 86400}[period[-1]]
        duration = int(period[:-1]) * mult
    else:
        duration = {"s": 1, "m": 60, "h": 3600, "d": 86400}[period[0]]
    return (num_requests, duration)


# ============================================================================
# CUSTOM THROTTLE CLASSES
# ============================================================================

class LoginThrottle(AnonRateThrottle):
    """
    Rate limit login attempts: 5 attempts per 15 minutes per IP address.
    PHASE 2: Prevents brute-force password attacks.
    """
    scope = "login"
    rate = "5/15m"  # DRF parse_rate expects s/m/h/d; 15m = 900s

    def parse_rate(self, rate):
        return _parse_rate(rate)

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return None  # Don't throttle authenticated users
        from api.utils import get_client_ip
        ip = get_client_ip(request)
        return f"throttle_login_{ip}"


class MFAThrottle(AnonRateThrottle):
    """
    Rate limit MFA verification: 3 attempts per 5 minutes per IP address.
    PHASE 2 (Task 5): Prevents MFA brute-force attacks.
    """
    scope = "mfa"
    rate = "3/5m"  # DRF parse_rate expects s/m/h/d; 5m = 300s

    def parse_rate(self, rate):
        return _parse_rate(rate)

    def get_cache_key(self, request, view):
        from api.utils import get_client_ip
        ip = get_client_ip(request)
        return f"throttle_mfa_{ip}"


class MFAUserThrottle(UserRateThrottle):
    """
    **MEDIUM-2 FIX:** Per-user MFA rate limiting.
    
    Rate limit MFA verification: 30 attempts per hour per user.
    This prevents brute-force TOTP attacks even across multiple IPs.
    
    Combined with IP-based MFAThrottle:
    - IP-level: 3/5min (prevents single attacker, multiple IPs)
    - User-level: 30/hour (prevents distributed attacks)
    """
    scope = "mfa_user"
    rate = "30/hour"
    
    def parse_rate(self, rate):
        return _parse_rate(rate)
    
    def get_cache_key(self, request, view):
        # Only apply to MFA verification attempts
        mfa_token = None
        if hasattr(request, "data"):
            mfa_token = request.data.get("mfa_token")
        if not mfa_token and hasattr(request, "POST"):
            mfa_token = request.POST.get("mfa_token")
        if not mfa_token and hasattr(request, "body"):
            try:
                body = request.body.decode("utf-8") if isinstance(request.body, (bytes, bytearray)) else str(request.body)
                obj = json.loads(body) if body else {}
                if isinstance(obj, dict):
                    mfa_token = obj.get("mfa_token")
            except Exception:
                mfa_token = None
        if not mfa_token:
            return None  # Skip if no MFA token present
        
        # Get user ID from MFASession database lookup
        try:
            from core.models import MFASession
            mfa_session = MFASession.objects.get(token=mfa_token)
            return f"throttle_mfa_user_{mfa_session.user_id}"
        except Exception:
            return None  # Invalid token or missing session, skip throttling



class PasswordResetThrottle(AnonRateThrottle):
    """
    Rate limit password reset requests: 3 per hour per IP address.
    PHASE 2: Prevents password reset spam and enumeration attacks.
    """
    scope = 'password_reset'
    rate = '3/hour'
    
    def get_cache_key(self, request, view):
        from api.utils import get_client_ip
        ip = get_client_ip(request)
        return f"throttle_password_reset_{ip}"


class PatientSearchThrottle(UserRateThrottle):
    """
    Rate limit patient search: 100 requests per hour per authenticated user.
    PHASE 2: Prevents enumeration attacks (guessing patient IDs).
    """
    scope = 'patient_search'
    rate = '100/hour'
    
    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return f"throttle_patient_search_{request.user.id}"


class AdminEndpointThrottle(UserRateThrottle):
    """
    Rate limit admin endpoints: 50 requests per hour per admin user.
    PHASE 2: Prevents admin action spam.
    """
    scope = 'admin_endpoint'
    rate = '50/hour'
    
    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        if request.user.role not in ('super_admin', 'hospital_admin'):
            return None
        return f"throttle_admin_{request.user.id}"


class ExportThrottle(UserRateThrottle):
    """
    Rate limit bulk export/report generation: 5 per day per user.
    PHASE 2: Prevents resource exhaustion from large exports.
    """
    scope = 'export'
    rate = '5/day'
    
    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return f"throttle_export_{request.user.id}"


class CrossFacilityAccessThrottle(UserRateThrottle):
    """
    Rate limit cross-facility/break-glass access: 10 per hour per user.
    PHASE 2: Monitors access to sensitive cross-hospital data.
    """
    scope = 'cross_facility'
    rate = '10/hour'
    
    def get_cache_key(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return None
        return f"throttle_cross_facility_{request.user.id}"


# ============================================================================
# THROTTLE CONFIGURATION REFERENCE
# ============================================================================

THROTTLE_CONFIG = {
    # Authentication endpoints
    'auth/login': 'LoginThrottle',              # 5/15min
    'auth/mfa-verify': 'MFAThrottle',           # 3/5min
    'auth/password-reset-request': 'PasswordResetThrottle',  # 3/hour
    'auth/password-reset': 'PasswordResetThrottle',
    
    # Patient search (prevents enumeration)
    'patients/search': 'PatientSearchThrottle',  # 100/hour
    'patients/': 'PatientSearchThrottle',
    
    # Admin actions
    'admin/users': 'AdminEndpointThrottle',      # 50/hour
    'admin/hospitals': 'AdminEndpointThrottle',
    'admin/audit-logs': 'AdminEndpointThrottle',
    
    # Data export
    'reports/export': 'ExportThrottle',          # 5/day
    'patients/export': 'ExportThrottle',
    
    # Cross-facility access
    'cross-facility': 'CrossFacilityAccessThrottle',  # 10/hour
    'break-glass': 'CrossFacilityAccessThrottle',
}


# ============================================================================
# UTILITY FUNCTIONS FOR MANUAL THROTTLING
# ============================================================================

def check_rate_limit(key, limit, window_seconds):
    """
    Manual rate limit check without DRF's BaseThrottle.
    
    Args:
        key: Cache key identifier (e.g., "user_123_action")
        limit: Max attempts allowed
        window_seconds: Time window in seconds
    
    Returns:
        (allowed, remaining_attempts, retry_after_seconds)
    """
    current_count = cache.get(key, 0)
    
    if current_count >= limit:
        # Calculate retry-after
        expiry = cache.ttl(key)  # Returns seconds until expiry
        retry_after = max(1, expiry) if expiry else window_seconds
        return False, 0, retry_after
    
    # Increment counter
    if current_count == 0:
        cache.set(key, 1, timeout=window_seconds)
    else:
        cache.incr(key)
    
    remaining = limit - (current_count + 1)
    return True, remaining, 0


def is_rate_limited(request, action, limit=10, window_seconds=3600):
    """
    Check if a request should be rate-limited.
    
    Args:
        request: HTTP request object
        action: Action name (e.g., 'login', 'password_reset')
        limit: Max attempts allowed (default: 10)
        window_seconds: Time window (default: 1 hour)
    
    Returns:
        bool: True if rate-limited, False if allowed
    """
    from api.utils import get_client_ip
    
    # Use IP for anonymous, user ID for authenticated
    if request.user and request.user.is_authenticated:
        key = f"throttle_{action}_{request.user.id}"
    else:
        ip = get_client_ip(request)
        key = f"throttle_{action}_{ip}"
    
    allowed, remaining, retry_after = check_rate_limit(
        key, limit, window_seconds
    )
    
    return not allowed


def get_rate_limit_headers(request, action, limit=10, window_seconds=3600):
    """
    Returns HTTP headers for rate limit info.
    
    Returns dict with:
        - X-RateLimit-Limit: max requests
        - X-RateLimit-Remaining: requests left
        - Retry-After: seconds to wait (if rate-limited)
    """
    from api.utils import get_client_ip
    
    if request.user and request.user.is_authenticated:
        key = f"throttle_{action}_{request.user.id}"
    else:
        ip = get_client_ip(request)
        key = f"throttle_{action}_{ip}"
    
    allowed, remaining, retry_after = check_rate_limit(
        key, limit, window_seconds
    )
    
    headers = {
        'X-RateLimit-Limit': str(limit),
        'X-RateLimit-Remaining': str(max(0, remaining)),
    }
    
    if not allowed:
        headers['Retry-After'] = str(retry_after)
    
    return headers
