"""
Pharmacy Dispensing Views.

Handles pharmacy worklist, medication dispensing, and drug interaction checking.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Case, When, IntegerField
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital, User, AuditLog
from records.models import Prescription
from patients.models import Patient
from api.utils import get_effective_hospital, sanitize_audit_resource_id

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pharmacy_worklist(request):
    """
    Get pharmacy dispensing worklist.
    
    Returns all pending prescriptions sorted by priority (STAT > urgent > routine) and age.
    
    **Query params:**
    - priority: filter by priority (stat|urgent|routine)
    - patient_id: filter by patient
    """
    
    # Permission check - only pharmacy staff, nurses, hospital_admin, super_admin
    if request.user.role not in ('pharmacy_technician', 'nurse', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    effective_hospital = get_effective_hospital(request)
    if not effective_hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Build query
    q = Q(hospital=effective_hospital, status='pending')
    
    # Filter by priority
    priority_filter = request.GET.get('priority')
    if priority_filter:
        q &= Q(priority=priority_filter)
    
    # Filter by patient
    patient_id = request.GET.get('patient_id')
    if patient_id:
        q &= Q(patient_id=patient_id)
    
    # Query with priority sorting
    prescriptions = Prescription.objects.filter(q).select_related(
        'patient', 'hospital', 'record__created_by'
    ).annotate(
        priority_order=Case(
            When(priority='stat', then=1),
            When(priority='urgent', then=2),
            When(priority='routine', then=3),
            default=4,
            output_field=IntegerField()
        )
    ).order_by('priority_order', 'created_at')[:100]
    
    # Calculate summary stats
    all_pending = Prescription.objects.filter(hospital=effective_hospital, status='pending')
    summary = {
        'total_pending': all_pending.count(),
        'stat_count': all_pending.filter(priority='stat').count(),
        'urgent_count': all_pending.filter(priority='urgent').count(),
        'routine_count': all_pending.filter(priority='routine').count(),
    }
    
    # Serialize
    worklist = []
    for rx in prescriptions:
        wait_time_minutes = int((timezone.now() - rx.created_at).total_seconds() / 60)
        
        worklist.append({
            'prescription_id': str(rx.id),
            'patient_id': str(rx.patient_id) if rx.patient_id else None,
            'patient_name': rx.patient.full_name if rx.patient else 'Unknown',
            'patient_age': rx.patient.age if rx.patient and hasattr(rx.patient, 'age') else None,
            'drug_name': rx.drug_name,
            'dosage': rx.dosage,
            'frequency': rx.frequency,
            'duration_days': rx.duration_days,
            'route': rx.route,
            'priority': rx.priority,
            'prescribed_by': rx.record.created_by.full_name if rx.record and rx.record.created_by else 'Unknown',
            'prescribed_at': rx.created_at.isoformat(),
            'wait_time_minutes': wait_time_minutes,
            'allergy_conflict': rx.allergy_conflict,
            'drug_interaction_checked': rx.drug_interaction_checked,
            'drug_interactions': rx.drug_interactions,
            'notes': rx.notes,
        })
    
    return Response({
        'worklist': worklist,
        'summary': summary
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dispense_medication(request, prescription_id):
    """
    Dispense medication to patient.
    
    **Request body:**
    - dispensed_quantity: int (required)
    - dispense_notes: str (optional)
    - drug_interaction_override: bool (optional, if interactions found)
    
    **Auto-checks:**
    - Drug-drug interactions (basic check)
    - Allergy conflicts (already checked at prescription time)
    """
    
    # Permission check
    if request.user.role not in ('pharmacy_technician', 'nurse', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        prescription = Prescription.objects.select_related('patient', 'hospital').get(pk=prescription_id)
    except Prescription.DoesNotExist:
        return Response({'error': 'Prescription not found'}, status=status.HTTP_404_NOT_FOUND)
    
    # Validate hospital context
    effective_hospital = get_effective_hospital(request)
    if effective_hospital and prescription.hospital_id != effective_hospital.id:
        return Response({'error': 'Cannot dispense prescription from another hospital'}, status=status.HTTP_403_FORBIDDEN)
    
    # Check if already dispensed
    if prescription.status == 'dispensed':
        return Response({'error': 'Prescription already dispensed'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Get request data
    dispensed_quantity = request.data.get('dispensed_quantity')
    dispense_notes = request.data.get('dispense_notes', '')
    
    if not dispensed_quantity:
        return Response({'error': 'dispensed_quantity is required'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        dispensed_quantity = int(dispensed_quantity)
        if dispensed_quantity <= 0:
            raise ValueError
    except (ValueError, TypeError):
        return Response({'error': 'dispensed_quantity must be a positive integer'}, status=status.HTTP_400_BAD_REQUEST)
    
    # Basic drug interaction check (placeholder - in production, integrate with DrugBank API)
    drug_interactions = None
    if prescription.patient:
        # Get patient's active prescriptions
        active_prescriptions = Prescription.objects.filter(
            patient=prescription.patient,
            status='pending',
            hospital=prescription.hospital
        ).exclude(pk=prescription.id)
        
        if active_prescriptions.exists():
            # Simplified interaction detection (in production, use DrugBank or similar)
            interactions = []
            for active_rx in active_prescriptions:
                # Example: Warfarin + NSAIDs = bleeding risk
                if ('warfarin' in prescription.drug_name.lower() and 'ibuprofen' in active_rx.drug_name.lower()) or \
                   ('warfarin' in active_rx.drug_name.lower() and 'ibuprofen' in prescription.drug_name.lower()):
                    interactions.append({
                        'drug_1': prescription.drug_name,
                        'drug_2': active_rx.drug_name,
                        'severity': 'high',
                        'description': 'Increased bleeding risk: NSAIDs + anticoagulants'
                    })
            
            if interactions:
                drug_interactions = interactions
                
                # Check if override provided
                if not request.data.get('drug_interaction_override'):
                    return Response({
                        'error': 'Drug interactions detected',
                        'drug_interactions': drug_interactions,
                        'requires_override': True
                    }, status=status.HTTP_400_BAD_REQUEST)
    
    # Update prescription
    with transaction.atomic():
        prescription.status = 'dispensed'
        prescription.dispense_status = 'dispensed'
        prescription.dispensed_at = timezone.now()
        prescription.dispensed_by = request.user
        prescription.dispensed_quantity = dispensed_quantity
        prescription.dispense_notes = dispense_notes
        prescription.drug_interaction_checked = True
        prescription.drug_interactions = drug_interactions
        prescription.save()
        
        # Audit log
        AuditLog.log_action(
            user=request.user,
            action='MEDICATION_DISPENSE',
            resource_type='Prescription',
            resource_id=sanitize_audit_resource_id(str(prescription.id)),
            hospital=prescription.hospital,
            extra_data={
                'drug_name': prescription.drug_name,
                'dispensed_quantity': dispensed_quantity,
                'patient_id': str(prescription.patient_id) if prescription.patient_id else None,
                'drug_interactions': bool(drug_interactions),
            }
        )
    
    return Response({
        'prescription_id': str(prescription.id),
        'status': prescription.status,
        'dispensed_at': prescription.dispensed_at.isoformat(),
        'dispensed_by': request.user.full_name,
        'dispensed_quantity': dispensed_quantity,
        'drug_interactions': drug_interactions,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def pharmacy_statistics(request):
    """
    Get pharmacy statistics for dashboard.
    
    Returns daily/weekly dispensing metrics.
    """
    
    if request.user.role not in ('pharmacy_technician', 'hospital_admin', 'super_admin'):
        return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
    
    effective_hospital = get_effective_hospital(request)
    if not effective_hospital:
        return Response({'error': 'Hospital context required'}, status=status.HTTP_400_BAD_REQUEST)
    
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = today_start - timedelta(days=7)
    
    # Today's stats
    today_dispensed = Prescription.objects.filter(
        hospital=effective_hospital,
        status='dispensed',
        dispensed_at__gte=today_start
    ).count()
    
    today_pending = Prescription.objects.filter(
        hospital=effective_hospital,
        status='pending',
        created_at__gte=today_start
    ).count()
    
    # Week stats
    week_dispensed = Prescription.objects.filter(
        hospital=effective_hospital,
        status='dispensed',
        dispensed_at__gte=week_start
    ).count()
    
    # Average turnaround time (prescription to dispense)
    recent_dispensed = Prescription.objects.filter(
        hospital=effective_hospital,
        status='dispensed',
        dispensed_at__gte=week_start,
        dispensed_at__isnull=False,
        created_at__isnull=False
    )
    
    avg_tat_minutes = 0
    if recent_dispensed.exists():
        total_seconds = sum([
            (rx.dispensed_at - rx.created_at).total_seconds()
            for rx in recent_dispensed
        ])
        avg_tat_minutes = int(total_seconds / recent_dispensed.count() / 60)
    
    return Response({
        'today': {
            'dispensed': today_dispensed,
            'pending': today_pending,
        },
        'week': {
            'dispensed': week_dispensed,
            'avg_turnaround_minutes': avg_tat_minutes,
        }
    })
