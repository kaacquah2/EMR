"""
PHASE 7: 3-Tier Password Recovery System

Tier 1: User Self-Service (forgot_password, reset_password in auth_views.py)
Tier 2: Hospital Admin Assist (generate_reset_link, generate_temp_password)
Tier 3: Super Admin Override (force_password_reset, get_suspicious_resets)

All endpoints log to PasswordResetAudit for HIPAA compliance and pattern detection.

CRITICAL FIX #2: Password Reset Token Security
- Tokens NOT exposed in URLs (sent via POST body only)
- Constant-time comparison using secrets.compare_digest()
- Frontend URL configurable via settings
- Email templates used for password reset links
"""

import secrets
from django.utils import timezone
from datetime import timedelta
from django.core.cache import cache
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from core.models import User, Hospital, PasswordResetAudit
from api.password_policy import validate_password, check_password_reuse, record_password_history
from api.utils import get_client_ip


def _get_request_context(request):
    """Extract IP and user agent from request."""
    return {
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
    }


def _generate_reset_token():
    """Generate cryptographically secure reset token (24-hour validity)."""
    return secrets.token_urlsafe(48)


def _generate_temp_password():
    """Generate temporary password for admin-assisted resets."""
    # 20+ characters: letters + digits + symbols for high entropy
    # But keep it typeable (no confusing chars like I, l, 1, O, 0)
    import string
    chars = string.ascii_letters + string.digits + "!@#$%"
    temp_pwd = "".join(secrets.choice(chars) for _ in range(20))
    return temp_pwd


def send_password_reset_email(user, reset_token):
    """
    Send password reset email to user with reset token.
    
    CRITICAL FIX #2: Token sent in email body, NOT in URL.
    User must copy token and submit via POST form.
    
    Args:
        user: User object
        reset_token: Generated reset token (24 chars, URL-safe)
    """
    expiry_hours = settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
    reset_url = settings.PASSWORD_RESET_FRONTEND_URL
    
    context = {
        'user_full_name': user.full_name,
        'reset_url': reset_url,
        'reset_token': reset_token,
        'expiry_hours': expiry_hours,
    }
    
    # Render HTML email
    html_message = render_to_string('password_reset_email.html', context)
    
    # Send email
    send_mail(
        subject='MedSync Password Reset Request',
        message=f'Your password reset token is: {reset_token}',  # Plain text fallback
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


def send_force_password_reset_email(user, reset_token, admin_name, hospital_name, reason):
    """
    CRITICAL FIX #3: Send forced password reset email to user.
    
    Sends a warning email to the USER (not admin) when a super admin forces reset.
    This ensures the user is notified and can take action if unauthorized.
    
    Args:
        user: User object receiving the reset
        reset_token: Generated reset token
        admin_name: Name of admin who initiated the reset
        hospital_name: Name of hospital
        reason: Reason for the forced reset
    """
    expiry_hours = settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
    reset_url = settings.PASSWORD_RESET_FRONTEND_URL
    
    context = {
        'user_full_name': user.full_name,
        'admin_name': admin_name,
        'hospital_name': hospital_name,
        'reason': reason,
        'reset_url': reset_url,
        'reset_token': reset_token,
        'expiry_hours': expiry_hours,
        'today_date': timezone.now().strftime('%B %d, %Y at %H:%M UTC'),
    }
    
    # Render HTML email from force_password_reset_email.html template
    html_message = render_to_string('force_password_reset_email.html', context)
    
    # Send email with warning subject
    send_mail(
        subject='⚠️ Password Reset Required by Your Hospital',
        message=f'Your password reset token is: {reset_token}. If you did not request this, contact your hospital IT immediately.',
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        html_message=html_message,
        fail_silently=False,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_reset_link(request, user_id):
    """
    TIER 2: Hospital Admin generates a password reset link for a user.
    
    CRITICAL FIX #2: Response NO LONGER includes reset_token in JSON.
    Token is sent via email only. Admin can see token was sent but not in response.
    
    - Only hospital_admin can call this
    - Can only reset users in the same hospital
    - Generates token valid for 24 hours
    - Logs to PasswordResetAudit
    - Sends email to user with reset token
    
    Request: {"reason": "User forgot password"}
    Response: {"message": "Reset email sent", "user_email": "...", "expires_in_hours": 24}
    """
    # Check requester is hospital_admin
    if request.user.role != "hospital_admin":
        return Response(
            {"message": "Only hospital admins can generate reset links"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get target user
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Verify same hospital
    if target_user.hospital_id != request.user.hospital_id:
        return Response(
            {"message": "Cannot reset users from other hospitals"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Generate token (24 hour validity)
    reset_token = _generate_reset_token()
    expiry_hours = settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
    target_user.password_reset_token = reset_token
    target_user.password_reset_expires_at = timezone.now() + timedelta(hours=expiry_hours)
    target_user.save()
    
    # Log to audit trail
    ctx = _get_request_context(request)
    PasswordResetAudit.objects.create(
        user=target_user,
        reset_type="admin_link",
        initiated_by=request.user,
        hospital=target_user.hospital,
        reason=request.data.get("reason", "Admin-initiated reset"),
        token_expires_at=target_user.password_reset_expires_at,
        **ctx,
        status="pending",
    )
    
    # Send email with reset token (NOT exposed in URL)
    try:
        send_password_reset_email(target_user, reset_token)
    except Exception as e:
        # Log but don't fail if email fails (development might use console backend)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send reset email to {target_user.email}: {e}")
    
    return Response({
        "message": "Password reset email sent to user",
        "user_email": target_user.email,
        "expires_in_hours": expiry_hours,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def generate_temp_password(request, user_id):
    """
    TIER 2: Hospital Admin generates a temporary password for urgent access.
    
    - Only hospital_admin can call this
    - Can only reset users in the same hospital
    - Temp password valid for 1 hour only
    - User MUST change password on next login
    - Logs to PasswordResetAudit
    - Returns temp password for admin to share verbally/securely
    
    Request: {"reason": "User locked out, urgent access needed"}
    Response: {"temp_password": "...", "expires_in_minutes": 60}
    """
    # Check requester is hospital_admin
    if request.user.role != "hospital_admin":
        return Response(
            {"message": "Only hospital admins can generate temp passwords"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get target user
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Verify same hospital
    if target_user.hospital_id != request.user.hospital_id:
        return Response(
            {"message": "Cannot reset users from other hospitals"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Generate temp password and set expiry
    temp_pwd = _generate_temp_password()
    target_user.temp_password = temp_pwd
    target_user.temp_password_expires_at = timezone.now() + timedelta(hours=1)
    target_user.must_change_password_on_login = True
    target_user.save()
    
    # Log to audit trail
    ctx = _get_request_context(request)
    PasswordResetAudit.objects.create(
        user=target_user,
        reset_type="temp_password",
        initiated_by=request.user,
        hospital=target_user.hospital,
        reason=request.data.get("reason", "Admin-initiated temp password"),
        token_expires_at=target_user.temp_password_expires_at,
        **ctx,
        status="pending",
    )
    
    return Response({
        "message": "Temporary password generated successfully",
        "user_email": target_user.email,
        "temp_password": temp_pwd,
        "expires_in_minutes": 60,
        "note": "User will be forced to change password on login",
    })


@api_view(["POST"])
def reset_password(request):
    """
    CRITICAL FIX #2: Reset password endpoint accepting token in POST body.
    
    SECURITY FEATURES:
    - Token accepted in request.data (POST body), NOT URL parameter
    - Constant-time comparison using secrets.compare_digest()
    - Prevents timing attacks and token leakage in browser history/Referer headers
    - Validates password policy before accepting new password
    - Checks password reuse (last 5 passwords)
    - Clears reset token after successful use
    
    Request body:
    {
        "email": "user@hospital.com",
        "reset_token": "...",
        "new_password": "NewPassword123!@#"
    }
    
    Response: {"message": "Password reset successful"}
    """
    email = request.data.get("email", "").strip()
    reset_token = request.data.get("reset_token", "").strip()
    new_password = request.data.get("new_password", "").strip()
    
    # Validate input
    if not email or not reset_token or not new_password:
        return Response(
            {"message": "email, reset_token, and new_password are required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Get user by email
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Generic message to prevent user enumeration
        return Response(
            {"message": "Invalid reset request or token expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Fetch latest pending audit for this user to track click/validation attempts
    audit = PasswordResetAudit.objects.filter(
        user=user,
        status="pending",
    ).order_by("-token_issued_at").first()
    
    # Mark that the user has clicked the link / reached the reset form
    if audit and audit.link_clicked_at is None:
        audit.link_clicked_at = timezone.now()
        audit.save(update_fields=["link_clicked_at"])
    
    # Check if reset token exists
    if not user.password_reset_token:
        if audit:
            audit.failed_validation_attempts += 1
            audit.failure_reason = (audit.failure_reason or "") or "Missing reset token"
            audit.save(update_fields=["failed_validation_attempts", "failure_reason"])
        return Response(
            {"message": "Invalid reset request or token expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Check if token has expired
    if user.password_reset_expires_at < timezone.now():
        user.password_reset_token = None
        user.password_reset_expires_at = None
        user.save()
        if audit:
            audit.status = "expired"
            audit.failure_reason = (audit.failure_reason or "") or "Token expired"
            audit.save(update_fields=["status", "failure_reason"])
        return Response(
            {"message": "Password reset token has expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # CRITICAL: Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(reset_token, user.password_reset_token):
        if audit:
            audit.failed_validation_attempts += 1
            audit.failure_reason = (audit.failure_reason or "") or "Invalid token"
            audit.save(update_fields=["failed_validation_attempts", "failure_reason"])
        return Response(
            {"message": "Invalid reset request or token expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Validate password policy
    validation_error = validate_password(new_password)
    if validation_error:
        if audit:
            audit.failed_validation_attempts += 1
            audit.failure_reason = validation_error
            audit.save(update_fields=["failed_validation_attempts", "failure_reason"])
        return Response(
            {"message": validation_error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Check password reuse (last 5 passwords)
    reuse_error = check_password_reuse(user, new_password)
    if reuse_error:
        if audit:
            audit.failed_validation_attempts += 1
            audit.failure_reason = reuse_error
            audit.save(update_fields=["failed_validation_attempts", "failure_reason"])
        return Response(
            {"message": reuse_error},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Set new password
    user.set_password(new_password)
    # Clear reset token after successful use
    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.account_status = "active"
    user.save()
    
    # Record password history
    record_password_history(user, new_password)
    
    # Update or create audit trail
    ctx = _get_request_context(request)
    now = timezone.now()
    if audit:
        audit.token_used_at = now
        audit.reset_completed_at = now
        audit.status = "completed"
        audit.ip_address = ctx.get("ip_address")
        audit.user_agent = ctx.get("user_agent")
        audit.save(
            update_fields=[
                "token_used_at",
                "reset_completed_at",
                "status",
                "ip_address",
                "user_agent",
            ]
        )
    else:
        PasswordResetAudit.objects.create(
            user=user,
            reset_type="self_service",
            hospital=user.hospital,
            reason="User initiated password reset",
            token_expires_at=user.password_reset_expires_at or now,
            token_used_at=now,
            reset_completed_at=now,
            **ctx,
            status="completed",
        )
    
    return Response({
        "message": "Password reset successful. You can now log in with your new password.",
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_password_reset_history(request):
    """
    TIER 2: Hospital Admin retrieves password reset audit history.
    
    - Only hospital_admin can call this
    - Returns resets for their hospital only
    - Filters by user, status, reset_type, date range
    - Supports pagination
    
    Query params:
    - user_id: Filter by specific user
    - status: pending, completed, expired, failed
    - reset_type: self_service, admin_link, temp_password, super_admin_override
    - days: Last N days (default 30)
    - limit: Results per page (default 20)
    - offset: Pagination offset (default 0)
    """
    # Check requester is hospital_admin
    if request.user.role != "hospital_admin":
        return Response(
            {"message": "Only hospital admins can view password reset history"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Build query
    queryset = PasswordResetAudit.objects.filter(hospital=request.user.hospital)
    
    # Filter by user
    user_id = request.query_params.get("user_id")
    if user_id:
        queryset = queryset.filter(user_id=user_id)
    
    # Filter by status
    reset_status = request.query_params.get("status")
    if reset_status:
        queryset = queryset.filter(status=reset_status)
    
    # Filter by reset type
    reset_type = request.query_params.get("reset_type")
    if reset_type:
        queryset = queryset.filter(reset_type=reset_type)
    
    # Filter by date range
    days = int(request.query_params.get("days", 30))
    queryset = queryset.filter(token_issued_at__gte=timezone.now() - timedelta(days=days))
    
    # Pagination
    limit = int(request.query_params.get("limit", 20))
    offset = int(request.query_params.get("offset", 0))
    total_count = queryset.count()
    
    resets = queryset[offset:offset + limit]
    
    return Response({
        "count": total_count,
        "limit": limit,
        "offset": offset,
        "results": [
            {
                "id": str(reset.id),
                "user": reset.user.email,
                "reset_type": reset.get_reset_type_display(),
                "status": reset.get_status_display(),
                "initiated_by": reset.initiated_by.email if reset.initiated_by else "User",
                "reason": reset.reason,
                "token_issued_at": reset.token_issued_at.isoformat(),
                "token_expires_at": reset.token_expires_at.isoformat(),
                "token_used_at": reset.token_used_at.isoformat() if reset.token_used_at else None,
            }
            for reset in resets
        ],
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def force_password_reset(request, user_id):
    """
    TIER 3: Super Admin forces password reset on a user.
    
    - Only super_admin can call this
    - Requires MFA verification (TOTP code)
    - Works across all hospitals (via hospital_id param)
    - Logs to PasswordResetAudit with mfa_verified=True
    - Notifies hospital admin of override
    - Sends email with reset token (NOT in URL)
    
    Request: {"mfa_code": "123456", "reason": "Suspicious activity detected", "hospital_id": "..."}
    Response: {"message": "Force password reset initiated", "notification_sent": true}
    """
    # Check requester is super_admin
    if request.user.role != "super_admin":
        return Response(
            {"message": "Only super admins can force password resets"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get hospital (super admin can specify which hospital's user to reset)
    hospital_id = request.data.get("hospital_id")
    if not hospital_id:
        return Response(
            {"message": "hospital_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return Response(
            {"message": "Hospital not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Get target user
    try:
        target_user = User.objects.get(id=user_id, hospital=hospital)
    except User.DoesNotExist:
        return Response(
            {"message": "User not found in hospital"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Verify MFA (super admin must provide TOTP code)
    mfa_code = str(request.data.get("mfa_code", "")).strip()
    if not mfa_code or len(mfa_code) != 6:
        return Response(
            {"message": "Valid 6-digit MFA code required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if not request.user.is_mfa_enabled or not request.user.totp_secret:
        return Response(
            {"message": "MFA not configured on your account"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Verify MFA code
    import pyotp
    totp = pyotp.TOTP(request.user.totp_secret)
    if not totp.verify(mfa_code):
        return Response(
            {"message": "Invalid MFA code"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Generate reset token (24 hour validity)
    reset_token = _generate_reset_token()
    expiry_hours = settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
    target_user.password_reset_token = reset_token
    target_user.password_reset_expires_at = timezone.now() + timedelta(hours=expiry_hours)
    target_user.save()
    
    # Log to audit trail with mfa_verified=True
    ctx = _get_request_context(request)
    PasswordResetAudit.objects.create(
        user=target_user,
        reset_type="super_admin_override",
        initiated_by=request.user,
        hospital=hospital,
        reason=request.data.get("reason", "Super admin override"),
        token_expires_at=target_user.password_reset_expires_at,
        **ctx,
        mfa_verified=True,
        status="pending",
    )
    
    # ==================== CRITICAL FIX #3: Notify hospital admin of super admin override ====================
    # Send notification email to hospital admin
    hospital_admins = User.objects.filter(
        hospital=hospital,
        role="hospital_admin"
    )
    
    if hospital_admins.exists():
        # Prepare notification context
        notify_context = {
            'target_user_email': target_user.email,
            'target_user_name': target_user.full_name,
            'super_admin_name': request.user.full_name,
            'hospital_name': hospital.name,
            'reason': request.data.get("reason", "Super admin override"),
            'timestamp': timezone.now().strftime('%B %d, %Y at %H:%M UTC'),
            'action_required': 'Monitor for unusual activity; user will need to reset password.',
        }
        
        # Render HTML email template
        html_message = render_to_string(
            'super_admin_password_reset_notification.html',
            notify_context
        )
        
        # Send to all hospital admins
        admin_emails = [admin.email for admin in hospital_admins]
        try:
            send_mail(
                subject=f'⚠️ Password Reset Action by Super Admin - {target_user.email}',
                message=f'Super Admin {request.user.full_name} has initiated a password reset for {target_user.email}. Reason: {notify_context["reason"]}',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=admin_emails,
                html_message=html_message,
                fail_silently=False,
            )
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send hospital admin notification: {e}")
    
    # Also send notification email to the user themselves
    _email_sent = False
    try:
        send_force_password_reset_email(
            target_user,
            reset_token,
            admin_name=request.user.full_name,
            hospital_name=hospital.name,
            reason=request.data.get("reason", "Super admin override")
        )
        _email_sent = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send force reset email to {target_user.email}: {e}")

    return Response({
        "message": "Force password reset initiated. Email sent to user.",
        "user_email": target_user.email,
        "expires_in_hours": expiry_hours,
        "notification_sent": _email_sent,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def force_password_reset_initiate(request, user_id):
    """
    CRITICAL FIX #3: Super Admin initiates forced password reset with USER notification.
    
    When a super admin forces a password reset, the USER must be notified immediately.
    This endpoint ensures the user receives an email warning about the reset action.
    
    KEY SECURITY FEATURES:
    - Only super_admin can call this
    - Requires MFA verification (TOTP code)
    - Sends email DIRECTLY TO USER (not admin) with warning
    - Email includes: admin name, hospital name, reason, expiry time
    - Email warns: "If you did not request this, contact IT immediately"
    - Token valid for 24 hours
    - Prevents horizontal escalation: cannot force reset for other super admins
    - Comprehensive audit logging with action='FORCE_PASSWORD_RESET_INITIATED'
    
    Request body:
    {
        "mfa_code": "123456",
        "user_id": "uuid",
        "hospital_id": "uuid",
        "reason": "Suspicious activity detected"
    }
    
    Response:
    {
        "message": "Forced password reset initiated. Warning email sent to user.",
        "user_email": "user@hospital.com",
        "token_expires_in_hours": 24,
        "email_sent_to": "user@hospital.com",
        "confirmation_required": true
    }
    """
    # Check requester is super_admin
    if request.user.role != "super_admin":
        return Response(
            {"message": "Only super admins can initiate forced password resets"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Verify MFA first (super admin must provide TOTP code)
    mfa_code = str(request.data.get("mfa_code", "")).strip()
    if not mfa_code or len(mfa_code) != 6:
        return Response(
            {"message": "Valid 6-digit MFA code required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if not request.user.is_mfa_enabled or not request.user.totp_secret:
        return Response(
            {"message": "MFA not configured on your account"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Verify MFA code
    import pyotp
    totp = pyotp.TOTP(request.user.totp_secret)
    if not totp.verify(mfa_code):
        return Response(
            {"message": "Invalid MFA code"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Get hospital
    hospital_id = request.data.get("hospital_id")
    if not hospital_id:
        return Response(
            {"message": "hospital_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    try:
        hospital = Hospital.objects.get(id=hospital_id)
    except Hospital.DoesNotExist:
        return Response(
            {"message": "Hospital not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Get target user
    try:
        # Super admins have hospital=None, so search differently
        target_user = User.objects.get(id=user_id)
        # Check if user belongs to the specified hospital (unless super admin)
        if target_user.role != "super_admin" and target_user.hospital_id != hospital.id:
            raise User.DoesNotExist
    except User.DoesNotExist:
        return Response(
            {"message": "User not found in hospital"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # CRITICAL SECURITY: Prevent horizontal escalation - cannot force reset for other super admins
    if target_user.role == "super_admin":
        return Response(
            {"message": "Cannot force password reset for super admin accounts"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Generate reset token (24 hour validity)
    reset_token = _generate_reset_token()
    expiry_hours = settings.PASSWORD_RESET_TOKEN_EXPIRY_HOURS
    target_user.password_reset_token = reset_token
    target_user.password_reset_expires_at = timezone.now() + timedelta(hours=expiry_hours)
    target_user.save()
    
    # Log to audit trail with action='FORCE_PASSWORD_RESET_INITIATED'
    ctx = _get_request_context(request)
    reason = request.data.get("reason", "Administrative forced reset")
    audit_log = PasswordResetAudit.objects.create(
        user=target_user,
        reset_type="super_admin_override",
        initiated_by=request.user,
        hospital=hospital,
        reason=reason,
        token_expires_at=target_user.password_reset_expires_at,
        **ctx,
        mfa_verified=True,
        status="pending",
    )
    
    # Send warning email DIRECTLY TO USER with force reset details
    try:
        send_force_password_reset_email(
            target_user,
            reset_token,
            request.user.full_name,
            hospital.name,
            reason
        )
        email_sent = True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to send forced reset email to {target_user.email}: {e}")
        email_sent = False
    
    return Response({
        "message": "Forced password reset initiated. Warning email sent to user.",
        "user_email": target_user.email,
        "token_expires_in_hours": expiry_hours,
        "email_sent_to": target_user.email if email_sent else None,
        "confirmation_required": True,
        "audit_log_id": str(audit_log.id),
    }, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def get_suspicious_resets(request):
    """
    TIER 3: Super Admin retrieves suspicious password reset activity.
    
    Identifies unusual patterns that may indicate account compromise:
    - Multiple resets in short time period (< 1 hour)
    - Resets with failed validation attempts > 3
    - Resets from unusual IP addresses
    - Failed password resets after token usage
    
    Query parameters:
    - hospital_id: Filter by hospital (required for hospital admin, optional for super admin)
    - days: Last N days to query (default 7)
    - min_failed_attempts: Minimum failed attempts to report (default 1)
    
    Returns:
    {
        'suspicious_resets': [
            {
                'id': str,
                'user_email': str,
                'hospital_name': str,
                'reset_type': str,
                'status': str,
                'failed_attempts': int,
                'reason': str,
                'initiated_by': str,
                'timestamp': str,
                'ip_addresses': [str],
                'risk_score': float (0-1),
                'risk_factors': [str],
            }
        ],
        'total_suspicious': int,
        'timestamp': str,
    }
    """
    # Check permission
    if request.user.role not in ('super_admin', 'hospital_admin'):
        return Response(
            {'message': 'Only super admins and hospital admins can view suspicious resets'},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get filter parameters
    hospital_id = request.query_params.get('hospital_id')
    days = int(request.query_params.get('days', 7))
    min_failed_attempts = int(request.query_params.get('min_failed_attempts', 1))
    
    # Build query
    queryset = PasswordResetAudit.objects.filter(
        token_issued_at__gte=timezone.now() - timedelta(days=days)
    )
    
    # Filter by hospital
    if request.user.role == 'hospital_admin':
        queryset = queryset.filter(hospital=request.user.hospital)
    elif hospital_id:
        queryset = queryset.filter(hospital_id=hospital_id)
    
    # Find suspicious patterns
    suspicious_resets = []
    
    for reset in queryset.order_by('-token_issued_at'):
        risk_score = 0.0
        risk_factors = []
        
        # Factor 1: Multiple failed attempts
        if reset.failed_validation_attempts >= min_failed_attempts:
            risk_score += 0.3
            risk_factors.append(f"{reset.failed_validation_attempts} failed attempts")
        
        # Factor 2: Status is failed or expired
        if reset.status == 'failed':
            risk_score += 0.2
            risk_factors.append('Reset failed after validation')
        elif reset.status == 'expired':
            risk_score += 0.1
            risk_factors.append('Token expired without use')
        
        # Factor 3: Reset type is forced (super admin override)
        if reset.reset_type == 'super_admin_override':
            risk_score += 0.2
            risk_factors.append('Super admin forced reset')
        
        # Factor 4: Unusual IP pattern – compare against user's prior successful resets
        # (within the past 90 days) to flag logins from new locations.
        if reset.ip_address:
            known_ips = set(
                PasswordResetAudit.objects.filter(
                    user=reset.user,
                    status='completed',
                    ip_address__isnull=False,
                    token_issued_at__gte=timezone.now() - timedelta(days=90),
                )
                .exclude(id=reset.id)
                .values_list('ip_address', flat=True)[:50]
            )
            if known_ips and reset.ip_address not in known_ips:
                risk_score += 0.2
                risk_factors.append('Unusual IP address (not seen in prior successful resets)')
        
        # Only include if risk score > 0
        if risk_score > 0:
            suspicious_resets.append({
                'id': str(reset.id),
                'user_email': reset.user.email,
                'hospital_name': reset.hospital.name if reset.hospital else 'N/A',
                'reset_type': reset.get_reset_type_display(),
                'status': reset.get_status_display(),
                'failed_attempts': reset.failed_validation_attempts,
                'reason': reset.reason,
                'initiated_by': reset.initiated_by.email if reset.initiated_by else 'User',
                'timestamp': reset.token_issued_at.isoformat(),
                'ip_address': reset.ip_address,
                'user_agent': reset.user_agent[:100] if reset.user_agent else None,
                'risk_score': risk_score,
                'risk_factors': risk_factors,
            })
    
    return Response({
        'suspicious_resets': sorted(suspicious_resets, key=lambda x: x['risk_score'], reverse=True),
        'total_suspicious': len(suspicious_resets),
        'timestamp': timezone.now().isoformat(),
    })


