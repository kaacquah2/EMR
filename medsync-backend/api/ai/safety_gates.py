"""
AI Safety Gates and Circuit Breaker Module.

Enforces clinical-grade safety checks for all AI features:
- Global circuit breaker (DISABLE_AI_CLINICAL_FEATURES)
- Hospital-level approval verification
- Confidence threshold validation
- Comprehensive audit logging

All AI endpoints MUST use the @require_ai_clinical_enabled decorator.
"""

import logging
from functools import wraps
from typing import Callable, Optional

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request

from core.models import Hospital, AuditLog
from api.utils import sanitize_audit_resource_id

logger = logging.getLogger(__name__)


class AIClinicalFeatureDisabled(Exception):
    """Raised when AI clinical features are disabled."""
    pass


def is_ai_clinical_enabled(request: Request) -> bool:
    """
    Check if AI clinical features are enabled globally and for the hospital.
    
    Returns:
        True if AI clinical features are enabled and hospital is approved
        False otherwise
    
    Checks (in order):
    1. DISABLE_AI_CLINICAL_FEATURES setting (global circuit breaker)
    2. AI_CLINICAL_FEATURES_ENABLED setting (global enable flag)
    3. Hospital-level approval from AIDeploymentLog
    """
    # Global circuit breaker
    if getattr(settings, 'DISABLE_AI_CLINICAL_FEATURES', True):
        logger.warning('AI clinical features are disabled by DISABLE_AI_CLINICAL_FEATURES setting')
        return False
    
    # Global enable flag
    if not getattr(settings, 'AI_CLINICAL_FEATURES_ENABLED', False):
        logger.warning('AI clinical features are not enabled by AI_CLINICAL_FEATURES_ENABLED setting')
        return False
    
    # Get hospital from user
    user = request.user
    if not user or not hasattr(user, 'hospital'):
        logger.warning('User has no hospital context')
        return False
    
    hospital: Optional[Hospital] = user.hospital
    if not hospital:
        # Super admin without hospital assignment can use AI if globally enabled
        return True
    
    # Check hospital-level approval
    try:
        from api.models import AIDeploymentLog
        deployment = AIDeploymentLog.get_latest_for_hospital(hospital)
        is_enabled = deployment.enabled if deployment else False
        
        if not is_enabled:
            logger.warning(f'AI not approved for hospital {hospital.id}')
        
        return is_enabled
    except Exception as e:
        logger.error(f'Error checking hospital AI approval: {e}')
        return False


def require_ai_clinical_enabled() -> Callable:
    """
    Decorator that enforces AI clinical feature gate.
    
    Returns 503 ServiceUnavailable if AI clinical features are disabled.
    
    Usage:
        @api_view(['POST'])
        @requires_role('doctor', 'nurse')
        @require_ai_clinical_enabled()
        def analyze_patient(request, patient_id):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: Request, *args, **kwargs):
            # Check if AI clinical features are enabled
            if not is_ai_clinical_enabled(request):
                hospital = request.user.hospital if hasattr(request.user, 'hospital') else None
                
                # Log the gate check
                try:
                    AuditLog.objects.create(
                        user=request.user,
                        action='AI_FEATURE_BLOCKED',
                        resource_type='AIAnalysis',
                        resource_id='gate_check',
                        hospital=hospital,
                        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
                        user_agent=request.META.get('HTTP_USER_AGENT', ''),
                        extra_data={
                            'reason': 'AI clinical features disabled',
                            'disable_ai_clinical_features': getattr(settings, 'DISABLE_AI_CLINICAL_FEATURES', True),
                            'ai_clinical_features_enabled': getattr(settings, 'AI_CLINICAL_FEATURES_ENABLED', False),
                        }
                    )
                except Exception as log_err:
                    logger.warning(f'Failed to log AI gate check: {log_err}')
                
                return Response(
                    {
                        'error': 'AI clinical features are currently disabled',
                        'message': 'Clinical AI features are not available. Contact your administrator.',
                        'status': 'service_unavailable',
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            # Execute the actual view
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def log_ai_recommendation(
    user,
    hospital: Optional[Hospital],
    recommendation,
    patient_id: str,
    analysis_type: str = 'AIRecommendation',
) -> None:
    """
    Log an AI recommendation to audit trail.
    
    Args:
        user: Request user
        hospital: Hospital context
        recommendation: AI recommendation object (must have id, confidence, model_version)
        patient_id: Patient ID being analyzed
        analysis_type: Type of analysis (default 'AIRecommendation')
    """
    try:
        AuditLog.objects.create(
            user=user,
            action='AI_ANALYSIS',
            resource_type=analysis_type,
            resource_id=str(recommendation.id) if hasattr(recommendation, 'id') else 'unknown',
            hospital=hospital,
            ip_address='system',
            extra_data={
                'model_version': getattr(recommendation, 'model_version', 'unknown'),
                'confidence': getattr(recommendation, 'confidence', 0.0),
                'analysis_type': getattr(recommendation, 'analysis_type', analysis_type),
                'patient_id': sanitize_audit_resource_id(patient_id),
            }
        )
    except Exception as e:
        logger.warning(f'Failed to log AI recommendation: {e}')


def validate_ai_confidence_threshold(confidence: float) -> bool:
    """
    Validate that AI confidence meets clinical threshold.
    
    For clinical deployments, confidence must be >= 0.80 (80%).
    
    Args:
        confidence: Confidence score (0.0 to 1.0)
    
    Returns:
        True if confidence meets threshold, False otherwise
    """
    threshold = getattr(settings, 'AI_CONFIDENCE_THRESHOLD_CLINICAL', 0.80)
    
    if confidence < threshold:
        logger.warning(
            f'AI confidence {confidence:.2f} below clinical threshold {threshold:.2f}'
        )
        return False
    
    return True
