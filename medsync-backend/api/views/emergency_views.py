"""
Emergency Department Views.

Handles triage color codes, real-time ED queue, and auto-escalation workflows.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q, Count, Avg, Min, F, DurationField, ExpressionWrapper, Case, When, IntegerField
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital, User, AuditLog
from patients.models import Appointment, Patient
from api.utils import get_effective_hospital, sanitize_audit_resource_id

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_triage_color(request, appointment_id):
    """
    Assign triage color code to emergency patient.
    
    **Triage Colors:**
    - RED (Immediate): Life-threatening, <5min
    - YELLOW (Urgent): Serious, <30min
    - GREEN (Less Urgent): Non-emergent, <2hr
    - BLUE (Non-Urgent): Stable, routine
    
    **Required fields:**
    - triage_color: red|yellow|green|blue
    - chief_complaint: str
    - vital signs (optional): bp_systolic, bp_diastolic, heart_rate, respiratory_rate, spo2, temperature, pain_scale
    
    **Auto-escalation rules:**
    - SpO2 <90% → RED
    - BP <90/60 → RED  
    - HR >130 or <50 → YELLOW
    - RR >30 or <10 → YELLOW
    - Pain scale >8 → YELLOW
    """
    
    # Permission check
    if request.user.role not in ("doctor", "nurse", "hospital_admin", "super_admin"):
        return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        appointment = Appointment.objects.get(pk=appointment_id)
    except Appointment.DoesNotExist:
        return Response({"error": "Appointment not found"}, status=status.HTTP_404_NOT_FOUND)
    
    # Validate hospital context
    effective_hospital = get_effective_hospital(request)
    if effective_hospital and appointment.hospital_id != effective_hospital.id:
        return Response({"error": "Cannot triage appointment from another hospital"}, status=status.HTTP_403_FORBIDDEN)
    
    # Get triage data
    triage_color = request.data.get('triage_color')
    chief_complaint = request.data.get('chief_complaint')
    
    # Validate triage color
    valid_colors = ['red', 'yellow', 'green', 'blue']
    if triage_color not in valid_colors:
        return Response({"error": f"Invalid triage_color. Must be one of: {valid_colors}"}, status=status.HTTP_400_BAD_REQUEST)
    
    if not chief_complaint:
        return Response({"error": "chief_complaint is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Extract vital signs
    vitals = {}
    vital_fields = ['bp_systolic', 'bp_diastolic', 'heart_rate', 'respiratory_rate', 'spo2', 'temperature', 'pain_scale']
    for field in vital_fields:
        if field in request.data:
            vitals[field] = request.data[field]
    
    # Auto-escalation rules
    escalated = False
    escalation_reason = []
    
    if 'spo2' in vitals and vitals['spo2'] < 90:
        triage_color = 'red'
        escalated = True
        escalation_reason.append(f"SpO2 {vitals['spo2']}% <90%")
    
    if 'bp_systolic' in vitals and vitals['bp_systolic'] < 90:
        triage_color = 'red'
        escalated = True
        escalation_reason.append(f"Systolic BP {vitals['bp_systolic']} <90")
    
    if 'heart_rate' in vitals:
        hr = vitals['heart_rate']
        if hr > 130 or hr < 50:
            if triage_color not in ['red']:  # Don't downgrade from red
                triage_color = 'yellow'
                escalated = True
                escalation_reason.append(f"HR {hr} outside 50-130")
    
    if 'respiratory_rate' in vitals:
        rr = vitals['respiratory_rate']
        if rr > 30 or rr < 10:
            if triage_color not in ['red']:
                triage_color = 'yellow'
                escalated = True
                escalation_reason.append(f"RR {rr} outside 10-30")
    
    if 'pain_scale' in vitals and vitals['pain_scale'] > 8:
        if triage_color not in ['red']:
            triage_color = 'yellow'
            escalated = True
            escalation_reason.append(f"Pain scale {vitals['pain_scale']}/10 >8")
    
    # Update appointment
    appointment.triage_color = triage_color
    appointment.chief_complaint = chief_complaint
    appointment.triage_vitals = vitals
    appointment.triage_assessed_at = timezone.now()
    appointment.triaged_by = request.user
    
    # If not already checked in, auto check-in ED patients
    if appointment.status == 'scheduled' and appointment.urgency == 'emergency':
        appointment.status = 'checked_in'
        appointment.ed_arrival_time = timezone.now()
    
    appointment.save()
    
    # Audit log
    AuditLog.log_action(
        user=request.user,
        action='TRIAGE_ASSIGN',
        resource_type='Appointment',
        resource_id=sanitize_audit_resource_id(str(appointment.id)),
        hospital=appointment.hospital,
        extra_data={
            'triage_color': triage_color,
            'chief_complaint': chief_complaint[:100],
            'escalated': escalated,
            'escalation_reason': escalation_reason if escalated else None,
        }
    )
    
    return Response({
        'success': True,
        'appointment_id': str(appointment.id),
        'triage_color': triage_color,
        'escalated': escalated,
        'escalation_reason': escalation_reason if escalated else None,
        'triaged_at': appointment.triage_assessed_at.isoformat(),
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ed_queue_realtime(request):
    """
    Real-time Emergency Department queue.
    
    Returns all ED patients sorted by:
    1. Triage color priority (red → yellow → green → blue)
    2. Wait time (longest first)
    
    **Response includes:**
    - Patient demographics
    - Triage color + chief complaint
    - Wait time (minutes)
    - Vitals
    - Assigned room (if any)
    
    **Query params:**
    - triage_color: filter by color (red|yellow|green|blue)
    - status: filter by appointment status (default: checked_in)
    """
    
    # Permission check
    if request.user.role not in ("doctor", "nurse", "receptionist", "hospital_admin", "super_admin"):
        return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
    
    effective_hospital = get_effective_hospital(request)
    if not effective_hospital:
        return Response({"error": "Hospital context required"}, status=status.HTTP_400_BAD_REQUEST)
    
    # Build query
    q = Q(hospital=effective_hospital, urgency='emergency')
    
    # Filter by status (default: checked_in)
    appointment_status = request.GET.get('status', 'checked_in')
    if appointment_status:
        q &= Q(status=appointment_status)
    
    # Filter by triage color
    triage_color_filter = request.GET.get('triage_color')
    if triage_color_filter:
        q &= Q(triage_color=triage_color_filter)
    
    # Fetch appointments
    appointments = Appointment.objects.filter(q).select_related('patient', 'triaged_by', 'provider').order_by(
        # Priority: red, yellow, green, blue, null
        models.Case(
            models.When(triage_color='red', then=1),
            models.When(triage_color='yellow', then=2),
            models.When(triage_color='green', then=3),
            models.When(triage_color='blue', then=4),
            default=5,
            output_field=models.IntegerField(),
        ),
        # Then by wait time (oldest first)
        'ed_arrival_time'
    )
    
    # Build response
    queue = []
    now = timezone.now()
    
    for apt in appointments:
        # Calculate wait time
        arrival = apt.ed_arrival_time or apt.scheduled_at
        wait_minutes = int((now - arrival).total_seconds() / 60)
        
        queue.append({
            'appointment_id': str(apt.id),
            'patient': {
                'id': str(apt.patient.id),
                'name': apt.patient.full_name,
                'ghana_health_id': apt.patient.ghana_health_id,
                'age': (timezone.now().date() - apt.patient.date_of_birth).days // 365,
                'gender': apt.patient.gender,
            },
            'triage_color': apt.triage_color,
            'chief_complaint': apt.chief_complaint,
            'vitals': apt.triage_vitals,
            'triaged_by': apt.triaged_by.full_name if apt.triaged_by else None,
            'triaged_at': apt.triage_assessed_at.isoformat() if apt.triage_assessed_at else None,
            'arrival_time': arrival.isoformat(),
            'wait_time_minutes': wait_minutes,
            'status': apt.status,
            'assigned_provider': apt.provider.full_name if apt.provider else None,
            'ed_room': apt.ed_room_assignment,
        })
    
    # Calculate summary stats
    summary = {
        'total_count': len(queue),
        'red_count': sum(1 for item in queue if item['triage_color'] == 'red'),
        'yellow_count': sum(1 for item in queue if item['triage_color'] == 'yellow'),
        'green_count': sum(1 for item in queue if item['triage_color'] == 'green'),
        'blue_count': sum(1 for item in queue if item['triage_color'] == 'blue'),
        'not_triaged_count': sum(1 for item in queue if not item['triage_color']),
        'avg_wait_time_minutes': int(sum(item['wait_time_minutes'] for item in queue) / len(queue)) if queue else 0,
        'max_wait_time_minutes': max((item['wait_time_minutes'] for item in queue), default=0),
    }
    
    return Response({
        'queue': queue,
        'summary': summary,
        'timestamp': now.isoformat(),
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def assign_ed_room(request, appointment_id):
    """
    Assign ED room/bed to patient.
    
    **Required fields:**
    - room_number: str (e.g., "ED-1", "Trauma Bay 2")
    """
    
    if request.user.role not in ("nurse", "hospital_admin", "super_admin"):
        return Response({"error": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        appointment = Appointment.objects.get(pk=appointment_id)
    except Appointment.DoesNotExist:
        return Response({"error": "Appointment not found"}, status=status.HTTP_404_NOT_FOUND)
    
    effective_hospital = get_effective_hospital(request)
    if effective_hospital and appointment.hospital_id != effective_hospital.id:
        return Response({"error": "Cannot assign room in another hospital"}, status=status.HTTP_403_FORBIDDEN)
    
    room_number = request.data.get('room_number')
    if not room_number:
        return Response({"error": "room_number is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    appointment.ed_room_assignment = room_number
    appointment.save()
    
    # Audit
    AuditLog.log_action(
        user=request.user,
        action='ED_ROOM_ASSIGN',
        resource_type='Appointment',
        resource_id=sanitize_audit_resource_id(str(appointment.id)),
        hospital=appointment.hospital,
        extra_data={'room_number': room_number}
    )
    
    return Response({
        'success': True,
        'appointment_id': str(appointment.id),
        'room_number': room_number,
    }, status=status.HTTP_200_OK)
