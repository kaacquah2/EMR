"""
AI Features REST API Endpoints.

Exposes AI Intelligence Module features via REST API:
- POST /api/v1/ai/analyze-patient/<patient_id> - Comprehensive analysis
- POST /api/v1/ai/risk-prediction/<patient_id> - Disease risk predictions
- POST /api/v1/ai/clinical-decision-support/<patient_id> - Differential diagnoses
- POST /api/v1/ai/triage/<patient_id> - Emergency triage classification
- POST /api/v1/ai/find-similar-patients/<patient_id> - Similar patient cases
- POST /api/v1/ai/referral-recommendation/<patient_id> - Hospital recommendations
- GET /api/v1/ai/analysis-history/<patient_id> - Past analyses
"""

import logging
import os
from datetime import timedelta
from typing import Any, Optional, cast

from django.utils import timezone

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request

from api.decorators import requires_role
from django.conf import settings
from api.utils import get_patient_queryset, get_effective_hospital, get_request_hospital
from api.models import AIAnalysis
from core.models import AuditLog
from api.ai.services import (
    RiskPredictionService,
    DiagnosisService,
    TriageService,
    SimilaritySearchService,
    ReferralRecommendationService,
    AIServiceException,
)
from api.ai.agents import get_orchestrator
from api.ai.data_processor import DataProcessor
from api.ai.feature_engineering import FeatureEngineer
from api.ai.persistence import save_comprehensive_analysis
from patients.models import Patient

logger = logging.getLogger(__name__)


def _model(cls: type[Any]) -> Any:
    """Django models expose `.objects` / `.DoesNotExist`; pyright needs a cast without django-stubs."""
    return cast(Any, cls)


def _as_str(value: Any, default: str = "") -> str:
    """Coerce DRF QueryDict / JSON body values to str for type-safe call sites."""
    if value is None:
        return default
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)) and len(value) > 0:
        return _as_str(value[0], default)
    if isinstance(value, dict):
        return default
    return str(value)


def _query_param_str(request: Request, key: str, default: str = "") -> str:
    qp: Any = request.query_params
    raw = qp.get(key, default)
    return _as_str(raw, default)


def _query_param_int(request: Request, key: str, default: int) -> int:
    return int(_query_param_str(request, key, str(default)))


def build_ai_status_payload() -> dict:
    """
    Lightweight AI integration status. Cached for 30 seconds to avoid
    repeated file I/O and database queries during rapid polling.
    
    Must not load models or run inference.
    """
    from django.core.cache import cache
    
    # Try cache first (cuts response time from 5-9s to <10ms if cached)
    cache_key = "ai_status_payload"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    model_paths = getattr(settings, "MODEL_PATHS", {}) or {}
    checks: dict = {}
    present = 0
    for key in ("triage_classifier", "risk_predictor", "diagnosis_classifier"):
        path = model_paths.get(key)
        configured = bool(path)
        exists = bool(path and os.path.exists(path))
        checks[key] = {"configured": configured, "present": exists}
        if exists:
            present += 1

    enabled = present > 0
    target_ms = 800
    avg_ms: Optional[int] = None

    analyses_24h = 0
    try:
        since = timezone.now() - timedelta(hours=24)
        analyses_24h = _model(AIAnalysis).objects.filter(created_at__gte=since).count()
    except Exception:
        pass

    status_str = "offline"
    if enabled:
        if avg_ms is None:
            status_str = "online"
        else:
            status_str = "degraded" if avg_ms > target_ms else "online"

    payload = {
        "status": status_str,
        "analyses_24h": analyses_24h,
        "avg_response_ms": avg_ms,
        "target_response_ms": target_ms,
        "modules": {
            "triage": "active" if checks.get("triage_classifier", {}).get("present") else "inactive",
            "risk_prediction": "active" if checks.get("risk_predictor", {}).get("present") else "inactive",
            "similarity_search": "active",
            "comprehensive": "active",
        },
        "uptime_7d_pct": None if enabled else 0,
        "models": checks,
    }
    
    # Cache for 30 seconds (status rarely changes, huge perf gain)
    cache.set(cache_key, payload, timeout=30)
    return payload


@api_view(["GET"])
@requires_role("super_admin")
def ai_status(request: Request) -> Response:
    """Lightweight AI integration status for the Super Admin dashboard."""
    return Response(build_ai_status_payload())


@api_view(['POST'])
@requires_role('doctor', 'nurse', 'hospital_admin', 'super_admin')
def analyze_patient_comprehensive(request: Request, patient_id: str) -> Response:
    """
    Run comprehensive multi-agent analysis on patient.
    
    Uses all 7 AI agents to provide complete clinical decision support.
    
    Query parameters:
    - include_similarity: bool (default=true) - Include similar patient search
    - include_referral: bool (default=true) - Include hospital recommendations
    
    Returns:
        200: Complete analysis result
        400: Bad request (missing data, invalid patient)
        403: Forbidden (insufficient permissions)
        404: Patient not found
    """
    try:
        # Parse query parameters
        include_similarity = _query_param_str(request, "include_similarity", "true").lower() == "true"
        include_referral = _query_param_str(request, "include_referral", "true").lower() == "true"
        
        # Extract patient data
        data_processor = DataProcessor(request.user)
        patient = data_processor._get_patient_or_raise(patient_id)
        patient_data = data_processor.extract_complete_patient_data(patient)
        
        # Engineer features
        feature_engineer = FeatureEngineer()
        features = feature_engineer.create_feature_vector(patient_data)
        
        # Get chief complaint from query or latest encounter
        body: Any = request.data
        chief_complaint = _as_str(body.get("chief_complaint", ""), "")
        if not chief_complaint:
            from records.models import Encounter

            latest_encounter = (
                _model(Encounter)
                .objects.filter(patient=patient, hospital=data_processor.effective_hospital)
                .order_by("-created_at")
                .first()
            )
            if latest_encounter:
                chief_complaint = latest_encounter.chief_complaint or ""
        
        # Run orchestrator
        orchestrator = get_orchestrator()
        analysis_result = orchestrator.analyze_patient_comprehensive(
            patient_data,
            features,
            chief_complaint=chief_complaint,
            include_similarity=include_similarity,
            include_referral=include_referral,
        )
        
        # Persist analysis for history and audit
        hospital = get_request_hospital(request)
        if hospital:
            try:
                save_comprehensive_analysis(
                    patient=patient,
                    hospital=hospital,
                    user=request.user,
                    analysis_result=analysis_result,
                    chief_complaint=chief_complaint,
                )
            except Exception as persist_err:
                logger.warning(f"Failed to persist AI analysis (continuing): {persist_err}")

        # Audit log
        _model(AuditLog).log_action(
            user=request.user,
            action='AI_ANALYSIS',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=hospital,
            request=request,
            extra_data={
                'analysis_type': 'comprehensive',
                'agents': analysis_result.get('agents_executed', []),
            }
        )
        
        logger.info(f"Comprehensive analysis for patient {patient_id} completed")
        return Response(analysis_result, status=status.HTTP_200_OK)
    
    except AIServiceException as e:
        logger.warning(f"AI Service error: {e}")
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except _model(Patient).DoesNotExist:
        return Response({'error': f'Patient {patient_id} not found'}, status=status.HTTP_404_NOT_FOUND)
    except Exception as e:
        logger.error(f"Error in comprehensive analysis: {e}")
        return Response(
            {'error': 'Analysis failed. Please try again.'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@requires_role('doctor', 'nurse', 'super_admin')
def predict_patient_risk(request: Request, patient_id: str) -> Response:
    """
    Predict disease risk for patient.
    
    Returns 5-year risk for:
    - Heart disease
    - Diabetes
    - Stroke
    - Pneumonia
    - Hypertension
    
    Returns:
        200: Risk predictions with contributing factors
        400: Bad request
        403: Forbidden
        404: Patient not found
    """
    try:
        service = RiskPredictionService(request.user)
        result = service.predict_risk(patient_id)
        
        # Audit
        _model(AuditLog).log_action(
            user=request.user,
            action='AI_RISK_PREDICTION',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            request=request,
        )
        
        logger.info(f"Risk prediction for patient {patient_id}")
        return Response(result, status=status.HTTP_200_OK)
    
    except AIServiceException as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Risk prediction error: {e}")
        return Response(
            {'error': 'Prediction failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@requires_role('doctor', 'super_admin')
def get_clinical_decision_support(request: Request, patient_id: str) -> Response:
    """
    Get differential diagnosis suggestions (Clinical Decision Support).
    
    Request body:
        {
            "chief_complaint": "string (optional)"
        }
    
    Returns:
        200: Diagnosis suggestions with test recommendations
        400: Bad request
        403: Forbidden (must be doctor)
        404: Patient not found
    """
    try:
        body: Any = request.data
        chief_complaint = _as_str(body.get("chief_complaint", ""), "")

        service = DiagnosisService(request.user)
        result = service.get_diagnosis_suggestions(patient_id, chief_complaint=chief_complaint or None)
        
        # Audit
        _model(AuditLog).log_action(
            user=request.user,
            action='AI_CDS',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            request=request,
        )
        
        logger.info(f"CDS for patient {patient_id}")
        return Response(result, status=status.HTTP_200_OK)
    
    except AIServiceException as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"CDS error: {e}")
        return Response(
            {'error': 'CDS failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@requires_role('nurse', 'doctor', 'super_admin')
def triage_patient(request: Request, patient_id: str) -> Response:
    """
    Triage patient by severity (emergency classification).
    
    Returns triage level: critical, high, medium, low
    Includes ESI (Emergency Severity Index) level (1-5)
    
    Request body:
        {
            "chief_complaint": "string (optional)"
        }
    
    Returns:
        200: Triage assessment with urgency indicators
        400: Bad request
        403: Forbidden
        404: Patient not found
    """
    try:
        body: Any = request.data
        chief_complaint = _as_str(body.get("chief_complaint", ""), "")

        service = TriageService(request.user)
        result = service.triage_patient(patient_id, chief_complaint=chief_complaint)
        
        # Audit
        _model(AuditLog).log_action(
            user=request.user,
            action='AI_TRIAGE',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            request=request,
            extra_data={'triage_level': result.get('triage_level')}
        )
        
        logger.info(f"Triage for patient {patient_id}: {result.get('triage_level')}")
        return Response(result, status=status.HTTP_200_OK)
    
    except AIServiceException as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Triage error: {e}")
        return Response(
            {'error': 'Triage failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@requires_role('doctor', 'super_admin')
def find_similar_patients(request: Request, patient_id: str) -> Response:
    """
    Find similar patient cases for treatment benchmarking.
    
    Query parameters:
    - k: int (default=10) - Number of similar patients to return
    
    Returns:
        200: List of similar patients with treatment outcomes
        400: Bad request
        403: Forbidden (must be doctor)
        404: Patient not found
    """
    try:
        k = _query_param_int(request, "k", 10)
        k = min(k, 50)  # Cap at 50
        
        service = SimilaritySearchService(request.user)
        result = service.find_similar_patients(patient_id, k=k)
        
        # Audit
        _model(AuditLog).log_action(
            user=request.user,
            action='AI_SIMILARITY_SEARCH',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            request=request,
        )
        
        logger.info(f"Similarity search for patient {patient_id}")
        return Response(result, status=status.HTTP_200_OK)
    
    except AIServiceException as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError:
        return Response({'error': 'Invalid k parameter'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Similarity search error: {e}")
        return Response(
            {'error': 'Similarity search failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@requires_role('doctor', 'hospital_admin', 'super_admin')
def recommend_referral_hospital(request: Request, patient_id: str) -> Response:
    """
    Recommend best hospital for inter-hospital referral.
    
    Request body:
        {
            "required_specialty": "string (optional)"
        }
    
    Returns:
        200: Top 3 recommended hospitals with reasons
        400: Bad request
        403: Forbidden
        404: Patient not found
    """
    try:
        body: Any = request.data
        required_specialty = _as_str(body.get("required_specialty", ""), "")

        service = ReferralRecommendationService(request.user)
        result = service.recommend_referral_hospital(patient_id, required_specialty=required_specialty)
        
        # Audit
        _model(AuditLog).log_action(
            user=request.user,
            action='AI_REFERRAL_RECOMMENDATION',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            request=request,
            extra_data={'specialty': required_specialty}
        )
        
        logger.info(f"Referral recommendation for patient {patient_id}")
        return Response(result, status=status.HTTP_200_OK)
    
    except AIServiceException as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Referral recommendation error: {e}")
        return Response(
            {'error': 'Referral recommendation failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@requires_role('doctor', 'nurse', 'super_admin')
def get_analysis_history(request: Request, patient_id: str) -> Response:
    """
    Get AI analysis history for patient.
    
    Query parameters:
    - limit: int (default=10) - Number of results
    - offset: int (default=0) - Pagination offset
    
    Returns:
        200: List of past AI analyses
        400: Bad request
        403: Forbidden
        404: Patient not found
    """
    try:
        patient_qs = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id)
        if not patient_qs.exists():
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        hospital = get_request_hospital(request)
        limit = min(_query_param_int(request, "limit", 10), 50)
        offset = _query_param_int(request, "offset", 0)

        qs = _model(AIAnalysis).objects.filter(patient_id=patient_id).order_by('-created_at')
        if hospital:
            qs = qs.filter(hospital=hospital)
        total = qs.count()
        analyses = list(qs[offset:offset + limit].values(
            'id', 'analysis_type', 'overall_confidence', 'agents_executed',
            'clinical_summary', 'recommended_actions', 'alerts', 'chief_complaint', 'created_at'
        ))
        for a in analyses:
            a['created_at'] = a['created_at'].isoformat() if a.get('created_at') else None

        _model(AuditLog).log_action(
            user=request.user,
            action='AI_HISTORY_VIEW',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=hospital,
            request=request,
        )

        return Response({
            'patient_id': patient_id,
            'analyses': analyses,
            'total': total,
            'limit': limit,
            'offset': offset,
        }, status=status.HTTP_200_OK)

    except ValueError:
        return Response({'error': 'Invalid limit or offset'}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Analysis history error: {e}")
        return Response(
            {'error': 'Failed to fetch history'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
