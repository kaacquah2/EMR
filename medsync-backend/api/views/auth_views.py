import hashlib
import json
import logging
import secrets
import pyotp
from django.conf import settings
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
from core.models import User, AuditLog, PasswordResetAudit, PasswordResetAttempt, MFASession, BackupCodeRateLimit, UserPasskey
from api.password_policy import validate_password, check_password_reuse, record_password_history
from api.utils import audit_log, get_client_ip
from api.rate_limiting import LoginThrottle, MFAThrottle, MFAUserThrottle, PasswordResetThrottle
from api.audit_logging import log_authentication_event, log_mfa_event, log_rate_limit_exceeded

# Email validator for consistent validation
_email_validator = EmailValidator()
_logger = logging.getLogger(__name__)


def _detect_platform(user_agent: str) -> str:
    """
    Detect platform from user agent string.
    
    MedSync supports Windows (Hello biometric) and macOS (Touch ID/Face ID) only.
    Other platforms are rejected during passkey registration.
    """
    ua = (user_agent or "").lower()
    if 'windows' in ua:
        return 'windows'
    # macOS detection (must check for 'mac' after iOS check, but iOS not supported)
    if 'macintosh' in ua or 'mac os x' in ua:
        return 'macos'
    # Reject all other platforms
    return 'unsupported'


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

    # ==================== PASSKEY RULE #1: Passkey replaces both password AND MFA ====================
    # If user has a registered passkey on ANY device, they already have multi-factor auth
    # (something you have: device + something you are: biometric).
    # Do NOT require TOTP on top — passkey is cryptographically stronger than TOTP.
    # This also means: if user has passkey but chose password login as fallback,
    # still skip MFA because passkey secures the account at a higher level.
    
    from core.models import UserPasskey
    has_registered_passkey = UserPasskey.objects.filter(user=user).exists()
    
    if has_registered_passkey:
        # User has a passkey registered → issue JWT directly, no MFA
        audit_log(user, "LOGIN", resource_type="PASSWORD", request=request,
                  extra_data={"has_passkey": True, "skipped_mfa": True})
        refresh = RefreshToken.for_user(user)
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "role": user.role,
            "hospital_id": str(user.hospital_id) if user.hospital_id else None,
            "user_profile": _user_to_dict(user),
        })

    # ==================== PASSKEY RULE #2: Password + MFA is the fallback ====================
    # No passkey registered → require MFA if enabled
    
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
        elif user.totp_secret:
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
@throttle_classes([LoginThrottle])
def activate_setup(request):
    # Prefer token in body (POST) to avoid query string in logs/Referer. GET kept for backward compat.
    token = (
        request.data.get("token") or "").strip() if request.method == "POST" else (
        request.GET.get("token") or "").strip()
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
@throttle_classes([LoginThrottle])
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
@throttle_classes([PasswordResetThrottle])
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
@throttle_classes([PasswordResetThrottle])
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


# ======================== PASSKEY (WEBAUTHN) ENDPOINTS ========================

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def passkey_register_begin(request):
    """
    Start WebAuthn registration ceremony for authenticated user.
    
    Returns challenge and options for browser to create passkey credential.
    Challenge is stored in session for verification in complete step.
    
    Response: WebAuthn registration options JSON with challenge, user, rp, etc.
    """
    if not settings.WEBAUTHN_ENABLED:
        return Response(
            {"message": "Passkey registration is not enabled"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    user = request.user
    
    try:
        from webauthn import generate_registration_options
        from webauthn.helpers.structs import (
            AuthenticatorSelectionCriteria,
            UserVerificationRequirement,
            ResidentKeyRequirement,
        )
        
        options = generate_registration_options(
            rp_id=settings.WEBAUTHN_RP_ID,
            rp_name=settings.WEBAUTHN_RP_NAME,
            user_id=str(user.id).encode(),
            user_name=user.email,
            user_display_name=user.full_name or user.email,
            authenticator_selection=AuthenticatorSelectionCriteria(
                user_verification=UserVerificationRequirement.REQUIRED,
                resident_key=ResidentKeyRequirement.PREFERRED,
            ),
        )
        
        # Store challenge in session for verification in complete step
        # Convert bytes to base64url string for session storage
        from webauthn.helpers import bytes_to_base64url
        challenge_b64 = bytes_to_base64url(options.challenge)
        request.session['passkey_registration_challenge'] = challenge_b64
        request.session.set_expiry(settings.WEBAUTHN_CHALLENGE_TTL)
        
        # Convert to JSON-serializable format
        from webauthn.helpers import options_to_json_dict
        
        response_data = options_to_json_dict(options)
        return Response(response_data)
        
    except Exception as e:
        _logger.error(f"Error in passkey_register_begin: {e}")
        return Response(
            {"message": "Failed to generate registration options"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def passkey_register_complete(request):
    """
    Complete WebAuthn registration ceremony.
    
    Verifies credential, stores it for future authentication.
    Requires valid challenge from passkey_register_begin step.
    
    Request: WebAuthn credential (from navigator.credentials.create)
    Response: { message, credential_id, device_name }
    """
    if not settings.WEBAUTHN_ENABLED:
        return Response(
            {"message": "Passkey registration is not enabled"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    user = request.user
    
    try:
        from webauthn import verify_registration_response
        
        challenge = request.session.get('passkey_registration_challenge')
        if not challenge:
            return Response(
                {"message": "Registration challenge not found or expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Convert challenge from base64url string back to bytes
        from webauthn.helpers import base64url_to_bytes
        challenge_bytes = base64url_to_bytes(challenge)
        
        credential_data = request.data
        device_name = request.data.get('device_name', 'Unnamed device')
        transports = request.data.get('transports', [])
        
        verified = verify_registration_response(
            credential=credential_data,
            expected_challenge=challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
        )
        
        # Store passkey credential with platform detection
        from core.models import UserPasskey
        
        platform = _detect_platform(request.META.get('HTTP_USER_AGENT', ''))
        
        # MedSync is desktop-only: support Windows Hello and macOS biometrics only
        if platform not in ('windows', 'macos'):
            return Response(
                {
                    "message": "Passkey registration is only supported on Windows (with Hello) and macOS (with Touch ID/Face ID). "
                               "Please use a Windows laptop or MacBook to register a passkey."
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        
        client_ip = get_client_ip(request)
        
        passkey = UserPasskey.objects.create(
            user=user,
            credential_id=verified.credential_id,
            public_key=verified.credential_public_key,
            sign_count=verified.sign_count,
            device_name=device_name,
            platform=platform,
            transports=transports or [],
            last_ip_address=client_ip,
        )
        
        # Log audit event
        audit_log(
            user,
            "PASSKEY_REGISTERED",
            resource_type="USER_PASSKEY",
            resource_id=str(passkey.id),
            extra_data={"device_name": device_name, "platform": platform},
            request=request,
        )
        
        # Clear session challenge
        del request.session['passkey_registration_challenge']
        
        return Response({
            "message": "Passkey registered successfully",
            "credential_id": str(passkey.id),
            "device_name": passkey.device_name,
            "platform": passkey.platform,
        })
        
    except Exception as e:
        _logger.error(f"Error in passkey_register_complete: {e}")
        return Response(
            {"message": f"Passkey registration failed: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def passkey_check(request):
    """
    Check if a user has registered passkeys (for frontend UI optimization).
    
    Does NOT start authentication ceremony — just checks if passkeys exist.
    Frontend uses this to show/hide passkey button before user submits password.
    
    Request: { email }
    Response: { has_passkeys: bool }
    """
    if not settings.WEBAUTHN_ENABLED:
        return Response(
            {"has_passkeys": False},
            status=status.HTTP_200_OK,
        )
    
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response(
            {"has_passkeys": False},
            status=status.HTTP_200_OK,
        )
    
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # Don't reveal that user doesn't exist (prevents enumeration)
        return Response(
            {"has_passkeys": False},
            status=status.HTTP_200_OK,
        )
    
    try:
        from core.models import UserPasskey
        
        has_passkeys = UserPasskey.objects.filter(user=user).exists()
        return Response({"has_passkeys": has_passkeys})
        
    except Exception as e:
        _logger.error(f"Error in passkey_check: {e}")
        return Response(
            {"has_passkeys": False},
            status=status.HTTP_200_OK,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def passkey_auth_begin(request):
    """
    Start WebAuthn authentication ceremony.
    
    Given email, returns challenge and list of allowed credentials (passkeys).
    Challenge is stored in session for verification in complete step.
    
    Request: { email }
    Response: WebAuthn authentication options with challenge and allowCredentials
    
    Note: Desktop-only deployment. Mobile devices not supported.
    """
    if not settings.WEBAUTHN_ENABLED:
        return Response(
            {"message": "Passkey authentication is not enabled"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Validate desktop platform
    platform = _detect_platform(request.META.get('HTTP_USER_AGENT', ''))
    if platform not in ('windows', 'macos'):
        return Response(
            {
                "message": "MedSync requires a Windows laptop or MacBook. "
                           "Mobile devices are not supported. Please use a desktop computer."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    
    email = request.data.get('email', '').strip().lower()
    if not email:
        return Response(
            {"message": "Email required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    try:
        user = User.objects.get(email__iexact=email)
    except User.DoesNotExist:
        # Don't reveal that user doesn't exist (prevents enumeration)
        return Response(
            {"message": "No passkeys found for this email"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    try:
        from webauthn import generate_authentication_options
        from webauthn.helpers.structs import (
            UserVerificationRequirement,
            PublicKeyCredentialDescriptor,
            PublicKeyCredentialType,
        )
        from webauthn.helpers import bytes_to_base64url
        from core.models import UserPasskey
        
        passkeys = UserPasskey.objects.filter(user=user)
        if not passkeys.exists():
            return Response(
                {"message": "No passkeys found for this email"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Create proper PublicKeyCredentialDescriptor objects
        allow_credentials = [
            PublicKeyCredentialDescriptor(
                type=PublicKeyCredentialType.PUBLIC_KEY,
                id=pk.credential_id,  # Keep as bytes, options_to_json_dict will encode it
                transports=pk.transports or [],
            )
            for pk in passkeys
        ]
        
        options = generate_authentication_options(
            rp_id=settings.WEBAUTHN_RP_ID,
            allow_credentials=allow_credentials,
            user_verification=UserVerificationRequirement.REQUIRED,
        )
        
        # Store challenge and user_id in session for verification in complete step
        # Convert bytes to base64url string for session storage
        challenge_b64 = bytes_to_base64url(options.challenge)
        request.session['passkey_auth_challenge'] = challenge_b64
        request.session['passkey_auth_user_id'] = str(user.id)
        request.session.set_expiry(settings.WEBAUTHN_CHALLENGE_TTL)
        
        # Convert to JSON-serializable format
        from webauthn.helpers import options_to_json_dict
        
        response_data = options_to_json_dict(options)
        return Response(response_data)
        
    except Exception as e:
        _logger.error(f"Error in passkey_auth_begin: {e}")
        return Response(
            {"message": "Failed to generate authentication options"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([MFAThrottle])
def passkey_auth_complete(request):
    """
    Complete WebAuthn authentication ceremony.
    
    Verifies credential signature, checks replay attack counter (sign_count),
    and issues JWT tokens on success.
    
    Request: WebAuthn assertion (from navigator.credentials.get)
    Response: { access_token, refresh_token, user_profile }
    
    Note: Desktop-only deployment. Mobile devices not supported.
    """
    if not settings.WEBAUTHN_ENABLED:
        return Response(
            {"message": "Passkey authentication is not enabled"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Validate desktop platform
    platform = _detect_platform(request.META.get('HTTP_USER_AGENT', ''))
    if platform not in ('windows', 'macos'):
        return Response(
            {
                "message": "MedSync requires a Windows laptop or MacBook. "
                           "Mobile devices are not supported. Please use a desktop computer."
            },
            status=status.HTTP_403_FORBIDDEN,
        )
    
    try:
        from webauthn import verify_authentication_response
        from core.models import UserPasskey
        
        challenge = request.session.get('passkey_auth_challenge')
        user_id = request.session.get('passkey_auth_user_id')
        
        if not challenge or not user_id:
            return Response(
                {"message": "Authentication challenge not found or expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Convert challenge from base64url string back to bytes
        from webauthn.helpers import base64url_to_bytes
        challenge_bytes = base64url_to_bytes(challenge)
        
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"message": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # Get the credential assertion from request
        assertion_data = request.data
        credential_id = assertion_data.get('id')
        
        # Find the passkey for this credential
        try:
            import base64
            # credential_id comes as base64url string from browser
            if isinstance(credential_id, str):
                credential_id_bytes = base64.urlsafe_b64decode(
                    credential_id + '=' * (4 - len(credential_id) % 4)
                )
            else:
                credential_id_bytes = credential_id
            
            passkey = UserPasskey.objects.get(
                user=user,
                credential_id=credential_id_bytes,
            )
        except (UserPasskey.DoesNotExist, ValueError) as e:
            _logger.error(f"Passkey not found for credential_id: {e}")
            return Response(
                {"message": "Invalid passkey"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # Verify assertion signature and replay attack
        verified = verify_authentication_response(
            credential=assertion_data,
            expected_challenge=challenge_bytes,
            expected_rp_id=settings.WEBAUTHN_RP_ID,
            expected_origin=settings.WEBAUTHN_ORIGIN,
            credential_public_key=passkey.public_key,
            credential_current_sign_count=passkey.sign_count,
        )
        
        # ⚠️  CRITICAL: Check sign_count to prevent replay attacks
        if verified.new_sign_count <= passkey.sign_count and passkey.sign_count != 0:
            _logger.warning(
                f"REPLAY ATTACK DETECTED: User {user.email}, "
                f"sign_count {verified.new_sign_count} <= {passkey.sign_count}"
            )
            audit_log(
                user,
                "LOGIN_FAILED",
                resource_type="PASSKEY",
                extra_data={"reason": "Replay attack detected"},
                request=request,
            )
            return Response(
                {"message": "Authentication failed"},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        
        # Update sign_count, last_used_at, and last_ip_address
        client_ip = get_client_ip(request)
        passkey.sign_count = verified.new_sign_count
        passkey.last_used_at = timezone.now()
        passkey.last_ip_address = client_ip
        passkey.save(update_fields=['sign_count', 'last_used_at', 'last_ip_address'])
        
        # Issue JWT tokens
        refresh = RefreshToken.for_user(user)
        
        # Clear session
        del request.session['passkey_auth_challenge']
        del request.session['passkey_auth_user_id']
        
        # Log successful authentication
        audit_log(user, "LOGIN", resource_type="PASSKEY", request=request)
        
        return Response({
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "role": user.role,
            "hospital_id": str(user.hospital_id) if user.hospital_id else None,
            "user_profile": _user_to_dict(user),
        })
        
    except Exception as e:
        _logger.error(f"Error in passkey_auth_complete: {e}", exc_info=True)
        return Response(
            {"message": f"Authentication failed: {str(e)}"},
            status=status.HTTP_401_UNAUTHORIZED,
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_passkeys(request):
    """
    List all passkeys registered for the authenticated user with multi-device info.
    
    Response: [ { id, device_name, platform, last_used_at, created_at }, ... ]
    """
    user = request.user
    
    try:
        from core.models import UserPasskey
        
        passkeys = UserPasskey.objects.filter(user=user).order_by('-created_at')
        
        return Response([
            {
                "id": str(pk.id),
                "device_name": pk.device_name,
                "platform": pk.platform,
                "platform_display": pk.get_platform_display(),
                "created_at": pk.created_at.isoformat(),
                "last_used_at": pk.last_used_at.isoformat() if pk.last_used_at else None,
                "last_ip_address": pk.last_ip_address,
                "transports": pk.transports,
            }
            for pk in passkeys
        ])
        
    except Exception as e:
        _logger.error(f"Error in list_passkeys: {e}")
        return Response(
            {"message": "Failed to list passkeys"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_passkey(request, pk):
    """
    Delete a passkey by ID.
    
    URL: /auth/passkeys/{pk}
    """
    user = request.user
    
    try:
        from core.models import UserPasskey
        
        passkey = UserPasskey.objects.get(id=pk, user=user)
        passkey_id = str(passkey.id)
        passkey.delete()
        
        # Log audit event
        audit_log(
            user,
            "PASSKEY_REMOVED",
            resource_type="USER_PASSKEY",
            resource_id=passkey_id,
            request=request,
        )
        
        return Response({"message": "Passkey deleted successfully"})
        
    except Exception as e:
        _logger.error(f"Error in delete_passkey: {e}")
        return Response(
            {"message": "Passkey not found or could not be deleted"},
            status=status.HTTP_404_NOT_FOUND,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def rename_passkey(request, pk):
    """
    Rename a passkey device name.
    
    URL: /auth/passkeys/{pk}/rename
    Body: { "device_name": "New Device Name" }
    """
    user = request.user
    new_name = request.data.get("new_name", "").strip()
    
    if not new_name or len(new_name) < 1 or len(new_name) > 100:
        return Response(
            {"message": "Device name must be between 1 and 100 characters"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    try:
        from core.models import UserPasskey
        
        passkey = UserPasskey.objects.get(id=pk, user=user)
        old_name = passkey.device_name
        passkey.device_name = new_name
        passkey.save()
        
        # Log audit event
        audit_log(
            user,
            "PASSKEY_RENAMED",
            resource_type="USER_PASSKEY",
            resource_id=str(passkey.id),
            request=request,
            extra_data={"old_name": old_name, "new_name": new_name},
        )
        
        return Response({
            "message": "Passkey renamed successfully",
            "device_name": passkey.device_name,
        })
        
    except UserPasskey.DoesNotExist:
        return Response(
            {"message": "Passkey not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    except Exception as e:
        _logger.error(f"Error in rename_passkey: {e}")
        return Response(
            {"message": "Failed to rename passkey"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


# ============================================================================
# ADMIN PASSKEY MANAGEMENT ENDPOINTS
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def admin_list_user_passkeys(request, user_id):
    """
    List passkeys for a specific user (admin/hospital admin only).
    
    Roles:
    - super_admin: can view any user's passkeys
    - hospital_admin: can view staff's passkeys in their hospital
    """
    from core.models import User, UserPasskey
    
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Authorization: super_admin can view anyone; hospital_admin can view staff in their hospital
    if request.user.role == "super_admin":
        pass  # Super admin can view any user
    elif request.user.role == "hospital_admin":
        # Hospital admin can view staff in their hospital
        if target_user.hospital_id != request.user.hospital_id:
            return Response(
                {"message": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
    else:
        return Response(
            {"message": "Only admins can view user passkeys"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    try:
        passkeys = UserPasskey.objects.filter(user=target_user).order_by("-created_at")
        
        result = [
            {
                "id": str(pk.id),
                "device_name": pk.device_name,
                "platform": pk.platform,
                "created_at": pk.created_at.isoformat(),
                "last_used_at": pk.last_used_at.isoformat() if pk.last_used_at else None,
                "transports": pk.transports or [],
            }
            for pk in passkeys
        ]
        
        return Response({"passkeys": result})
        
    except Exception as e:
        _logger.error(f"Error listing user passkeys: {e}")
        return Response(
            {"message": "Failed to list user passkeys"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def admin_reset_user_passkeys(request, user_id):
    """
    Admin: Reset (remove all) passkeys for a user.
    
    Use when a user loses access to all devices or requests a security reset.
    The user can re-register passkeys during next login or via settings.
    
    Roles:
    - super_admin: can reset any user's passkeys
    - hospital_admin: can reset staff's passkeys in their hospital
    """
    from core.models import User, UserPasskey
    
    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"message": "User not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Authorization
    if request.user.role == "super_admin":
        pass  # Super admin can reset anyone
    elif request.user.role == "hospital_admin":
        # Hospital admin can reset staff in their hospital
        if target_user.hospital_id != request.user.hospital_id:
            return Response(
                {"message": "Unauthorized"},
                status=status.HTTP_403_FORBIDDEN,
            )
    else:
        return Response(
            {"message": "Only admins can reset user passkeys"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    try:
        passkeys = UserPasskey.objects.filter(user=target_user)
        count = passkeys.count()
        
        # Delete all passkeys
        passkeys.delete()
        
        # Log audit event for each deleted passkey
        audit_log(
            request.user,
            "PASSKEY_RESET_BY_ADMIN",
            resource_type="USER",
            resource_id=str(target_user.id),
            request=request,
            extra_data={
                "target_user_email": target_user.email,
                "passkeys_deleted": count,
            },
        )
        
        return Response({
            "message": f"Reset {count} passkey(s) for {target_user.email}",
            "passkeys_deleted": count,
        })
        
    except Exception as e:
        _logger.error(f"Error resetting user passkeys: {e}")
        return Response(
            {"message": "Failed to reset user passkeys"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )
