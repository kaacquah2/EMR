"""
AI Governance Module for MedSync.

Every AI feature MUST route through this module. No AI endpoint is exempt.

Responsibilities:
- Log every AI call with full context
- Validate response schema
- Enforce confidence threshold warnings
- Check hospital-level AI disable flag
- Rate limit AI calls
- Enforce clinical features circuit breaker
"""

import logging
import json
from datetime import timedelta
from functools import wraps
from typing import Any, Callable, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.request import Request

from core.models import Hospital, AuditLog

logger = logging.getLogger(__name__)

# Configuration
CONFIDENCE_THRESHOLD = 0.40  # Warn if confidence < 40%
AI_RATE_LIMIT_PER_USER = 5  # Max AI calls per minute per user
AI_RATE_LIMIT_WINDOW = 60  # Window in seconds


class AIGovernanceError(Exception):
    """Raised when AI governance check fails."""
    pass


class AIDisabledError(AIGovernanceError):
    """Raised when AI is disabled for the hospital."""
    pass


class AIRateLimitError(AIGovernanceError):
    """Raised when AI rate limit is exceeded."""
    pass


class AIClinicalFeaturesDisabledError(AIGovernanceError):
    """Raised when clinical AI features are not enabled globally or for the hospital."""
    pass


class AIModelDriftError(AIGovernanceError):
    """Raised when model drift exceeds safe thresholds."""
    pass


def check_model_drift_health(model_name: str = 'risk_predictor') -> None:
    """
    Check if the specified model has acceptable drift levels.

    Raises AIModelDriftError if PSI exceeds the critical threshold (0.25).
    This prevents predictions from a model whose input or output
    distribution has shifted significantly from training.
    """
    try:
        from api.ai.model_monitor import is_model_healthy

        if not is_model_healthy(model_name):
            raise AIModelDriftError(
                f"Model '{model_name}' has critical drift detected. "
                f"Predictions are blocked until the model is retrained or "
                f"drift is investigated. Contact your ML administrator."
            )
    except AIModelDriftError:
        raise
    except Exception as e:
        # If monitoring itself fails, log but don't block
        logger.warning(f"Could not check model health for {model_name}: {e}")


def log_ai_call(
    user,
    hospital: Optional[Hospital],
    analysis_type: str,
    input_summary: str,
    output_summary: str,
    model_version: str,
    confidence: Optional[float] = None,
    success: bool = True,
    error_message: Optional[str] = None,
    latency_ms: Optional[float] = None,
) -> None:
    """
    Log every AI call for audit and governance.
    """
    extra_data = {
        'analysis_type': analysis_type,
        'input_summary': input_summary[:500],  # Truncate for storage
        'output_summary': output_summary[:1000] if output_summary else None,
        'model_version': model_version,
        'confidence': confidence,
        'success': success,
        'latency_ms': latency_ms,
    }
    if error_message:
        extra_data['error'] = error_message[:500]
    
    AuditLog.objects.create(
        user=user,
        action='AI_ANALYSIS' if success else 'AI_ANALYSIS_FAILED',
        resource_type='AIAnalysis',
        resource_id=analysis_type,
        hospital=hospital,
        ip_address='system',
        extra_data=extra_data,
    )
    
    logger.info(
        f"AI Call: user={user.email if user else 'System'}, type={analysis_type}, "
        f"confidence={confidence}, latency={latency_ms}ms, success={success}"
    )


def validate_ai_output(analysis_type: str, result: Dict[str, Any]) -> tuple[bool, str]:
    """
    Validate AI output for clinical safety and schema integrity.
    
    Returns: (is_valid, error_message)
    """
    if not result:
        return False, "Empty result"
        
    try:
        # Common checks
        if 'confidence_score' in result:
            conf = result['confidence_score']
            if not (0 <= conf <= 1):
                return False, f"Invalid confidence_score: {conf}"
                
        # Type-specific checks
        if analysis_type == 'risk_prediction':
            predictions = result.get('risk_predictions', {})
            if not predictions:
                return False, "No risk predictions found"
            for disease, data in predictions.items():
                score = data.get('risk_score', 0)
                if not (0 <= score <= 100):
                    return False, f"Invalid risk_score for {disease}: {score}"
                    
        elif analysis_type == 'triage':
            level = result.get('triage_level')
            valid_levels = ['critical', 'high', 'medium', 'low', 'unknown']
            if level not in valid_levels:
                return False, f"Invalid triage_level: {level}"
                
        elif analysis_type == 'comprehensive':
            required_keys = ['clinical_summary', 'recommended_actions', 'confidence_score']
            for key in required_keys:
                if key not in result:
                    return False, f"Missing required key in comprehensive analysis: {key}"
            
        return True, ""
        
    except Exception as e:
        return False, f"Validation error: {str(e)}"


def check_ai_enabled(hospital: Optional[Hospital]) -> None:
    """
    Check if AI is enabled for the hospital.
    Raises AIDisabledError if disabled.
    """
    if hospital is None:
        return  # Super admin without hospital context - allow
    
    # Check hospital-level AI flag
    if hasattr(hospital, 'ai_enabled') and not hospital.ai_enabled:
        raise AIDisabledError(
            f"AI features are disabled for {hospital.name}. "
            "Contact your system administrator to enable."
        )


def check_ai_rate_limit(user) -> None:
    """
    Check if user has exceeded AI rate limit.
    Raises AIRateLimitError if exceeded.
    """
    cache_key = f"ai_rate_limit:{user.id}"
    current_count = cache.get(cache_key, 0)
    
    if current_count >= AI_RATE_LIMIT_PER_USER:
        raise AIRateLimitError(
            f"AI rate limit exceeded. Maximum {AI_RATE_LIMIT_PER_USER} "
            f"requests per minute. Please wait and try again."
        )
    
    # Increment counter
    cache.set(cache_key, current_count + 1, AI_RATE_LIMIT_WINDOW)


def validate_ai_response(response: dict, required_fields: list[str]) -> bool:
    """
    Validate AI response has required schema.
    Returns True if valid, False if malformed.
    """
    if not isinstance(response, dict):
        return False
    
    for field in required_fields:
        if field not in response:
            logger.warning(f"AI response missing required field: {field}")
            return False
    
    return True


def check_confidence_threshold(confidence: Optional[float]) -> dict:
    """
    Check if confidence is below threshold.
    Returns warning dict if below threshold.
    """
    if confidence is None:
        return {}
    
    if confidence < CONFIDENCE_THRESHOLD:
        return {
            'confidence_warning': True,
            'confidence_message': (
                f"AI confidence is {confidence:.0%}, below the "
                f"{CONFIDENCE_THRESHOLD:.0%} threshold. Results should "
                "be reviewed carefully."
            )
        }
    
    return {}


def log_suggestion_override(
    user,
    hospital: Optional[Hospital],
    suggestion_type: str,
    suggestion_id: str,
    reason: Optional[str] = None,
) -> None:
    """
    Log when a doctor does not apply an AI suggestion.
    """
    AuditLog.objects.create(
        user=user,
        action='AI_SUGGESTION_IGNORED',
        resource_type='AIAnalysis',
        resource_id=suggestion_id,
        hospital=hospital,
        ip_address='system',
        extra_data={
            'suggestion_type': suggestion_type,
            'reason': reason,
        },
    )


def check_ai_clinical_features_enabled(hospital: Optional[Hospital]) -> None:
    """
    Check if clinical AI features are enabled globally and for the hospital.
    
    Raises AIClinicalFeaturesDisabledError if:
    - AI_CLINICAL_FEATURES_ENABLED = False globally, OR
    - Hospital hasn't approved AI features
    
    This is a CIRCUIT BREAKER: clinical AI is disabled by default and must be
    explicitly approved per hospital after model validation.
    """
    # Global circuit breaker
    if not getattr(settings, 'AI_CLINICAL_FEATURES_ENABLED', False):
        raise AIClinicalFeaturesDisabledError(
            'Clinical AI features are not enabled. Models are being validated. '
            'Contact MedSync administrators.'
        )
    
    # Hospital-level approval check
    if hospital:
        from api.models import AIDeploymentLog
        approval = AIDeploymentLog.objects.filter(
            hospital=hospital,
            enabled=True
        ).latest('enabled_at')
        
        if not approval:
            raise AIClinicalFeaturesDisabledError(
                f'AI features not approved for {hospital.name}. '
                f'Contact hospital administrator.'
            )


def ai_governance_clinical(analysis_type: str, model_version: str = "1.0"):
    """
    Decorator for CLINICAL AI endpoints with circuit breaker enforcement.
    
    Unlike @ai_governance, this enforces:
    - AI_CLINICAL_FEATURES_ENABLED must be True
    - Hospital must have approval from AIDeploymentLog
    - Model version and confidence thresholds are checked
    
    Use this for: comprehensive_analysis, risk_prediction, diagnosis_support, triage
    Don't use for: demo/experimental endpoints
    
    Usage:
        @api_view(['POST'])
        @ai_governance_clinical('comprehensive_analysis', model_version='1.0.0')
        def analyze_patient(request, patient_id):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: Request, *args, **kwargs) -> Response:
            user = request.user
            hospital = getattr(user, 'hospital', None)
            
            try:
                # CIRCUIT BREAKER: Check clinical features enabled
                check_ai_clinical_features_enabled(hospital)
                
                # Standard governance checks
                check_ai_enabled(hospital)
                check_ai_rate_limit(user)

                # Model health check (drift detection)
                try:
                    check_model_drift_health()
                except AIModelDriftError as e:
                    log_ai_call(
                        user=user,
                        hospital=hospital,
                        analysis_type=analysis_type,
                        input_summary=str(request.data)[:500],
                        output_summary='',
                        model_version=model_version,
                        success=False,
                        error_message=str(e),
                    )
                    return Response(
                        {
                            'error': 'Model drift detected',
                            'message': str(e),
                            'status': 'model_drift_critical',
                        },
                        status=status.HTTP_503_SERVICE_UNAVAILABLE
                    )
                
                # Execute the AI view
                response = view_func(request, *args, **kwargs)
                
                # Post-execution logging with model version tracking
                if response.status_code == 200:
                    response_data = response.data if hasattr(response, 'data') else {}
                    confidence = response_data.get('confidence') or response_data.get('overall_confidence')
                    
                    log_ai_call(
                        user=user,
                        hospital=hospital,
                        analysis_type=analysis_type,
                        input_summary=str(request.data)[:500],
                        output_summary=str(response_data)[:1000],
                        model_version=model_version,
                        confidence=confidence,
                        success=True,
                    )
                    
                    # Check against clinical threshold
                    clinical_threshold = getattr(settings, 'AI_CONFIDENCE_THRESHOLD_CLINICAL', 0.80)
                    if confidence and confidence < clinical_threshold:
                        if isinstance(response_data, dict):
                            response_data['confidence_warning'] = (
                                f'Confidence {confidence:.1%} below clinical threshold {clinical_threshold:.1%}. '
                                f'Recommendation should be reviewed by clinician.'
                            )
                            response.data = response_data
                
                return response
                
            except AIClinicalFeaturesDisabledError as e:
                log_ai_call(
                    user=user,
                    hospital=hospital,
                    analysis_type=analysis_type,
                    input_summary=str(request.data)[:500],
                    output_summary='',
                    model_version=model_version,
                    success=False,
                    error_message=str(e),
                )
                return Response(
                    {
                        'error': 'Clinical AI features disabled',
                        'message': str(e),
                        'status': 'clinical_features_disabled',
                    },
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            except (AIDisabledError, AIRateLimitError) as e:
                log_ai_call(
                    user=user,
                    hospital=hospital,
                    analysis_type=analysis_type,
                    input_summary=str(request.data)[:500],
                    output_summary='',
                    model_version=model_version,
                    success=False,
                    error_message=str(e),
                )
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
            
            except Exception as e:
                logger.error(f"AI governance error: {e}")
                return Response(
                    {'error': 'Internal AI error'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return wrapper
    return decorator

    """
    Decorator for AI endpoints that enforces governance rules.
    
    Usage:
        @api_view(['POST'])
        @ai_governance('risk_prediction', model_version='1.0')
        def predict_risk(request, patient_id):
            ...
    """
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: Request, *args, **kwargs) -> Response:
            user = request.user
            hospital = getattr(user, 'hospital', None)
            
            try:
                # Pre-flight checks
                check_ai_enabled(hospital)
                check_ai_rate_limit(user)
                
                # Execute the AI view
                response = view_func(request, *args, **kwargs)
                
                # Post-execution logging
                if response.status_code == 200:
                    response_data = response.data if hasattr(response, 'data') else {}
                    confidence = response_data.get('confidence') or response_data.get('overall_confidence')
                    
                    log_ai_call(
                        user=user,
                        hospital=hospital,
                        analysis_type=analysis_type,
                        input_summary=str(request.data)[:500],
                        output_summary=str(response_data)[:1000],
                        model_version=model_version,
                        confidence=confidence,
                        success=True,
                    )
                    
                    # Add confidence warning if needed
                    warning = check_confidence_threshold(confidence)
                    if warning and isinstance(response_data, dict):
                        response_data.update(warning)
                        response.data = response_data
                
                return response
                
            except AIDisabledError as e:
                log_ai_call(
                    user=user,
                    hospital=hospital,
                    analysis_type=analysis_type,
                    input_summary=str(request.data)[:500],
                    output_summary='',
                    model_version=model_version,
                    success=False,
                    error_message=str(e),
                )
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE
                )
                
            except AIRateLimitError as e:
                log_ai_call(
                    user=user,
                    hospital=hospital,
                    analysis_type=analysis_type,
                    input_summary=str(request.data)[:500],
                    output_summary='',
                    model_version=model_version,
                    success=False,
                    error_message=str(e),
                )
                return Response(
                    {'error': str(e)},
                    status=status.HTTP_429_TOO_MANY_REQUESTS
                )
                
        return wrapper
    return decorator
