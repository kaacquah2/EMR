"""
Clinical Decision Support (CDS) API endpoints.

GET /encounters/<id>/cds-alerts/ - Get alerts for an encounter
POST /cds-alerts/<id>/acknowledge/ - Acknowledge an alert
"""

import logging
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from records.models import Encounter
from api.models import CdsAlert
from api.audit_logging import audit_log_extended

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def encounter_cds_alerts(request, encounter_id):
    """
    Get all CDS alerts for an encounter.
    
    Returns unacknowledged alerts with severity ordering (critical > warning > info).
    
    Query params:
    - acknowledged: 'true'/'false' to filter by acknowledgment status (default: unacknowledged)
    """
    try:
        encounter = Encounter.objects.get(id=encounter_id)
        
        # Permission check: user must be able to access this patient
        from api.permissions_helpers import can_access_patient
        
        if not can_access_patient(request.user, encounter.patient):
            return Response(
                {'error': 'Not authorized to access this encounter'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get alerts
        acknowledged_param = request.query_params.get('acknowledged', 'false').lower()
        
        alerts_qs = CdsAlert.objects.filter(encounter=encounter).order_by('-severity', '-created_at')
        
        if acknowledged_param == 'true':
            alerts_qs = alerts_qs.filter(acknowledged=True)
        elif acknowledged_param == 'false':
            alerts_qs = alerts_qs.filter(acknowledged=False)
        # else: include all
        
        # Serialize
        alerts_data = [
            {
                'id': str(alert.id),
                'rule_id': str(alert.rule.id),
                'rule_name': alert.rule.name,
                'encounter_id': str(alert.encounter.id),
                'severity': alert.severity,
                'message': alert.message,
                'context_data': alert.context_data,
                'acknowledged': alert.acknowledged,
                'acknowledged_by': alert.acknowledged_by.full_name if alert.acknowledged_by else None,
                'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                'acknowledgment_notes': alert.acknowledgment_notes,
                'created_at': alert.created_at.isoformat(),
            }
            for alert in alerts_qs
        ]
        
        # Audit log
        audit_log_extended(
            user=request.user,
            action='VIEW',
            resource_type='CdsAlert',
            resource_id=f'encounter:{encounter_id}',
            hospital=encounter.hospital,
            extra_data={'alert_count': len(alerts_data)}
        )
        
        return Response({
            'count': len(alerts_data),
            'alerts': alerts_data,
            'encounter_id': str(encounter.id),
        }, status=status.HTTP_200_OK)
    
    except Encounter.DoesNotExist:
        return Response(
            {'error': 'Encounter not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching CDS alerts: {e}", exc_info=True)
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def acknowledge_cds_alert(request, alert_id):
    """
    Acknowledge a CDS alert.
    
    Mark alert as acknowledged and optionally store doctor's notes.
    
    Request body:
    {
        "notes": "Doctor's acknowledgment notes (optional)"
    }
    """
    try:
        alert = get_object_or_404(CdsAlert, id=alert_id)
        
        # Permission check: user must be able to access the encounter's patient
        from api.permissions_helpers import can_access_patient
        
        if not can_access_patient(request.user, alert.encounter.patient):
            return Response(
                {'error': 'Not authorized to access this alert'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get notes from request
        notes = request.data.get('notes', '')
        
        # Mark as acknowledged
        alert.acknowledge(user=request.user, notes=notes)
        
        # Audit log
        audit_log_extended(
            user=request.user,
            action='ACKNOWLEDGE_CDS_ALERT',
            resource_type='CdsAlert',
            resource_id=str(alert.id),
            hospital=alert.encounter.hospital,
            extra_data={
                'rule_id': str(alert.rule.id),
                'severity': alert.severity,
                'notes': notes[:100] if notes else '',  # Log only first 100 chars
            }
        )
        
        # Return updated alert
        response_data = {
            'id': str(alert.id),
            'rule_id': str(alert.rule.id),
            'rule_name': alert.rule.name,
            'encounter_id': str(alert.encounter.id),
            'severity': alert.severity,
            'message': alert.message,
            'acknowledged': alert.acknowledged,
            'acknowledged_by': alert.acknowledged_by.full_name if alert.acknowledged_by else None,
            'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            'acknowledgment_notes': alert.acknowledgment_notes,
            'created_at': alert.created_at.isoformat(),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except CdsAlert.DoesNotExist:
        return Response(
            {'error': 'Alert not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error acknowledging CDS alert: {e}", exc_info=True)
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def cds_alert_detail(request, alert_id):
    """
    Get details of a specific CDS alert.
    """
    try:
        alert = get_object_or_404(CdsAlert, id=alert_id)
        
        # Permission check
        from api.permissions_helpers import can_access_patient
        
        if not can_access_patient(request.user, alert.encounter.patient):
            return Response(
                {'error': 'Not authorized to access this alert'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Serialize
        response_data = {
            'id': str(alert.id),
            'rule_id': str(alert.rule.id),
            'rule_name': alert.rule.name,
            'rule_type': alert.rule.rule_type,
            'encounter_id': str(alert.encounter.id),
            'patient_id': str(alert.encounter.patient.id),
            'severity': alert.severity,
            'message': alert.message,
            'context_data': alert.context_data,
            'acknowledged': alert.acknowledged,
            'acknowledged_by': alert.acknowledged_by.full_name if alert.acknowledged_by else None,
            'acknowledged_at': alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
            'acknowledgment_notes': alert.acknowledgment_notes,
            'created_at': alert.created_at.isoformat(),
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    except CdsAlert.DoesNotExist:
        return Response(
            {'error': 'Alert not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error fetching CDS alert detail: {e}", exc_info=True)
        return Response(
            {'error': 'Internal server error'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
