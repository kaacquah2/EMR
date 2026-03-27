import hashlib
import json
import logging
import secrets
import pyotp
from django.conf import settings
from django.core.cache import cache
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.utils import timezone
from django.db.models import F
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from core.models import User, AuditLog, PasswordResetAudit, PasswordResetAttempt, MFASession, BackupCodeRateLimit
from api.password_policy import validate_password, check_password_reuse, record_password_history
from api.utils import sanitize_audit_resource_id, audit_log, get_client_ip
from api.rate_limiting import LoginThrottle, MFAThrottle, MFAUserThrottle, PasswordResetThrottle
from api.validators import validate_email_format
from api.audit_logging import log_authentication_event, log_mfa_event, log_rate_limit_exceeded

# Email validator for consistent validation
_email_validator = EmailValidator()
_logger = logging.getLogger(__name__)


def _mfa_dev_authenticator_emails():
    return frozenset(getattr(settings, "DEV_PERMISSION_BYPASS_EMAILS", None) or [])


def _mfa_use_authenticator_only(email: str) -> bool:
    """Dev seed accounts: fake inboxes — MFA via TOTP app only, not email OTP."""
    e = (email or "").strip().lower()
    return e in _mfa_dev_authenticator_emails()


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    from django.db import transaction
    
    email = request.data.get("email", "").strip().lower()
    password = request.data.get("password", "")
    if not email or not password:
        return Response(
            {"message": "Email and password required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # ⚠️  SECURITY: Don't reveal that email doesn't exist (prevents user enumeration)
        return Response(
            {"message": "Invalid email or password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # ==================== CRITICAL FIX #4: Use atomic transaction with row lock ====================
    with transaction.atomic():
        # Lock the row for UPDATE - other transactions must wait
        user = User.objects.select_for_update().get(id=user.id)
        
        # PHASE 1: Account Lockout Check (Task 3)
        # Check if account is locked due to too many failed login attempts
        if user.locked_until and user.locked_until > timezone.now():
            return Response(
                {"message": "Account locked. Try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        
        # ⚠️  SECURITY: Log account status for monitoring, but don't reveal to user
        if user.account_status not in ("active", "pending"):
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Login attempt for inactive account: {email}, status={user.account_status}")
            # Return generic message (same as wrong password) to prevent enumeration
            return Response(
                {"message": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        if not user.check_password(password):
            # HIGH-2 FIX: Use F() expressions for atomic increment to prevent race condition
            User.objects.filter(id=user.id).update(
                failed_login_attempts=F('failed_login_attempts') + 1
            )
            
            # Refresh user object to get updated failed_login_attempts
            user.refresh_from_db()
            
            if user.failed_login_attempts >= 5:
                # Lock account for 15 minutes after 5 failed attempts
                User.objects.filter(id=user.id).update(
                    locked_until=timezone.now() + timezone.timedelta(minutes=15)
                )
                user.refresh_from_db()
                
                # Log account lockout
                audit_log(
                    user, 'ACCOUNT_LOCKED',
                    request=request,
                    extra_data={
                        'failed_attempts': user.failed_login_attempts,
                        'locked_until': user.locked_until.isoformat(),
                    }
                )
            
            # Log failed attempt
            log_authentication_event(
                user_email=email,
                success=False,
                request=request,
                error_reason=f"Failed attempt {user.failed_login_attempts}/5"
            )
            
            return Response(
                {"message": "Invalid email or password"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # PHASE 1: Reset failed login attempts on successful authentication (Task 3)
        user.failed_login_attempts = 0
        user.locked_until = None
        user.save()
    # ==================== END CRITICAL FIX #4 ====================
    
    if not user.is_mfa_enabled or not user.totp_secret:
        return Response(
            {"message": "MFA not configured"},
            status=status.HTTP_403_FORBIDDEN,
        )
    # PHASE 1: Use database-backed MFASession instead of cache (Task 5)
    # This ensures MFA sessions persist across service restarts and cache clears
    mfa_token = secrets.token_urlsafe(48)
    expires_at = timezone.now() + timezone.timedelta(minutes=5)
    use_app = _mfa_use_authenticator_only(user.email)

    if use_app:
        MFASession.objects.create(
            user=user,
            token=mfa_token,
            expires_at=expires_at,
            ip_address=get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
            email_otp_hash=None,
        )
        return Response(
            {
                "mfa_required": True,
                "mfa_token": mfa_token,
                "mfa_channel": "authenticator",
            }
        )

    otp_plain = f"{secrets.randbelow(1_000_000):06d}"
    otp_hash = hashlib.sha256(otp_plain.encode()).hexdigest()
    MFASession.objects.create(
        user=user,
        token=mfa_token,
        expires_at=expires_at,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
        email_otp_hash=otp_hash,
    )
    subject = "Your MedSync sign-in code"
    body = (
        f"Your one-time sign-in code is: {otp_plain}\n\n"
        "It expires in 5 minutes. If you did not try to sign in, ignore this email."
    )
    try:
        send_mail(
            subject,
            body,
            getattr(settings, "DEFAULT_FROM_EMAIL", None) or "noreply@medsync.local",
            [user.email],
            fail_silently=False,
        )
    except Exception:
        _logger.exception(
            "MFA email OTP send failed (user_id=%s, email=%s); check EMAIL_* / SMTP.",
            user.id,
            user.email,
        )
        MFASession.objects.filter(token=mfa_token).delete()
        return Response(
            {
                "message": "Could not send sign-in code. Try again later or contact support.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return Response(
        {
            "mfa_required": True,
            "mfa_token": mfa_token,
            "mfa_channel": "email",
        }
    )




def _generate_backup_codes(count=8):
    codes = [secrets.token_hex(4) for _ in range(count)]
    return codes, [hashlib.sha256(c.encode()).hexdigest() for c in codes]


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MFAThrottle, MFAUserThrottle])
def mfa_verify(request):
    mfa_token = request.data.get("mfa_token")
    code = str(request.data.get("code", "")).strip()
    backup_code = request.data.get("backup_code", "").strip()
    if not mfa_token:
        return Response(
            {"message": "MFA token required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not code and not backup_code:
        return Response(
            {"message": "Enter your 6-digit code or backup code"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # PHASE 1: Use database-backed MFASession instead of cache (Task 5)
    try:
        mfa_session = MFASession.objects.get(token=mfa_token)
    except MFASession.DoesNotExist:
        return Response(
            {"message": "Session expired. Please login again."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Check if session has expired
    if mfa_session.expires_at < timezone.now():
        mfa_session.delete()
        return Response(
            {"message": "Session expired. Please login again."},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    user = mfa_session.user
    
    # ==================== CRITICAL FIX #1: User-level MFA rate limiting ====================
    # Check total failed MFA attempts in last hour across ALL sessions
    failed_mfa_count = AuditLog.objects.filter(
        user=user,
        action='MFA_FAILED',
        timestamp__gte=timezone.now() - timezone.timedelta(hours=1)
    ).count()
    
    # Hard limit: 10 failures in 1 hour locks account for 1 hour
    if failed_mfa_count >= 10:
        user.locked_until = timezone.now() + timezone.timedelta(hours=1)
        user.save()
        
        mfa_session.delete()
        
        # Log rate limit exceeded using centralized helper
        log_rate_limit_exceeded(request, 'MFA_ATTEMPTS_EXCEEDED')
        
        return Response(
            {
                "message": "Account locked due to too many failed MFA attempts. Try again after 1 hour.",
                "locked_until": user.locked_until.isoformat(),
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    
    # Per-session rate limiting (max 3 failures)
    if mfa_session.failed_attempts >= 3:
        mfa_session.delete()
        return Response(
            {"message": "Too many failed attempts. Please login again."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    # ==================== END CRITICAL FIX #1 ====================
    
    verified = False
    if backup_code:
        # MEDIUM-1 FIX: Use database-backed rate limiting instead of cache
        allowed, remaining = BackupCodeRateLimit.check_and_record(user, max_attempts=2, window_minutes=5)
        if not allowed:
            mfa_session.delete()
            log_mfa_event(user, success=False, request=request, error_reason="Backup code limit exceeded")
            return Response(
                {"message": "Too many backup code attempts. Please login again."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        # HIGH-4 FIX: Acquire row lock before backup code verification to prevent race condition
        # Prevents two requests from consuming the same backup code in parallel
        user_locked = User.objects.select_for_update().get(pk=user.id)
        
        stored = json.loads(user_locked.mfa_backup_codes or "[]")
        code_hash = hashlib.sha256(backup_code.encode()).hexdigest()
        # HIGH-1 FIX: Use constant-time comparison to prevent timing attack
        verified = any(secrets.compare_digest(code_hash, stored_hash) for stored_hash in stored)
        
        if verified:
            # Log consumption as a sensitive operation
            from api.audit_logging import log_sensitive_operation

            log_sensitive_operation(
                user=user,
                operation="BACKUP_CODE_CONSUMED",
                resource_type="MFABackupCode",
                resource_id=user.id,
                request=request,
                details={"consumed_at": timezone.now().isoformat()},
            )

            stored.remove(code_hash)
            user_locked.mfa_backup_codes = json.dumps(stored)
            user_locked.save()
            verified = True
            log_mfa_event(
                user,
                success=True,
                request=request,
                extra_data={"backup_code_used": True},
            )
        else:
            # Backup code was invalid; attempt already recorded by check_and_record()
            mfa_session.failed_attempts += 1
            mfa_session.save()
            log_mfa_event(user, success=False, request=request, error_reason="Invalid backup code")
    elif code:
        if mfa_session.email_otp_hash:
            if secrets.compare_digest(
                hashlib.sha256(code.encode()).hexdigest(),
                mfa_session.email_otp_hash,
            ):
                verified = True
                log_mfa_event(user, success=True, request=request)
            else:
                mfa_session.failed_attempts += 1
                mfa_session.save()
                log_mfa_event(
                    user,
                    success=False,
                    request=request,
                    error_reason="Invalid email OTP",
                )
        elif user.totp_secret and _mfa_use_authenticator_only(user.email):
            totp = pyotp.TOTP(user.totp_secret)
            if totp.verify(code, valid_window=2):
                verified = True
                log_mfa_event(user, success=True, request=request)
            else:
                mfa_session.failed_attempts += 1
                mfa_session.save()
                log_mfa_event(
                    user,
                    success=False,
                    request=request,
                    error_reason="Invalid TOTP code",
                )
        else:
            mfa_session.failed_attempts += 1
            mfa_session.save()
            log_mfa_event(
                user,
                success=False,
                request=request,
                error_reason="MFA session missing email OTP",
            )
    
    if not verified:
        # PHASE 1: Increment failed attempts (Task 5)
        return Response(
            {
                "message": "Invalid MFA or backup code",
                "failed_attempts": mfa_session.failed_attempts,
                "max_attempts": 3,
            },
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    mfa_session.delete()
    refresh = RefreshToken.for_user(user)
    audit_log(user, "LOGIN", request=request)
    return Response({
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "role": user.role,
        "hospital_id": str(user.hospital_id) if user.hospital_id else None,
        "user_profile": _user_to_dict(user),
    })


def _user_to_dict(user):
    return {
        "user_id": str(user.id),
        "hospital_id": str(user.hospital_id) if user.hospital_id else None,
        "email": user.email,
        "role": user.role,
        "full_name": user.full_name,
        "department": user.department or "",
        "department_id": str(user.department_link_id) if getattr(user, "department_link_id", None) else None,
        "department_name": user.department_link.name if getattr(user, "department_link", None) else None,
        "ward_id": str(user.ward_id) if user.ward_id else None,
        "lab_unit_id": str(user.lab_unit_id) if getattr(user, "lab_unit_id", None) else None,
        "lab_unit_name": user.lab_unit.name if getattr(user, "lab_unit", None) else None,
        "account_status": user.account_status,
        "hospital_name": user.hospital.name if user.hospital else None,
        "ward_name": user.ward.ward_name if user.ward else None,
        "gmdc_licence_number": getattr(user, "gmdc_licence_number", None) or None,
        "licence_verified": getattr(user, "licence_verified", False),
        # PHASE 7: 3-Tier Password Recovery
        "must_change_password_on_login": user.must_change_password_on_login,
    }


@api_view(["GET", "POST"])
@permission_classes([AllowAny])
def activate_setup(request):
    # Prefer token in body (POST) to avoid query string in logs/Referer. GET kept for backward compat.
    token = (request.data.get("token") or "").strip() if request.method == "POST" else (request.GET.get("token") or "").strip()
    if not token:
        return Response(
            {"message": "Token required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from django.utils import timezone
    try:
        user = User.objects.get(invitation_token=token)
    except User.DoesNotExist:
        return Response(
            {"message": "Invalid or expired invitation"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.invitation_expires_at and user.invitation_expires_at < timezone.now():
        return Response(
            {"message": "Invitation expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.account_status == "active":
        return Response(
            {"message": "Account already activated"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    totp = pyotp.TOTP(user.totp_secret)
    provisioning_url = totp.provisioning_uri(
        name=user.email,
        issuer_name="MedSync",
    )
    return Response({
        "totp_secret": user.totp_secret,
        "provisioning_url": provisioning_url,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def activate(request):
    token = request.data.get("token")
    password = request.data.get("password")
    totp_code = request.data.get("totp_confirmation", "")
    if not token or not password:
        return Response(
            {"message": "Token and password required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    from django.utils import timezone
    try:
        user = User.objects.get(invitation_token=token)
    except User.DoesNotExist:
        return Response(
            {"message": "Invalid or expired invitation"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.invitation_expires_at and user.invitation_expires_at < timezone.now():
        return Response(
            {"message": "Invitation expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if user.account_status == "active":
        return Response(
            {"message": "Account already activated"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not user.totp_secret:
        return Response(
            {"message": "Invalid invitation state"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    ok, msg = validate_password(password)
    if not ok:
        return Response({"message": msg}, status=status.HTTP_400_BAD_REQUEST)
    ok, msg = check_password_reuse(user, password)
    if not ok:
        return Response({"message": msg}, status=status.HTTP_400_BAD_REQUEST)
    totp = pyotp.TOTP(user.totp_secret)
    if not totp.verify(totp_code, valid_window=1):
        return Response(
            {"message": "Invalid TOTP confirmation. Please try activation again."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    raw_codes, hashed = _generate_backup_codes()
    user.mfa_backup_codes = json.dumps(hashed)
    if user.password:
        record_password_history(user, user.password)
    user.set_password(password)
    user.account_status = "active"
    user.is_mfa_enabled = True
    user.invitation_token = None
    user.invitation_expires_at = None
    user.activated_at = timezone.now()
    user.save()
    audit_log(user, "ACCOUNT_ACTIVATED", request=request)
    refresh = RefreshToken.for_user(user)
    return Response({
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "role": user.role,
        "hospital_id": str(user.hospital_id) if user.hospital_id else None,
        "user_profile": _user_to_dict(user),
        "backup_codes": raw_codes,
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    TIER 1: User self-service password reset via email.
    
    Request a password reset for the given email. Sets password_reset_token and
    password_reset_expires_at (1 hour). Email delivery is out of scope: the reset
    link (e.g. frontend URL with token query) must be sent by an external
    system or provided manually. Use POST /auth/reset-password with the token
    to set the new password.
    
    ⚠️  SECURITY: Rate limited to 10 attempts per email per 15 minutes to prevent abuse.
    """
    email = request.data.get("email", "").strip().lower()
    if not email:
        return Response(
            {"message": "Email required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # ⚠️  SECURITY: Validate email format before database query
    try:
        _email_validator(email)
    except ValidationError:
        return Response(
            {"message": "Invalid email format"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # HIGH-5 FIX: Per-email rate limiting (10 attempts per 15 minutes) using database-backed model
    allowed, remaining = PasswordResetAttempt.check_and_record(
        email=email,
        max_attempts=10,
        window_minutes=15,
        ip_address=get_client_ip(request),
    )
    
    if not allowed:
        return Response(
            {"message": "Too many reset attempts. Please try again in 15 minutes."},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )
    
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # ⚠️  SECURITY: Return same message for non-existent users (don't enumerate)
        return Response({"message": "If an account exists, a reset link was sent."})
    
    if user.account_status != "active":
        # ⚠️  SECURITY: Return same message for inactive users
        return Response({"message": "If an account exists, a reset link was sent."})
    
    from django.utils import timezone
    from datetime import timedelta
    reset_token = secrets.token_urlsafe(48)
    user.password_reset_token = reset_token
    user.password_reset_expires_at = timezone.now() + timedelta(hours=1)
    user.save()
    
    # Log to PasswordResetAudit
    ctx = {
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
    }
    PasswordResetAudit.objects.create(
        user=user,
        reset_type="self_service",
        hospital=user.hospital,
        token_expires_at=user.password_reset_expires_at,
        status="pending",
        **ctx,
    )
    
    return Response({"message": "If an account exists, a reset link was sent."})


@api_view(["POST"])
@permission_classes([AllowAny])
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
    - Invalidates all existing sessions after password reset
    
    Request body:
    {
        "email": "user@hospital.com",
        "reset_token": "...",
        "new_password": "NewPassword123!@#"
    }
    
    Response: {"message": "Password reset successful", "access_token": "...", "refresh_token": "..."}
    """
    email = request.data.get("email", "").strip().lower()
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
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # Generic message to prevent user enumeration
        return Response(
            {"message": "Invalid reset request or token expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Check if reset token exists
    if not user.password_reset_token:
        return Response(
            {"message": "Invalid reset request or token expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Check if token has expired
    if user.password_reset_expires_at and user.password_reset_expires_at < timezone.now():
        user.password_reset_token = None
        user.password_reset_expires_at = None
        user.save()
        
        # Mark audit as expired
        PasswordResetAudit.objects.filter(
            user=user,
            status="pending",
        ).update(status="expired")
        
        return Response(
            {"message": "Password reset token has expired. Please request a new one."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # CRITICAL: Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(reset_token, user.password_reset_token):
        return Response(
            {"message": "Invalid reset request or token expired"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Validate password policy
    ok, msg = validate_password(new_password)
    if not ok:
        return Response(
            {"message": msg},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Check password reuse (last 5 passwords)
    ok, msg = check_password_reuse(user, new_password)
    if not ok:
        return Response(
            {"message": msg},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Record old password history before updating
    if user.password:
        record_password_history(user, user.password)
    
    # Set new password
    user.set_password(new_password)
    # Clear reset token after successful use
    user.password_reset_token = None
    user.password_reset_expires_at = None
    user.failed_password_reset_attempts = 0
    user.account_status = "active"
    user.save()
    
    # Mark audit record as completed
    ctx = {
        "ip_address": get_client_ip(request),
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:500],
    }
    PasswordResetAudit.objects.filter(
        user=user,
        status="pending",
    ).update(
        status="completed",
        token_used_at=timezone.now(),
        **ctx,
    )
    
    # Log to general audit log
    audit_log(user, "UPDATE", resource_type="PASSWORD_RESET", request=request)
    
    # Generate new tokens (invalidates old ones automatically via JWT expiry)
    refresh = RefreshToken.for_user(user)
    
    return Response({
        "message": "Password reset successful. You can now log in with your new password.",
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "role": user.role,
        "hospital_id": str(user.hospital_id) if user.hospital_id else None,
        "user_profile": _user_to_dict(user),
    })


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login_with_temp_password(request):
    """
    TIER 2: Login with temporary password generated by admin.
    
    Used when admin provides temp password. After successful login:
    1. Returns access token with must_change_password_on_login=True
    2. Frontend must show password change modal before allowing other actions
    3. User calls POST /auth/change-password-on-login to complete login process
    
    ⚠️  SECURITY: Temp password is valid only 1 hour from generation.
    """
    from django.utils import timezone
    
    email = request.data.get("email", "").strip().lower()
    temp_password = request.data.get("temp_password", "").strip()
    
    if not email or not temp_password:
        return Response(
            {"message": "Email and temp password required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        return Response(
            {"message": "Invalid email or temp password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Verify temp password is valid (use constant-time comparison to prevent timing attack)
    import secrets
    if not user.temp_password or not secrets.compare_digest(str(temp_password), str(user.temp_password)):
        return Response(
            {"message": "Invalid email or temp password"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Verify temp password hasn't expired
    if user.temp_password_expires_at and user.temp_password_expires_at < timezone.now():
        user.temp_password = None
        user.temp_password_expires_at = None
        user.save()
        return Response(
            {"message": "Temp password has expired"},
            status=status.HTTP_401_UNAUTHORIZED,
        )
    
    # Clear temp password (one-time use)
    user.temp_password = None
    user.temp_password_expires_at = None
    user.save()
    
    # Return access token - frontend will enforce password change
    refresh = RefreshToken.for_user(user)
    audit_log(user, "LOGIN", request=request)
    
    return Response({
        "access_token": str(refresh.access_token),
        "refresh_token": str(refresh),
        "role": user.role,
        "hospital_id": str(user.hospital_id) if user.hospital_id else None,
        "user_profile": _user_to_dict(user),
        "must_change_password_on_login": True,  # Force frontend to show modal
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_on_login(request):
    """
    TIER 2: User changes password after admin-generated temp password login.
    
    Used after user logs in with temp password. Validates new password
    and clears must_change_password_on_login flag.
    
    Request: {"password": "new_password"}
    Response: {"message": "Password changed successfully"}
    """
    from django.utils import timezone
    
    user = request.user
    password = request.data.get("password")
    
    if not password:
        return Response(
            {"message": "New password required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Validate new password
    ok, msg = validate_password(password)
    if not ok:
        return Response({"message": msg}, status=status.HTTP_400_BAD_REQUEST)
    
    ok, msg = check_password_reuse(user, password)
    if not ok:
        return Response({"message": msg}, status=status.HTTP_400_BAD_REQUEST)
    
    # Record old password history
    if user.password:
        record_password_history(user, user.password)
    
    # Update password and clear forced change flag
    user.set_password(password)
    user.must_change_password_on_login = False
    user.save()
    
    audit_log(user, "UPDATE", resource_type="PASSWORD_CHANGE_ON_LOGIN", request=request)
    
    return Response({
        "message": "Password changed successfully",
        "user_profile": _user_to_dict(user),
    })


@api_view(["POST"])
@permission_classes([AllowAny])
def refresh(request):
    refresh_token = request.data.get("refresh_token")
    if not refresh_token:
        return Response(
            {"message": "refresh_token required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        serializer = TokenRefreshSerializer(data={"refresh": refresh_token})
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        return Response({
            "access_token": str(data["access"]),
            "refresh_token": str(data.get("refresh", refresh_token)),
        })
    except InvalidToken:
        return Response(
            {"message": "Invalid or expired refresh token"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout(request):
    user = request.user
    audit_log(user, "LOGOUT", request=request)
    refresh_raw = request.data.get("refresh_token") or request.data.get("refresh")
    if refresh_raw:
        try:
            token = RefreshToken(refresh_raw)
            token.blacklist()
        except (InvalidToken, Exception):
            pass
    return Response({"message": "Logged out"})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(_user_to_dict(request.user))
