"""
AI Admin Management Views.

Hospital admins manage AI deployment, approvals, and performance monitoring:
- View deployment status per hospital
- Approve/revoke model deployments
- Monitor AI recommendation metrics
- View audit trail of AI decisions
"""

import logging
from datetime import timedelta
from typing import Optional

from django.utils import timezone
from django.db.models import Count, Q, Avg

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request

from api.decorators import requires_role
from api.models import AIAnalysis
from api.models_deployment_log import AIDeploymentLog
from core.models import Hospital, AuditLog
from api.utils import get_effective_hospital, get_request_hospital

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@requires_role('hospital_admin', 'super_admin')
def ai_deployment_status(request: Request) -> Response:
    """
    Get AI deployment status for hospital.
    
    Hospital admins see their hospital only.
    Super admins can filter by hospital_id query param.
    
    Response:
    {
        "hospital": {...},
        "deployed": true,
        "model_version": "1.0.0-hybrid",
        "confidence_threshold": 0.80,
        "deployed_at": "2026-04-20T10:00:00Z",
        "validation_metrics": {...},
        "recent_analyses": [{...}]
    }
    """
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response(
            {"detail": "No hospital context"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get latest deployment
    deployment = AIDeploymentLog.get_latest_for_hospital(hospital)
    
    # Get approval record
    approval = None
    if deployment:
        try:
            approval = AIDeploymentApproval.objects.filter(
                hospital=hospital,
                model_version=deployment.model_version,
                enabled=True
            ).latest('approved_at')
        except AIDeploymentApproval.DoesNotExist:
            pass
    
    # Get recent analyses for hospital
    recent_analyses = AIAnalysis.objects.filter(
        hospital=hospital
    ).order_by('-created_at')[:10].values(
        'id', 'analysis_type', 'overall_confidence', 'created_at'
    )
    
    response_data = {
        "hospital": {
            "id": hospital.id,
            "name": hospital.name,
            "code": hospital.code
        },
        "deployed": deployment.enabled if deployment else False,
        "model_version": deployment.model_version if deployment else None,
        "confidence_threshold": float(approval.confidence_threshold) if approval else 0.80,
        "deployed_at": deployment.enabled_at.isoformat() if deployment else None,
        "validation_metrics": deployment.validation_metrics if deployment else {},
        "recent_analyses_count": len(recent_analyses),
        "recent_analyses": list(recent_analyses)
    }
    
    return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requires_role('hospital_admin')
def approve_ai_deployment(request: Request) -> Response:
    """
    Hospital admin approves AI model for clinical use.
    
    Request body:
    {
        "model_version": "1.0.0-hybrid",
        "confidence_threshold": 0.80,
        "notes": "Approved after validation review"
    }
    
    Returns:
    {
        "approval_id": "...",
        "hospital": "...",
        "model_version": "...",
        "status": "approved",
        "approved_at": "..."
    }
    """
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response(
            {"detail": "No hospital context"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    model_version = request.data.get('model_version')
    confidence_threshold = request.data.get('confidence_threshold', 0.80)
    notes = request.data.get('notes', '')
    
    if not model_version:
        return Response(
            {"detail": "model_version required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate threshold
    try:
        threshold_float = float(confidence_threshold)
        if not (0.75 <= threshold_float <= 1.0):
            return Response(
                {"detail": "confidence_threshold must be 0.75-1.0"},
                status=status.HTTP_400_BAD_REQUEST
            )
    except (ValueError, TypeError):
        return Response(
            {"detail": "confidence_threshold must be a number"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create or update approval
    approval, created = AIDeploymentApproval.objects.update_or_create(
        hospital=hospital,
        model_version=model_version,
        defaults={
            'approved_by': request.user,
            'confidence_threshold': threshold_float,
            'enabled': True,
            'revoked_at': None,
            'revoked_by': None,
            'notes': notes
        }
    )
    
    # Log to audit trail
    try:
        AuditLog.log_action(
            user=request.user,
            action='AI_APPROVAL_GRANT',
            resource_type='AIDeploymentApproval',
            resource_id=str(approval.id),
            metadata={
                'hospital_id': hospital.id,
                'model_version': model_version,
                'confidence_threshold': threshold_float,
                'notes': notes
            }
        )
    except Exception as e:
        logger.error(f"Failed to log AI approval: {e}")
    
    return Response(
        {
            "approval_id": str(approval.id),
            "hospital": hospital.name,
            "model_version": model_version,
            "status": "approved",
            "confidence_threshold": threshold_float,
            "approved_at": approval.approved_at.isoformat(),
            "created": created
        },
        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
    )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@requires_role('hospital_admin')
def revoke_ai_deployment(request: Request, approval_id: str) -> Response:
    """
    Hospital admin revokes AI deployment approval.
    
    Response:
    {
        "status": "revoked",
        "approval_id": "...",
        "revoked_at": "..."
    }
    """
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response(
            {"detail": "No hospital context"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        approval = AIDeploymentApproval.objects.get(
            id=approval_id,
            hospital=hospital
        )
    except AIDeploymentApproval.DoesNotExist:
        return Response(
            {"detail": "Approval not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Revoke
    approval.enabled = False
    approval.revoked_at = timezone.now()
    approval.revoked_by = request.user
    approval.save()
    
    # Log to audit trail
    try:
        AuditLog.log_action(
            user=request.user,
            action='AI_APPROVAL_REVOKE',
            resource_type='AIDeploymentApproval',
            resource_id=str(approval.id),
            metadata={
                'hospital_id': hospital.id,
                'model_version': approval.model_version
            }
        )
    except Exception as e:
        logger.error(f"Failed to log AI approval revocation: {e}")
    
    return Response({
        "status": "revoked",
        "approval_id": str(approval.id),
        "revoked_at": approval.revoked_at.isoformat()
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@requires_role('hospital_admin', 'super_admin')
def ai_recommendation_audit_trail(request: Request, patient_id: str) -> Response:
    """
    Get audit trail of all AI recommendations for a patient.
    
    Hospital admins see only their hospital.
    Super admins see all.
    
    Response:
    {
        "patient_id": "...",
        "recommendations": [
            {
                "analysis_type": "risk_prediction",
                "model_version": "1.0.0",
                "confidence": 0.85,
                "created_at": "...",
                "user_email": "..."
            }
        ]
    }
    """
    hospital = get_effective_hospital(request)
    
    # Get all analyses for patient
    query = AIAnalysis.objects.filter(patient_id=patient_id)
    
    if hospital:
        query = query.filter(hospital=hospital)
    
    analyses = query.order_by('-created_at').values(
        'id',
        'analysis_type',
        'overall_confidence',
        'created_at',
        'performed_by__email',
        'performed_by__first_name',
        'performed_by__last_name'
    )
    
    recommendations = []
    for analysis in analyses:
        recommendations.append({
            "analysis_id": str(analysis['id']),
            "analysis_type": analysis['analysis_type'],
            "confidence": analysis['overall_confidence'],
            "created_at": analysis['created_at'].isoformat() if analysis['created_at'] else None,
            "performed_by": analysis['performed_by__email'] or 'system'
        })
    
    return Response({
        "patient_id": patient_id,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
@requires_role('hospital_admin', 'super_admin')
def ai_performance_metrics(request: Request) -> Response:
    """
    Get AI performance metrics for hospital.
    
    Returns:
    {
        "hospital": "...",
        "analyses_count": 100,
        "avg_confidence": 0.82,
        "confidence_distribution": {...},
        "analysis_type_distribution": {...},
        "recommendations_by_hour": [...]
    }
    """
    hospital = get_effective_hospital(request)
    if not hospital:
        return Response(
            {"detail": "No hospital context"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Get analyses in last 30 days
    thirty_days_ago = timezone.now() - timedelta(days=30)
    
    analyses = AIAnalysis.objects.filter(
        hospital=hospital,
        created_at__gte=thirty_days_ago
    )
    
    # Aggregate metrics
    total_count = analyses.count()
    avg_confidence = analyses.aggregate(
        avg=Avg('overall_confidence')
    )['avg'] or 0
    
    # Distribution by analysis type
    type_distribution = analyses.values('analysis_type').annotate(
        count=Count('id')
    )
    
    # Confidence ranges
    confidence_ranges = {
        '0.0-0.5': analyses.filter(overall_confidence__lt=0.5).count(),
        '0.5-0.75': analyses.filter(
            overall_confidence__gte=0.5,
            overall_confidence__lt=0.75
        ).count(),
        '0.75-0.9': analyses.filter(
            overall_confidence__gte=0.75,
            overall_confidence__lt=0.9
        ).count(),
        '0.9+': analyses.filter(overall_confidence__gte=0.9).count()
    }
    
    return Response({
        "hospital": hospital.name,
        "period_days": 30,
        "analyses_count": total_count,
        "avg_confidence": round(float(avg_confidence), 4),
        "confidence_distribution": confidence_ranges,
        "analysis_type_distribution": list(type_distribution),
        "timestamp": timezone.now().isoformat()
    })
