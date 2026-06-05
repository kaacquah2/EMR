"""
PHASE 2: Adaptive Authentication Utils

Implements NIST 800-63 Authenticator Assurance Level (AAL) scoring for login risk context.

AAL1 (no MFA): Trusted device, known IP, business hours
AAL2 (email OTP): New device, unknown IP, or after-hours
AAL3 (step-up): High-risk actions requiring explicit re-verification

Device fingerprint = SHA256(user_agent + screen_resolution + timezone)
"""

import hashlib
import ipaddress
import logging
from datetime import datetime
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


def compute_device_fingerprint(request) -> str:
    """
    Compute device fingerprint from request context.
    
    Fingerprint = SHA256(user_agent + screen_resolution + timezone)
    
    Args:
        request: Django request object
        
    Returns:
        str: SHA256 hex digest (64 chars)
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    # Frontend passes screen resolution and timezone in request body or headers
    # For initial login: check body; for subsequent requests: check headers
    screen_resolution = ''
    timezone_str = ''
    
    if hasattr(request, 'data') and isinstance(request.data, dict):
        screen_resolution = request.data.get('screen_resolution', '')
        timezone_str = request.data.get('timezone', '')
    
    # Fallback to headers if not in body
    if not screen_resolution:
        screen_resolution = request.META.get('HTTP_X_SCREEN_RESOLUTION', '')
    if not timezone_str:
        timezone_str = request.META.get('HTTP_X_TIMEZONE', '')
    
    # Build fingerprint from components
    raw = f"{user_agent}|{screen_resolution}|{timezone_str}"
    fingerprint = hashlib.sha256(raw.encode()).hexdigest()
    
    return fingerprint


def is_ip_in_hospital_subnet(ip_str: str, hospital) -> bool:
    """
    Check if an IP address falls within hospital's registered subnets.
    
    Args:
        ip_str (str): IP address (e.g., "192.168.1.100")
        hospital: Hospital model instance with ip_subnets JSONField
        
    Returns:
        bool: True if IP is in any registered subnet, False otherwise
    """
    if not hospital or not hospital.ip_subnets:
        # No subnets configured for hospital → IP is unknown
        return False
    
    try:
        ip = ipaddress.ip_address(ip_str)
        
        for subnet_str in hospital.ip_subnets:
            try:
                subnet = ipaddress.ip_network(subnet_str, strict=False)
                if ip in subnet:
                    return True
            except ValueError as e:
                logger.warning(f"Invalid CIDR in hospital {hospital.id} ip_subnets: {subnet_str} — {e}")
                continue
        
        return False
    except ValueError as e:
        logger.warning(f"Invalid IP address: {ip_str} — {e}")
        return False


def is_within_business_hours(user_timezone: str = None) -> bool:
    """
    Check if current time is within business hours (06:00–22:00).
    
    Args:
        user_timezone (str): User's timezone string (e.g., "Africa/Accra")
        
    Returns:
        bool: True if current time is 06:00–22:00 in user's timezone
    """
    try:
        from zoneinfo import ZoneInfo
        
        if not user_timezone:
            # No timezone provided → assume not during business hours (err on side of caution)
            return False
        
        tz = ZoneInfo(user_timezone)
        now = datetime.now(tz)
        hour = now.hour
        
        # Business hours: 06:00 to 22:00 (inclusive)
        return 6 <= hour < 22
    except Exception as e:
        logger.warning(f"Error checking business hours for timezone {user_timezone}: {e}")
        # On error, assume not during business hours (safer)
        return False


def compute_login_risk_tier(user, request) -> dict:
    """
    Compute authentication assurance level for a login attempt.
    
    Evaluates:
    1. Known device (matching fingerprint, not expired)
    2. Known IP (within hospital subnets)
    3. Business hours (06:00–22:00 in user's timezone)
    4. Role (super_admin/hospital_admin always get risk_tier=2)
    
    Risk Tier Matrix:
    - risk_tier = 1 (AAL1, no MFA):
      known_device AND known_ip AND in_hours AND NOT (super_admin OR hospital_admin)
    
    - risk_tier = 2 (AAL2, email OTP required):
      new_device OR unknown_ip OR after_hours OR super_admin OR hospital_admin
    
    Args:
        user: User model instance
        request: Django request object (for IP, user_agent, etc.)
        
    Returns:
        dict: {
            'risk_tier': 1 or 2,
            'device_fingerprint': str,
            'factors': [list of matched factors],
            'reason': str (human-readable explanation)
        }
    """
    from api.utils import get_client_ip
    from core.models import TrustedDevice
    
    ip_address = get_client_ip(request)
    device_fingerprint = compute_device_fingerprint(request)
    timezone_str = request.data.get('timezone', '') if hasattr(request, 'data') else ''
    
    matched_factors = []
    
    # Check 1: Known device
    known_device = False
    try:
        trusted_device = TrustedDevice.objects.filter(
            user=user,
            device_fingerprint=device_fingerprint,
            is_active=True,
        ).first()
        
        if trusted_device and not trusted_device.is_expired():
            known_device = True
            matched_factors.append('device')
            # Refresh expiry (sliding 30-day window)
            trusted_device.refresh_expiry(days=30)
    except Exception as e:
        logger.warning(f"Error checking trusted device for user {user.id}: {e}")
    
    # Check 2: Known IP (within hospital subnet)
    known_ip = False
    if user.hospital:
        known_ip = is_ip_in_hospital_subnet(ip_address, user.hospital)
        if known_ip:
            matched_factors.append('ip')
    
    # Check 3: Business hours
    in_hours = is_within_business_hours(timezone_str)
    if in_hours:
        matched_factors.append('hours')
    
    # Check 4: Role-based enforcement
    is_admin = user.role in ('super_admin', 'hospital_admin')
    
    # Compute risk tier
    if known_device and known_ip and in_hours and not is_admin:
        risk_tier = 1
        reason = "Trusted device, known IP, business hours → no MFA"
    else:
        risk_tier = 2
        reason_parts = []
        if not known_device:
            reason_parts.append("new device")
        if not known_ip and user.hospital:
            reason_parts.append("unknown IP")
        if not in_hours and timezone_str:
            reason_parts.append("after-hours")
        if is_admin:
            reason_parts.append("admin role")
        reason = f"MFA required: {', '.join(reason_parts)}"
    
    return {
        'risk_tier': risk_tier,
        'device_fingerprint': device_fingerprint,
        'factors': matched_factors,
        'reason': reason,
    }
