"""
Hospital Admin AI Management Endpoints.

Provides hospital admins with:
- POST /admin/ai/enable - Enable clinical AI for their hospital
- GET /admin/ai/status - Check deployment status
- GET /admin/ai/history - View deployment history
- PUT /admin/ai/disable - Disable clinical AI (emergency)
"""

import logging
from datetime import timedelta

from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework.request import Request

from core.models import Hospital, AuditLog
from api.models import AIDeploymentLog
from api.utils import get_request_hospital
from api.decorators import requires_role

logger = logging.getLogger(__name__)


@api_view(['POST'])
@requires_role('hospital_admin', 'super_admin')
def enable_clinical_ai(request: Request) -> Response:
    """
    Enable clinical AI features for this hospital.

    Hospital admin must provide:
    - model_version: Version of model being deployed (e.g., "1.0.0-mimic-iv")
    - validation_metrics: JSON dict with AUC-ROC, sensitivity, specificity
    - approval_notes: Notes explaining why AI is being approved

    Metrics must meet minimum thresholds:
    - AUC-ROC >= 0.80
    - Sensitivity >= 0.75
    - Specificity >= 0.85

    Example request:
    POST /admin/ai/enable
    {
        "model_version": "1.0.0-mimic-iv",
        "validation_metrics": {
            "overall_auc_roc": 0.85,
            "overall_sensitivity": 0.78,
            "overall_specificity": 0.88,
            "diseases": {
                "malaria": {"auc_roc": 0.92, "sensitivity": 0.85, "specificity": 0.95},
                "hypertension": {"auc_roc": 0.78, "sensitivity": 0.70, "specificity": 0.85}
            },
            "test_data_size": 1000,
            "test_data_source": "MIMIC-IV",
            "training_date": "2026-04-20"
        },
        "approval_notes": "Validated on MIMIC-IV ICU data. Meets all thresholds. Approved for clinical use."
    }
    """
    try:
        hospital = get_request_hospital(request)
        if not hospital:
            return Response(
                {'error': 'Hospital context not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Extract request data
        model_version = request.data.get('model_version', '')
        validation_metrics = request.data.get('validation_metrics', {})
        approval_notes = request.data.get('approval_notes', '')

        # Validate required fields
        if not model_version:
            return Response(
                {'error': 'model_version is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if not validation_metrics:
            return Response(
                {'error': 'validation_metrics is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create deployment log
        deployment = AIDeploymentLog.objects.create(
            hospital=hospital,
            enabled_by=request.user,
            enabled=True,
            model_version=model_version,
            validation_metrics=validation_metrics,
            approval_notes=approval_notes
        )

        # Validate metrics
        is_valid, message = deployment.validate_metrics()
        if not is_valid:
            # Disable if metrics don't meet thresholds
            deployment.enabled = False
            deployment.save()
            return Response(
                {
                    'error': 'Validation metrics do not meet clinical thresholds',
                    'message': message,
                    'required': {
                        'auc_roc': '>= 0.80',
                        'sensitivity': '>= 0.75',
                        'specificity': '>= 0.85'
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Audit log
        AuditLog.objects.create(
            user=request.user,
            action='AI_DEPLOYMENT_ENABLED',
            resource_type='Hospital',
            resource_id=hospital.id,
            hospital=hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            extra_data={
                'model_version': model_version,
                'metrics': validation_metrics,
            }
        )

        logger.info(f"Clinical AI enabled for {hospital.name} by {request.user.email} (model: {model_version})")

        return Response(
            {
                'message': f'Clinical AI enabled for {hospital.name}',
                'deployment': {
                    'id': str(deployment.id),
                    'hospital': hospital.name,
                    'enabled': deployment.enabled,
                    'model_version': deployment.model_version,
                    'enabled_at': deployment.enabled_at.isoformat(),
                    'enabled_by': request.user.email
                }
            },
            status=status.HTTP_201_CREATED
        )

    except Exception as e:
        logger.error(f"Error enabling clinical AI: {e}")
        return Response(
            {'error': 'Failed to enable clinical AI'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@requires_role('hospital_admin', 'super_admin', 'doctor', 'nurse')
def get_ai_deployment_status(request: Request) -> Response:
    """
    Get current AI deployment status for this hospital.

    Returns:
    - enabled: Is clinical AI currently enabled?
    - model_version: What version of model is deployed?
    - enabled_at: When was it enabled?
    - metrics: Validation metrics for deployed model
    - approval_notes: Notes on approval
    """
    try:
        hospital = get_request_hospital(request)
        if not hospital:
            return Response(
                {'error': 'Hospital context not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get latest deployment
        deployment = AIDeploymentLog.get_latest_for_hospital(hospital)

        if not deployment:
            return Response(
                {
                    'message': 'No AI deployment configured for this hospital',
                    'enabled': False,
                    'hospital': hospital.name
                },
                status=status.HTTP_200_OK
            )

        return Response(
            {
                'enabled': deployment.enabled,
                'hospital': hospital.name,
                'model_version': deployment.model_version,
                'enabled_at': deployment.enabled_at.isoformat(),
                'disabled_at': deployment.disabled_at.isoformat() if deployment.disabled_at else None,
                'enabled_by': deployment.enabled_by.email,
                'validation_metrics': deployment.validation_metrics,
                'approval_notes': deployment.approval_notes,
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error fetching AI deployment status: {e}")
        return Response(
            {'error': 'Failed to fetch deployment status'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@requires_role('hospital_admin', 'super_admin')
def get_ai_deployment_history(request: Request) -> Response:
    """
    Get deployment history (past 30 days) for this hospital.

    Returns a list of past deployments with approval metadata.
    """
    try:
        hospital = get_request_hospital(request)
        if not hospital:
            return Response(
                {'error': 'Hospital context not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get past 30 days of deployments
        thirty_days_ago = timezone.now() - timedelta(days=30)
        deployments = AIDeploymentLog.objects.filter(
            hospital=hospital,
            enabled_at__gte=thirty_days_ago
        ).order_by('-enabled_at')

        history = [
            {
                'id': str(d.id),
                'model_version': d.model_version,
                'enabled': d.enabled,
                'enabled_at': d.enabled_at.isoformat(),
                'disabled_at': d.disabled_at.isoformat() if d.disabled_at else None,
                'enabled_by': d.enabled_by.email,
                'approval_notes': d.approval_notes[:200],  # Truncate for list view
                'metrics_valid': d.validate_metrics()[0]
            }
            for d in deployments
        ]

        return Response(
            {
                'hospital': hospital.name,
                'deployment_count': len(history),
                'history': history
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error fetching AI deployment history: {e}")
        return Response(
            {'error': 'Failed to fetch deployment history'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@requires_role('hospital_admin', 'super_admin')
def disable_clinical_ai(request: Request) -> Response:
    """
    Disable clinical AI features for this hospital (emergency).

    Should only be used if models are misbehaving or need revalidation.
    """
    try:
        hospital = get_request_hospital(request)
        if not hospital:
            return Response(
                {'error': 'Hospital context not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Get latest deployment
        deployment = AIDeploymentLog.get_latest_for_hospital(hospital)

        if not deployment or not deployment.enabled:
            return Response(
                {
                    'message': 'Clinical AI is not currently enabled',
                    'hospital': hospital.name
                },
                status=status.HTTP_200_OK
            )

        # Disable
        deployment.enabled = False
        deployment.disabled_at = timezone.now()
        deployment.save()

        # Audit log
        reason = request.data.get('reason', 'No reason provided')
        AuditLog.objects.create(
            user=request.user,
            action='AI_DEPLOYMENT_DISABLED',
            resource_type='Hospital',
            resource_id=hospital.id,
            hospital=hospital,
            ip_address=request.META.get('REMOTE_ADDR', '127.0.0.1'),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            extra_data={
                'model_version': deployment.model_version,
                'reason': reason,
            }
        )

        logger.warning(f"Clinical AI disabled for {hospital.name} by {request.user.email}. Reason: {reason}")

        return Response(
            {
                'message': f'Clinical AI disabled for {hospital.name}',
                'disabled_at': deployment.disabled_at.isoformat()
            },
            status=status.HTTP_200_OK
        )

    except Exception as e:
        logger.error(f"Error disabling clinical AI: {e}")
        return Response(
            {'error': 'Failed to disable clinical AI'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
