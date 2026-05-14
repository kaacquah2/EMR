import logging
from django.utils import timezone
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from api.models import ModelVersion
from api.serializers import ModelVersionSerializer
from api.tasks.ai_tasks import retrain_model_task

logger = logging.getLogger(__name__)

class IsSuperAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user and request.user.is_superuser

class AIModelManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for super_admins to manage AI model versions and retraining.
    """
    queryset = ModelVersion.objects.all().order_by('-trained_at')
    serializer_class = ModelVersionSerializer
    permission_classes = [permissions.IsAuthenticated, IsSuperAdmin]

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """
        Approves a model version for clinical use.
        """
        version = self.get_object()
        notes = request.data.get('notes')
        
        if not notes:
            return Response({"error": "Approval notes are required."}, status=status.HTTP_400_BAD_REQUEST)
            
        version.clinical_use_approved = True
        version.is_production = True
        version.approved_by = request.user
        version.approved_at = timezone.now()
        version.approval_notes = notes
        version.save()
        
        # Demote others
        ModelVersion.objects.filter(
            model_type=version.model_type,
            is_production=True
        ).exclude(id=version.id).update(is_production=False)
        
        return Response({"status": "approved", "version_tag": version.version_tag})

    @action(detail=False, methods=['post'])
    def retrain(self, request):
        """
        Triggers an async retraining task.
        """
        model_type = request.data.get('model_type')
        data_source = request.data.get('data_source', 'synthetic')
        hospital_id = request.data.get('hospital_id')
        
        if not model_type:
            return Response({"error": "model_type is required."}, status=status.HTTP_400_BAD_REQUEST)
            
        task = retrain_model_task.delay(
            model_type=model_type,
            data_source=data_source,
            hospital_id=hospital_id,
            user_id=request.user.id
        )
        
        return Response({
            "task_id": task.id,
            "status": "training_started"
        })

    @action(detail=False, methods=['get'], url_path='retrain/(?P<task_id>[^/.]+)/status')
    def retrain_status(self, request, task_id=None):
        """
        Polls the status of a retraining task.
        """
        from celery.result import AsyncResult
        res = AsyncResult(task_id)
        
        return Response({
            "task_id": task_id,
            "status": res.status,
            "result": res.result if res.ready() else None,
            "progress": res.info.get('progress') if isinstance(res.info, dict) else None
        })

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsSuperAdmin])
def ai_deployment_status(request):
    """Placeholder for global AI deployment status."""
    return Response({"status": "active", "global_version": "1.0.0"})

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsSuperAdmin])
def approve_ai_deployment(request):
    """Placeholder for global AI deployment approval."""
    return Response({"status": "approved"})

@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated, IsSuperAdmin])
def revoke_ai_deployment(request, approval_id=None):
    """Placeholder for revoking global AI deployment."""
    return Response({"status": "revoked"})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsSuperAdmin])
def ai_recommendation_audit_trail(request, patient_id=None):
    """Placeholder for AI recommendation audit trail."""
    return Response({"patient_id": patient_id, "history": []})

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated, IsSuperAdmin])
def ai_performance_metrics(request):
    """Placeholder for global AI performance metrics."""
    return Response({"f1": 0.92, "accuracy": 0.94})
