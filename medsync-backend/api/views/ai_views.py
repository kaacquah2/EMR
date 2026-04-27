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
from rest_framework.decorators import api_view, throttle_classes
from rest_framework.response import Response
from rest_framework.request import Request

from api.decorators import requires_role
from api.ai.governance import ai_governance_clinical
from api.rate_limiting import AIEndpointThrottle, AIHospitalThrottle
from django.conf import settings
from api.utils import get_patient_queryset, get_effective_hospital, get_request_hospital
from api.models import AIAnalysis
from api.serializers import AIAnalysisJobSerializer
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
    except Exception as e:
        logger.warning(f"Failed to count AI analyses in last 24h: {str(e)}")

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
@ai_governance_clinical('status', model_version='1.0.0-placeholder')
def ai_status(request: Request) -> Response:
    """Lightweight AI integration status for the Super Admin dashboard."""
    return Response(build_ai_status_payload())

@api_view(['POST'])
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'nurse', 'hospital_admin', 'super_admin')
@ai_governance_clinical('comprehensive_analysis', model_version='1.0.0-placeholder')
def analyze_patient_comprehensive(request: Request, patient_id: str) -> Response:
    """
    Run comprehensive multi-agent analysis on patient.

    ⚠️  DEPRECATION: Synchronous analysis is deprecated. Please use POST /api/v1/ai/async-analysis instead.
    """
    return Response({
        "message": "Synchronous comprehensive analysis is deprecated due to resource intensity. Please use the async endpoint.",
        "async_endpoint": "/api/v1/ai/async-analysis/",
        "patient_id": patient_id
    }, status=status.HTTP_400_BAD_REQUEST)

    # Legacy code (unreachable)
    try:
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
                .order_by("-encounter_date")
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
        AuditLog.objects.create(
            user=request.user,
            action='AI_ANALYSIS',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'nurse', 'super_admin')
@ai_governance_clinical('risk_prediction', model_version='1.0.0-placeholder')
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
        AuditLog.objects.create(
            user=request.user,
            action='AI_RISK_PREDICTION',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'super_admin')
@ai_governance_clinical('clinical_decision_support', model_version='1.0.0-placeholder')
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
        AuditLog.objects.create(
            user=request.user,
            action='AI_CDS',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('nurse', 'doctor', 'super_admin')
@ai_governance_clinical('triage', model_version='1.0.0-placeholder')
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
        AuditLog.objects.create(
            user=request.user,
            action='AI_TRIAGE',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'super_admin')
@ai_governance_clinical('similarity_search', model_version='1.0.0-placeholder')
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
        AuditLog.objects.create(
            user=request.user,
            action='AI_SIMILARITY_SEARCH',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'hospital_admin', 'super_admin')
@ai_governance_clinical('referral_recommendation', model_version='1.0.0-placeholder')
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
        AuditLog.objects.create(
            user=request.user,
            action='AI_REFERRAL_RECOMMENDATION',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=service.effective_hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'nurse', 'super_admin')
@ai_governance_clinical('analysis_history', model_version='1.0.0-placeholder')
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

        AuditLog.objects.create(
            user=request.user,
            action='AI_HISTORY_VIEW',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
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


@api_view(['POST'])
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'hospital_admin', 'super_admin')
def start_async_analysis(request: Request, patient_id: str) -> Response:
    """
    Start an async AI analysis job.

    Returns 202 Accepted with job_id for polling.
    Frontend polls GET /ai/async-analysis/:job_id to track progress.

    Request body:
    {
        "analysis_type": "comprehensive",  # or risk_prediction, clinical_decision_support, etc.
        "include_similarity": true,
        "include_referral": true
    }

    Returns:
        202: Job created with job_id and polling URL
        400: Bad request
        403: Forbidden
        404: Patient not found
    """
    try:
        from api.models import AIAnalysisJob
        from api.tasks.ai_tasks import comprehensive_analysis_task, risk_prediction_task

        # Verify patient access
        patient_qs = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id)
        if not patient_qs.exists():
            return Response({'error': 'Patient not found'}, status=status.HTTP_404_NOT_FOUND)

        patient = patient_qs.first()
        hospital = patient.registered_at
        analysis_type = request.data.get('analysis_type', 'comprehensive')

        # Validate analysis type
        valid_types = [
            'comprehensive',
            'risk_prediction',
            'clinical_decision_support',
            'triage',
            'similarity_search',
            'referral',
            # NEW TYPES
            'differentials',
            'encounter_summary',
            'discharge_summary',
            'readmission_risk',
            'icd10_suggest',
            'ward_forecast',
        ]
        if analysis_type not in valid_types:
            return Response({'error': f'Invalid analysis type. Must be one of: {valid_types}'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Create job record
        job = AIAnalysisJob.objects.create(
            patient=patient,
            hospital=hospital,
            created_by=request.user,
            analysis_type=analysis_type
        )
        
        # Set initial step based on analysis type
        if analysis_type == 'differentials':
            # Differential diagnosis from chief complaint + HPI
            job.current_step = 'Analyzing symptoms for differential diagnoses'
        elif analysis_type == 'encounter_summary':
            encounter_id = request.data.get('encounter_id')
            if not encounter_id:
                job.delete()
                return Response({'error': 'encounter_id required'}, status=status.HTTP_400_BAD_REQUEST)
            job.current_step = 'Generating encounter summary'
        elif analysis_type == 'discharge_summary':
            encounter_id = request.data.get('encounter_id')
            if not encounter_id:
                job.delete()
                return Response({'error': 'encounter_id required'}, status=status.HTTP_400_BAD_REQUEST)
            job.current_step = 'Drafting discharge summary'
        elif analysis_type == 'readmission_risk':
            job.current_step = 'Calculating readmission risk score'
        elif analysis_type == 'icd10_suggest':
            free_text = request.data.get('free_text', '')
            if not free_text:
                job.delete()
                return Response({'error': 'free_text required'}, status=status.HTTP_400_BAD_REQUEST)
            job.current_step = 'Extracting ICD-10 codes from text'
        elif analysis_type == 'ward_forecast':
            job.current_step = 'Predicting ward bed pressure'
        
        job.save()

        # Queue the appropriate task
        if analysis_type == 'comprehensive':
            task = comprehensive_analysis_task.delay(
                patient_id=str(patient_id),
                job_id=str(job.id),
                user_id=str(request.user.id),
                analysis_type=analysis_type
            )
        elif analysis_type == 'risk_prediction':
            task = risk_prediction_task.delay(
                patient_id=str(patient_id),
                job_id=str(job.id),
                user_id=str(request.user.id)
            )
        else:
            # For other types, just queue comprehensive for now
            task = comprehensive_analysis_task.delay(
                patient_id=str(patient_id),
                job_id=str(job.id),
                user_id=str(request.user.id),
                analysis_type=analysis_type
            )

        # Store Celery task ID
        job.celery_task_id = task.id
        job.save()

        # Log action
        AuditLog.objects.create(
            user=request.user,
            action='AI_ANALYSIS_START_ASYNC',
            resource_type='Patient',
            resource_id=patient_id,
            hospital=hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            extra_data={'job_id': str(job.id), 'analysis_type': analysis_type}
        )

        return Response({
            'job_id': str(job.id),
            'patient_id': str(patient_id),
            'analysis_type': analysis_type,
            'status': 'pending',
            'polling_url': f'/api/v1/ai/async-analysis/{job.id}',
            'message': 'Analysis job queued. Poll the URL above to track progress.'
        }, status=status.HTTP_202_ACCEPTED)

    except ValueError as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as e:
        logger.error(f"Error starting async analysis: {e}")
        return Response(
            {'error': 'Failed to start analysis'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@requires_role('doctor', 'nurse', 'hospital_admin', 'super_admin')
@ai_governance_clinical('async_analysis_status', model_version='1.0.0-placeholder')
def get_async_analysis_status(request: Request, job_id: str) -> Response:
    """
    Poll the status of an async AI analysis job.

    Returns current status, progress percentage, and results when complete.

    Returns:
        200: Job status with progress
        404: Job not found
    """
    try:
        from api.models import AIAnalysisJob

        # Find job
        try:
            job = AIAnalysisJob.objects.get(id=job_id)
        except AIAnalysisJob.DoesNotExist:
            return Response({'error': 'Job not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check access (user must have access to patient)
        patient_qs = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=job.patient_id)
        if not patient_qs.exists():
            return Response({'error': 'Access denied'}, status=status.HTTP_403_FORBIDDEN)

        # Serialize and return job status
        serializer = AIAnalysisJobSerializer(job)
        return Response(serializer.data, status=status.HTTP_200_OK)

    except Exception as e:
        logger.error(f"Error getting async analysis status: {e}")
        return Response(
            {'error': 'Failed to get status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'hospital_admin', 'super_admin')
@ai_governance_clinical('antibiotic_guidance', model_version='1.0.0-placeholder')
def antibiotic_guidance(request: Request) -> Response:
    """
    GET /ai/antibiotic-guidance?drug=&diagnosis_icd10=&severity=
    
    Returns antibiotic guidance based on local resistance data.
    """
    drug = request.query_params.get('drug', '')
    diagnosis = request.query_params.get('diagnosis_icd10', '')
    severity = request.query_params.get('severity', 'moderate')
    
    if not drug or not diagnosis:
        return Response(
            {'error': 'drug and diagnosis_icd10 parameters required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Mock response - would integrate with resistance database
    guidance = {
        'drug': drug,
        'diagnosis': diagnosis,
        'severity': severity,
        'recommended': True,
        'duration_days': 7,
        'notes': 'Standard first-line therapy for this indication.',
        'local_resistance_rate': 0.12,  # 12%
        'de_escalation_guidance': 'Consider stepping down to oral therapy after 48h if improving.',
        'alternatives': [
            {'drug': 'Amoxicillin', 'reason': 'Lower spectrum if susceptible'},
        ],
        'warnings': [],
    }
    
    # Audit
    AuditLog.objects.create(
        user=request.user,
        action='AI_ANTIBIOTIC_GUIDANCE',
        resource_type='Drug',
        resource_id=drug,
        hospital=getattr(request.user, 'hospital', None),
        ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
    )
    
    return Response(guidance)


@api_view(['GET'])
@throttle_classes([AIEndpointThrottle, AIHospitalThrottle])
@requires_role('doctor', 'nurse', 'receptionist', 'hospital_admin', 'super_admin')
@ai_governance_clinical('no_show_risk', model_version='1.0.0-placeholder')
def no_show_risk(request: Request) -> Response:
    """
    GET /ai/no-show-risk?appointment_id=
    
    Returns no-show probability for an appointment.
    """
    appointment_id = request.query_params.get('appointment_id')
    
    if not appointment_id:
        return Response(
            {'error': 'appointment_id parameter required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Mock response - would use ML model based on patient history
    risk = {
        'appointment_id': appointment_id,
        'no_show_probability': 0.15,  # 15%
        'risk_level': 'low',  # low/medium/high
        'factors': [
            {'factor': 'previous_no_shows', 'impact': 'neutral', 'value': 0},
            {'factor': 'appointment_lead_time', 'impact': 'positive', 'value': '3 days'},
            {'factor': 'time_of_day', 'impact': 'neutral', 'value': 'morning'},
        ],
        'recommendation': 'Standard reminder 24h before appointment.',
    }
    
    return Response(risk)
