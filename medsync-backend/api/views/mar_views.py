"""
Medication Administration Record (MAR) Views.

Handles medication scheduling, administration tracking, and ward-based medication due lists.
"""

import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Hospital, User, AuditLog, Ward
from records.models import Prescription, MedicationSchedule
from patients.models import Patient, PatientAdmission
from api.utils import get_effective_hospital, sanitize_audit_resource_id

logger = logging.getLogger(__name__)

ALLOWED_ROLES = ('nurse', 'doctor', 'hospital_admin', 'super_admin')


def _check_mar_permission(request, ward_id=None):
    """Check if user has permission to access MAR functions."""
    if request.user.role not in ALLOWED_ROLES:
        return None, Response(
            {'error': 'Insufficient permissions. Only nurses, doctors, hospital admins and super admins can access MAR.'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    effective_hospital = get_effective_hospital(request)
    if not effective_hospital and request.user.role != 'super_admin':
        return None, Response(
            {'error': 'Hospital context required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if ward_id:
        try:
            ward = Ward.objects.get(pk=ward_id)
            if effective_hospital and ward.hospital_id != effective_hospital.id:
                return None, Response(
                    {'error': 'Ward does not belong to your hospital'},
                    status=status.HTTP_403_FORBIDDEN
                )
        except Ward.DoesNotExist:
            return None, Response(
                {'error': 'Ward not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        return {'hospital': effective_hospital, 'ward': ward}, None
    
    return {'hospital': effective_hospital}, None


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def ward_medications_due(request, ward_id):
    """
    Get medications due in next 2 hours for a ward.
    
    **Returns:**
    List of scheduled medications that need to be administered soon.
    
    **Access:** nurse, doctor, hospital_admin, super_admin
    """
    ctx, err = _check_mar_permission(request, ward_id)
    if err:
        return err
    
    ward = ctx['ward']
    hospital = ctx['hospital']
    
    now = timezone.now()
    window_end = now + timedelta(hours=2)
    
    # Get patients admitted to this ward
    admitted_patients = PatientAdmission.objects.filter(
        ward=ward,
        discharged_at__isnull=True
    ).values_list('patient_id', flat=True)
    
    # Get scheduled medications for these patients in the next 2 hours
    schedules = MedicationSchedule.objects.filter(
        patient_id__in=admitted_patients,
        scheduled_time__gte=now,
        scheduled_time__lte=window_end,
        status='scheduled'
    ).select_related(
        'prescription', 'patient', 'hospital'
    ).order_by('scheduled_time')
    
    # If hospital context exists, filter by hospital
    if hospital:
        schedules = schedules.filter(hospital=hospital)
    
    # Also get overdue medications (past due, still scheduled)
    overdue = MedicationSchedule.objects.filter(
        patient_id__in=admitted_patients,
        scheduled_time__lt=now,
        status='scheduled'
    ).select_related(
        'prescription', 'patient', 'hospital'
    ).order_by('scheduled_time')
    
    if hospital:
        overdue = overdue.filter(hospital=hospital)
    
    def serialize_schedule(sched, is_overdue=False):
        return {
            'schedule_id': str(sched.id),
            'patient_id': str(sched.patient_id),
            'patient_name': sched.patient.full_name,
            'prescription_id': str(sched.prescription_id),
            'drug_name': sched.prescription.drug_name,
            'dosage': sched.prescription.dosage,
            'route': sched.prescription.route,
            'frequency': sched.prescription.frequency,
            'scheduled_time': sched.scheduled_time.isoformat(),
            'status': sched.status,
            'is_overdue': is_overdue,
            'minutes_until_due': int((sched.scheduled_time - now).total_seconds() / 60) if not is_overdue else None,
            'minutes_overdue': int((now - sched.scheduled_time).total_seconds() / 60) if is_overdue else None,
            'notes': sched.prescription.notes,
        }
    
    due_meds = [serialize_schedule(s, is_overdue=False) for s in schedules]
    overdue_meds = [serialize_schedule(s, is_overdue=True) for s in overdue]
    
    return Response({
        'ward_id': str(ward_id),
        'ward_name': ward.name,
        'as_of': now.isoformat(),
        'window_end': window_end.isoformat(),
        'due_medications': due_meds,
        'overdue_medications': overdue_meds,
        'summary': {
            'due_count': len(due_meds),
            'overdue_count': len(overdue_meds),
            'total': len(due_meds) + len(overdue_meds),
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def administer_medication(request, schedule_id):
    """
    Mark medication as administered.
    
    **Request body:**
    - notes: str (optional) - Administration notes
    
    **Access:** nurse, doctor, hospital_admin, super_admin
    """
    ctx, err = _check_mar_permission(request)
    if err:
        return err
    
    hospital = ctx['hospital']
    
    try:
        schedule = MedicationSchedule.objects.select_related(
            'prescription', 'patient', 'hospital'
        ).get(pk=schedule_id)
    except MedicationSchedule.DoesNotExist:
        return Response(
            {'error': 'Medication schedule not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Hospital scope check
    if hospital and schedule.hospital_id != hospital.id:
        return Response(
            {'error': 'Cannot administer medication from another hospital'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Check current status
    if schedule.status == 'administered':
        return Response(
            {'error': 'Medication already administered'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if schedule.status == 'held':
        return Response(
            {'error': 'Medication is on hold. Remove hold before administering.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    notes = request.data.get('notes', '')
    
    with transaction.atomic():
        schedule.status = 'administered'
        schedule.actual_time = timezone.now()
        schedule.administered_by = request.user
        if notes:
            schedule.notes = notes
        schedule.save()
        
        # Audit log
        AuditLog.log_action(
            user=request.user,
            action='MEDICATION_ADMINISTERED',
            resource_type='MedicationSchedule',
            resource_id=sanitize_audit_resource_id(str(schedule.id)),
            hospital=schedule.hospital,
            extra_data={
                'drug_name': schedule.prescription.drug_name,
                'dosage': schedule.prescription.dosage,
                'patient_id': str(schedule.patient_id),
                'scheduled_time': schedule.scheduled_time.isoformat(),
                'actual_time': schedule.actual_time.isoformat(),
            }
        )
    
    return Response({
        'schedule_id': str(schedule.id),
        'status': schedule.status,
        'actual_time': schedule.actual_time.isoformat(),
        'administered_by': request.user.full_name,
        'drug_name': schedule.prescription.drug_name,
        'patient_name': schedule.patient.full_name,
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def hold_medication(request, schedule_id):
    """
    Put medication on hold with reason.
    
    **Request body:**
    - reason: str (required) - Reason for holding medication
    
    **Access:** nurse, doctor, hospital_admin, super_admin
    """
    ctx, err = _check_mar_permission(request)
    if err:
        return err
    
    hospital = ctx['hospital']
    
    try:
        schedule = MedicationSchedule.objects.select_related(
            'prescription', 'patient', 'hospital'
        ).get(pk=schedule_id)
    except MedicationSchedule.DoesNotExist:
        return Response(
            {'error': 'Medication schedule not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Hospital scope check
    if hospital and schedule.hospital_id != hospital.id:
        return Response(
            {'error': 'Cannot hold medication from another hospital'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Check current status
    if schedule.status == 'administered':
        return Response(
            {'error': 'Cannot hold medication that has already been administered'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if schedule.status == 'held':
        return Response(
            {'error': 'Medication is already on hold'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    reason = request.data.get('reason', '').strip()
    if not reason:
        return Response(
            {'error': 'Reason is required to hold medication'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    with transaction.atomic():
        schedule.status = 'held'
        schedule.hold_reason = reason
        schedule.save()
        
        # Audit log
        AuditLog.log_action(
            user=request.user,
            action='MEDICATION_HELD',
            resource_type='MedicationSchedule',
            resource_id=sanitize_audit_resource_id(str(schedule.id)),
            hospital=schedule.hospital,
            extra_data={
                'drug_name': schedule.prescription.drug_name,
                'patient_id': str(schedule.patient_id),
                'hold_reason': reason,
            }
        )
    
    return Response({
        'schedule_id': str(schedule.id),
        'status': schedule.status,
        'hold_reason': schedule.hold_reason,
        'held_by': request.user.full_name,
        'drug_name': schedule.prescription.drug_name,
        'patient_name': schedule.patient.full_name,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_medication_schedule(request, patient_id):
    """
    Get patient's medication schedule for today.
    
    **Query params:**
    - date: str (optional) - Date in YYYY-MM-DD format, defaults to today
    
    **Access:** nurse, doctor, hospital_admin, super_admin
    """
    ctx, err = _check_mar_permission(request)
    if err:
        return err
    
    hospital = ctx['hospital']
    
    # Validate patient exists
    try:
        patient = Patient.objects.get(pk=patient_id)
    except Patient.DoesNotExist:
        return Response(
            {'error': 'Patient not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Parse date parameter
    date_str = request.GET.get('date')
    if date_str:
        try:
            from datetime import datetime
            target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Invalid date format. Use YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    else:
        target_date = timezone.now().date()
    
    # Get start and end of day
    day_start = timezone.make_aware(
        timezone.datetime.combine(target_date, timezone.datetime.min.time())
    )
    day_end = timezone.make_aware(
        timezone.datetime.combine(target_date, timezone.datetime.max.time())
    )
    
    # Get schedules for this patient on the target date
    schedules = MedicationSchedule.objects.filter(
        patient=patient,
        scheduled_time__gte=day_start,
        scheduled_time__lte=day_end
    ).select_related(
        'prescription', 'administered_by', 'hospital'
    ).order_by('scheduled_time')
    
    # Hospital scope check
    if hospital:
        schedules = schedules.filter(hospital=hospital)
    
    now = timezone.now()
    
    schedule_list = []
    for sched in schedules:
        administered_by_name = None
        if sched.administered_by:
            administered_by_name = sched.administered_by.full_name
        
        schedule_list.append({
            'schedule_id': str(sched.id),
            'prescription_id': str(sched.prescription_id),
            'drug_name': sched.prescription.drug_name,
            'dosage': sched.prescription.dosage,
            'route': sched.prescription.route,
            'frequency': sched.prescription.frequency,
            'scheduled_time': sched.scheduled_time.isoformat(),
            'actual_time': sched.actual_time.isoformat() if sched.actual_time else None,
            'status': sched.status,
            'administered_by': administered_by_name,
            'hold_reason': sched.hold_reason,
            'refused_reason': sched.refused_reason,
            'notes': sched.notes,
            'is_overdue': sched.status == 'scheduled' and sched.scheduled_time < now,
        })
    
    # Summary counts
    status_counts = {
        'scheduled': 0,
        'administered': 0,
        'missed': 0,
        'held': 0,
        'refused': 0,
    }
    for sched in schedules:
        if sched.status in status_counts:
            status_counts[sched.status] += 1
    
    return Response({
        'patient_id': str(patient_id),
        'patient_name': patient.full_name,
        'date': target_date.isoformat(),
        'schedules': schedule_list,
        'summary': {
            'total': len(schedule_list),
            **status_counts
        }
    })
