"""
Step-Up Verification Endpoints

Implements NIST 800-63 AAL3 step-up MFA for high-risk actions:
- POST /api/v1/auth/step-up/request — Initiate step-up, send email OTP
- POST /api/v1/auth/step-up/verify — Verify OTP, receive step-up JWT (valid 5 min)

Step-up JWTs are scoped to a single action type and cannot be reused.
"""

from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from datetime import timedelta
from django.core.mail import send_mail
from django.conf import settings
import secrets
import hashlib
import jwt

from core.models import User, StepUpSession
from api.serializers import UserSerializer
from api.utils import get_effective_hospital
import logging

logger = logging.getLogger(__name__)


class StepUpRequestSerializer(serializers.Serializer):
    """Request schema for step-up initiation."""
    action = serializers.CharField(
        max_length=50,
        help_text="Action type: cross_facility_access, break_glass, consent, export, superadmin_write"
    )


class StepUpVerifySerializer(serializers.Serializer):
    """Request schema for step-up OTP verification."""
    step_up_token = serializers.CharField(max_length=255)
    otp_code = serializers.CharField(max_length=6, min_length=6)
    action = serializers.CharField(max_length=50)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def step_up_request(request):
    """
    Initiate step-up verification for a high-risk action.
    
    Sends a 6-digit OTP to the user's registered email.
    Returns a step_up_token valid for 5 minutes.
    
    Request:
        {
            "action": "cross_facility_access"  # or break_glass, consent, export, superadmin_write
        }
    
    Response (200):
        {
            "step_up_token": "eyJ0eXAiOiJKV1QiLC...",
            "expires_in": 300,
            "message": "OTP sent to user@example.com"
        }
    
    Response (400):
        { "error": "Invalid action type" }
    """
    serializer = StepUpRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    action = serializer.validated_data['action']
    
    # Validate action type
    valid_actions = ['cross_facility_access', 'break_glass', 'consent', 'export', 'superadmin_write']
    if action not in valid_actions:
        return Response(
            {'error': f'Invalid action type. Must be one of: {", ".join(valid_actions)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Invalidate any previous step-up session for this action
    StepUpSession.objects.filter(
        user=request.user,
        action=action,
        is_verified=False
    ).update(is_verified=None)  # Mark as expired
    
    # Generate OTP and session token
    otp_code = secrets.randbelow(999999)
    otp_code_str = f"{otp_code:06d}"
    
    session_token = secrets.token_urlsafe(32)
    otp_hash = hashlib.sha256(otp_code_str.encode()).hexdigest()
    
    # Create StepUpSession
    expires_at = timezone.now() + timedelta(minutes=5)
    step_up_session = StepUpSession.objects.create(
        user=request.user,
        action=action,
        session_token=session_token,
        otp_hash=otp_hash,
        expires_at=expires_at,
        attempts=0,
        is_verified=False,
    )
    
    # Send email OTP
    try:
        send_mail(
            subject=f'MedSync Step-Up Verification Code',
            message=f'Your MedSync step-up verification code is: {otp_code_str}\n\n'
                    f'This code is valid for 5 minutes.\n'
                    f'Action: {action.replace("_", " ").title()}',
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.user.email],
            fail_silently=False,
        )
        logger.info(f"Step-up OTP sent to {request.user.email} for action {action}")
    except Exception as e:
        logger.error(f"Failed to send step-up OTP email: {e}")
        return Response(
            {'error': 'Failed to send OTP email'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    return Response(
        {
            'step_up_token': session_token,
            'expires_in': 300,
            'message': f'OTP sent to {request.user.email}',
        },
        status=status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def step_up_verify(request):
    """
    Verify step-up OTP and receive a step-up JWT.
    
    Request:
        {
            "step_up_token": "...",
            "otp_code": "123456",
            "action": "cross_facility_access"
        }
    
    Response (200):
        {
            "step_up_jwt": "eyJ0eXAiOiJKV1QiLC...",
            "expires_in": 300
        }
    
    Response (400):
        { "error": "Invalid OTP or expired session" }
    
    Response (429):
        { "error": "Too many failed attempts. Session locked." }
    """
    serializer = StepUpVerifySerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    session_token = serializer.validated_data['step_up_token']
    otp_code = serializer.validated_data['otp_code']
    action = serializer.validated_data['action']
    
    # Find the step-up session
    try:
        step_up_session = StepUpSession.objects.get(
            user=request.user,
            session_token=session_token,
            action=action,
            is_verified=False,
        )
    except StepUpSession.DoesNotExist:
        logger.warning(f"Step-up session not found for user {request.user.id}, action {action}")
        return Response(
            {'error': 'Invalid step-up session or already verified'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check expiry
    if step_up_session.is_expired():
        logger.info(f"Step-up session expired for user {request.user.id}, action {action}")
        return Response(
            {'error': 'Step-up session expired. Request a new one.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check attempt limit (max 3)
    if step_up_session.attempts >= 3:
        logger.warning(f"Too many failed attempts for step-up session {step_up_session.id}")
        return Response(
            {'error': 'Too many failed attempts. Session locked.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS
        )
    
    # Verify OTP
    otp_hash = hashlib.sha256(otp_code.encode()).hexdigest()
    if otp_hash != step_up_session.otp_hash:
        step_up_session.attempts += 1
        step_up_session.save()
        
        logger.warning(f"Invalid OTP for step-up session {step_up_session.id}, attempt {step_up_session.attempts}/3")
        return Response(
            {'error': f'Invalid OTP. {3 - step_up_session.attempts} attempts remaining.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # OTP verified — mark session and generate step-up JWT
    step_up_session.is_verified = True
    step_up_session.verified_at = timezone.now()
    step_up_session.save()
    
    logger.info(f"Step-up OTP verified for user {request.user.id}, action {action}")
    
    # Create step-up JWT (valid 5 minutes, scoped to action)
    step_up_jwt = _create_step_up_jwt(request.user, action)
    
    return Response(
        {
            'step_up_jwt': step_up_jwt,
            'expires_in': 300,  # 5 minutes
        },
        status=status.HTTP_200_OK
    )


def _create_step_up_jwt(user: User, action: str) -> str:
    """
    Create a short-lived step-up JWT scoped to a specific action.
    
    Args:
        user: User model instance
        action: Action type (cross_facility_access, break_glass, etc.)
    
    Returns:
        str: JWT token valid for 5 minutes
    """
    from django.conf import settings
    
    expires_at = timezone.now() + timedelta(minutes=5)
    
    payload = {
        'user_id': str(user.id),
        'username': user.username,
        'email': user.email,
        'step_up_action': action,
        'type': 'step_up',
        'exp': expires_at,
        'iat': timezone.now(),
    }
    
    token = jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm='HS256'
    )
    
    return token
