"""
Real-Time Vital Monitoring views for MedSync EMR.
Provides patient vital trends, ward dashboards, and alert escalation.
"""

from datetime import timedelta
from decimal import Decimal

from django.db.models import Max, Q
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import AuditLog, User, Ward, Hospital
from patients.models import ClinicalAlert, Patient, PatientAdmission
from records.models import MedicalRecord, Vital

from api.utils import get_effective_hospital, get_request_hospital


# Abnormal vital thresholds
ABNORMAL_THRESHOLDS = {
    "spo2_low": Decimal("92.0"),
    "heart_rate_high": 120,
    "heart_rate_low": 50,
    "bp_systolic_high": 180,
    "bp_diastolic_high": 120,
    "bp_systolic_low": 90,
    "bp_diastolic_low": 60,
    "temp_high": Decimal("38.5"),
}


def _get_hospital_context(request):
    """Return effective hospital for scoping. Returns None for super_admin without scoping."""
    effective = get_effective_hospital(request)
    if effective:
        return effective
    if request.user.role == "super_admin" and not request.user.hospital_id:
        return None
    return request.user.hospital


def _check_abnormal_flags(vital):
    """Check vital signs against thresholds and return list of abnormal flags."""
    flags = []
    
    if vital.spo2_percent is not None and vital.spo2_percent < ABNORMAL_THRESHOLDS["spo2_low"]:
        flags.append({
            "type": "spo2_low",
            "value": float(vital.spo2_percent),
            "threshold": float(ABNORMAL_THRESHOLDS["spo2_low"]),
            "severity": "critical",
            "message": f"SpO2 {vital.spo2_percent}% below 92%",
        })
    
    if vital.pulse_bpm is not None:
        if vital.pulse_bpm > ABNORMAL_THRESHOLDS["heart_rate_high"]:
            flags.append({
                "type": "heart_rate_high",
                "value": vital.pulse_bpm,
                "threshold": ABNORMAL_THRESHOLDS["heart_rate_high"],
                "severity": "high",
                "message": f"Heart rate {vital.pulse_bpm} bpm above 120",
            })
        elif vital.pulse_bpm < ABNORMAL_THRESHOLDS["heart_rate_low"]:
            flags.append({
                "type": "heart_rate_low",
                "value": vital.pulse_bpm,
                "threshold": ABNORMAL_THRESHOLDS["heart_rate_low"],
                "severity": "high",
                "message": f"Heart rate {vital.pulse_bpm} bpm below 50",
            })
    
    if vital.bp_systolic is not None and vital.bp_diastolic is not None:
        if vital.bp_systolic > ABNORMAL_THRESHOLDS["bp_systolic_high"] or \
           vital.bp_diastolic > ABNORMAL_THRESHOLDS["bp_diastolic_high"]:
            flags.append({
                "type": "bp_high",
                "value": f"{vital.bp_systolic}/{vital.bp_diastolic}",
                "threshold": f"{ABNORMAL_THRESHOLDS['bp_systolic_high']}/{ABNORMAL_THRESHOLDS['bp_diastolic_high']}",
                "severity": "critical",
                "message": f"BP {vital.bp_systolic}/{vital.bp_diastolic} critically high",
            })
        elif vital.bp_systolic < ABNORMAL_THRESHOLDS["bp_systolic_low"] or \
             vital.bp_diastolic < ABNORMAL_THRESHOLDS["bp_diastolic_low"]:
            flags.append({
                "type": "bp_low",
                "value": f"{vital.bp_systolic}/{vital.bp_diastolic}",
                "threshold": f"{ABNORMAL_THRESHOLDS['bp_systolic_low']}/{ABNORMAL_THRESHOLDS['bp_diastolic_low']}",
                "severity": "high",
                "message": f"BP {vital.bp_systolic}/{vital.bp_diastolic} critically low",
            })
    
    if vital.temperature_c is not None and vital.temperature_c > ABNORMAL_THRESHOLDS["temp_high"]:
        flags.append({
            "type": "temp_high",
            "value": float(vital.temperature_c),
            "threshold": float(ABNORMAL_THRESHOLDS["temp_high"]),
            "severity": "high",
            "message": f"Temperature {vital.temperature_c}°C above 38.5",
        })
    
    return flags


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def patient_vital_trends(request, patient_id):
    """
    GET /vitals/patient/<patient_id>/trends
    
    Returns vital sign trends for a patient over time periods (24h, 7d, 30d).
    
    Query Parameters:
        period: 24h, 7d, 30d (default: 24h)
    
    Returns:
        {
            "patient_id": "uuid",
            "patient_name": "Ama Owusu",
            "period": "24h",
            "data_points": [
                {
                    "timestamp": "2024-01-15T08:00:00Z",
                    "bp_systolic": 120,
                    "bp_diastolic": 80,
                    "heart_rate": 72,
                    "respiratory_rate": 16,
                    "spo2": 98.0,
                    "temperature": 36.8,
                    "recorded_by": "Nurse Adjei"
                }, ...
            ],
            "abnormal_events": [...],
            "summary": {
                "total_readings": 12,
                "abnormal_count": 2
            }
        }
    
    Roles: doctor, nurse, hospital_admin, super_admin
    """
    allowed_roles = {"doctor", "nurse", "hospital_admin", "super_admin"}
    if request.user.role not in allowed_roles:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get hospital context
    hospital = _get_hospital_context(request)
    
    # Get patient
    try:
        patient_qs = Patient.objects.all()
        if hospital:
            patient_qs = patient_qs.filter(registered_at=hospital)
        patient = patient_qs.get(id=patient_id)
    except Patient.DoesNotExist:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Parse period
    period = request.GET.get("period", "24h")
    period_map = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    if period not in period_map:
        return Response(
            {"message": "Invalid period. Use 24h, 7d, or 30d"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    cutoff = timezone.now() - period_map[period]
    
    # Get vital records for patient within period
    vital_records = MedicalRecord.objects.filter(
        patient=patient,
        record_type="vital_signs",
        created_at__gte=cutoff,
    ).select_related("created_by").order_by("created_at")
    
    if hospital:
        vital_records = vital_records.filter(hospital=hospital)
    
    vital_ids = [r.id for r in vital_records]
    vitals = Vital.objects.filter(record_id__in=vital_ids).select_related("record", "recorded_by")
    
    # Build lookup
    vital_by_record = {v.record_id: v for v in vitals}
    
    data_points = []
    abnormal_events = []
    
    for record in vital_records:
        vital = vital_by_record.get(record.id)
        if not vital:
            continue
        
        point = {
            "timestamp": record.created_at.isoformat(),
            "bp_systolic": vital.bp_systolic,
            "bp_diastolic": vital.bp_diastolic,
            "heart_rate": vital.pulse_bpm,
            "respiratory_rate": vital.resp_rate,
            "spo2": float(vital.spo2_percent) if vital.spo2_percent else None,
            "temperature": float(vital.temperature_c) if vital.temperature_c else None,
            "recorded_by": vital.recorded_by.full_name if vital.recorded_by else None,
        }
        data_points.append(point)
        
        # Check for abnormal values
        flags = _check_abnormal_flags(vital)
        if flags:
            abnormal_events.append({
                "timestamp": record.created_at.isoformat(),
                "flags": flags,
            })
    
    # Audit log
    AuditLog.log_action(
        user=request.user,
        action="VIEW_VITAL_TRENDS",
        resource_type="patient",
        resource_id=str(patient_id),
        hospital=hospital,
        request=request,
        details={"period": period},
    )
    
    return Response({
        "patient_id": str(patient.id),
        "patient_name": patient.full_name,
        "period": period,
        "data_points": data_points,
        "abnormal_events": abnormal_events,
        "summary": {
            "total_readings": len(data_points),
            "abnormal_count": len(abnormal_events),
        },
    })


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def ward_vitals_dashboard(request, ward_id):
    """
    GET /vitals/ward/<ward_id>/dashboard
    
    Returns current vitals for all admitted patients in a ward.
    Highlights abnormal values.
    
    Returns:
        {
            "ward_id": "uuid",
            "ward_name": "ICU",
            "timestamp": "2024-01-15T18:30:00Z",
            "patients": [
                {
                    "patient_id": "uuid",
                    "patient_name": "Ama Owusu",
                    "bed_number": "3B-01",
                    "latest_vitals": {
                        "bp_systolic": 120,
                        "bp_diastolic": 80,
                        "heart_rate": 72,
                        "respiratory_rate": 16,
                        "spo2": 98.0,
                        "temperature": 36.8
                    },
                    "abnormal_flags": [...],
                    "last_recorded_at": "2024-01-15T18:00:00Z",
                    "last_recorded_by": "Nurse Adjei"
                }, ...
            ],
            "summary": {
                "total_patients": 12,
                "patients_with_abnormals": 2,
                "critical_count": 1
            }
        }
    
    Roles: nurse, doctor, hospital_admin, super_admin
    """
    allowed_roles = {"nurse", "doctor", "hospital_admin", "super_admin"}
    if request.user.role not in allowed_roles:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get hospital context
    hospital = _get_hospital_context(request)
    
    # Get ward
    try:
        ward_qs = Ward.objects.all()
        if hospital:
            ward_qs = ward_qs.filter(hospital=hospital)
        ward = ward_qs.get(id=ward_id)
    except Ward.DoesNotExist:
        return Response(
            {"message": "Ward not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Get admitted patients in ward
    admissions = PatientAdmission.objects.filter(
        ward=ward,
        discharged_at__isnull=True,
    ).select_related("patient", "bed")
    
    if hospital:
        admissions = admissions.filter(hospital=hospital)
    
    patient_ids = [a.patient_id for a in admissions]
    
    # Get latest vital record for each patient (within last 24h)
    cutoff_24h = timezone.now() - timedelta(hours=24)
    
    latest_records = MedicalRecord.objects.filter(
        patient_id__in=patient_ids,
        record_type="vital_signs",
        created_at__gte=cutoff_24h,
    ).values("patient_id").annotate(latest=Max("created_at"))
    
    latest_times = {r["patient_id"]: r["latest"] for r in latest_records}
    
    # Fetch the actual records
    record_filters = Q()
    for pid, ts in latest_times.items():
        record_filters |= Q(patient_id=pid, created_at=ts, record_type="vital_signs")
    
    if record_filters:
        records = MedicalRecord.objects.filter(record_filters).select_related("created_by")
    else:
        records = MedicalRecord.objects.none()
    
    record_by_patient = {r.patient_id: r for r in records}
    
    # Fetch vitals
    record_ids = [r.id for r in records]
    vitals = Vital.objects.filter(record_id__in=record_ids).select_related("recorded_by")
    vital_by_record = {v.record_id: v for v in vitals}
    
    # Build bed mapping
    bed_map = {a.patient_id: a.bed.bed_code if a.bed else None for a in admissions}
    patient_map = {a.patient_id: a.patient for a in admissions}
    
    patients_data = []
    patients_with_abnormals = 0
    critical_count = 0
    
    for patient_id in patient_ids:
        patient = patient_map.get(patient_id)
        if not patient:
            continue
        
        record = record_by_patient.get(patient_id)
        vital = vital_by_record.get(record.id) if record else None
        
        patient_entry = {
            "patient_id": str(patient_id),
            "patient_name": patient.full_name,
            "bed_number": bed_map.get(patient_id),
            "latest_vitals": None,
            "abnormal_flags": [],
            "last_recorded_at": None,
            "last_recorded_by": None,
        }
        
        if vital:
            patient_entry["latest_vitals"] = {
                "bp_systolic": vital.bp_systolic,
                "bp_diastolic": vital.bp_diastolic,
                "heart_rate": vital.pulse_bpm,
                "respiratory_rate": vital.resp_rate,
                "spo2": float(vital.spo2_percent) if vital.spo2_percent else None,
                "temperature": float(vital.temperature_c) if vital.temperature_c else None,
            }
            patient_entry["last_recorded_at"] = record.created_at.isoformat()
            patient_entry["last_recorded_by"] = vital.recorded_by.full_name if vital.recorded_by else None
            
            flags = _check_abnormal_flags(vital)
            patient_entry["abnormal_flags"] = flags
            
            if flags:
                patients_with_abnormals += 1
                if any(f["severity"] == "critical" for f in flags):
                    critical_count += 1
        
        patients_data.append(patient_entry)
    
    # Audit log
    AuditLog.log_action(
        user=request.user,
        action="VIEW_WARD_VITALS_DASHBOARD",
        resource_type="ward",
        resource_id=str(ward_id),
        hospital=hospital or ward.hospital,
        request=request,
    )
    
    return Response({
        "ward_id": str(ward.id),
        "ward_name": ward.name,
        "timestamp": timezone.now().isoformat(),
        "patients": patients_data,
        "summary": {
            "total_patients": len(patients_data),
            "patients_with_abnormals": patients_with_abnormals,
            "critical_count": critical_count,
        },
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def escalate_alert(request, alert_id):
    """
    POST /vitals/alert/escalate/<alert_id>
    
    Escalate a clinical alert to senior staff.
    
    Request Body:
        {
            "escalation_reason": "Patient deteriorating rapidly",
            "escalate_to_role": "attending_doctor" | "department_head" | "on_call"
        }
    
    Returns:
        {
            "alert_id": "uuid",
            "escalation_id": "uuid",
            "escalated_at": "2024-01-15T18:30:00Z",
            "escalated_to_role": "attending_doctor",
            "escalated_to_users": ["Dr. Mensah"],
            "status": "escalated"
        }
    
    Roles: nurse, doctor
    """
    allowed_roles = {"nurse", "doctor"}
    if request.user.role not in allowed_roles:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Get hospital context
    hospital = _get_hospital_context(request)
    if not hospital:
        hospital = request.user.hospital
    
    if not hospital:
        return Response(
            {"message": "No hospital context available"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Get the alert
    try:
        alert_qs = ClinicalAlert.objects.select_related("patient")
        if hospital:
            alert_qs = alert_qs.filter(hospital=hospital)
        alert = alert_qs.get(id=alert_id)
    except ClinicalAlert.DoesNotExist:
        return Response(
            {"message": "Alert not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    # Validate request body
    escalation_reason = request.data.get("escalation_reason")
    escalate_to_role = request.data.get("escalate_to_role")
    
    if not escalation_reason:
        return Response(
            {"message": "escalation_reason is required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    valid_escalation_roles = {"attending_doctor", "department_head", "on_call"}
    if escalate_to_role not in valid_escalation_roles:
        return Response(
            {"message": f"escalate_to_role must be one of: {', '.join(valid_escalation_roles)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Find users to escalate to based on role
    target_users = []
    
    if escalate_to_role == "attending_doctor":
        # Find doctors in the hospital
        target_users = User.objects.filter(
            hospital=hospital,
            role="doctor",
            is_active=True,
        )[:5]
    elif escalate_to_role == "department_head":
        # Find hospital admins or senior doctors
        target_users = User.objects.filter(
            hospital=hospital,
            role__in=["doctor", "hospital_admin"],
            is_active=True,
        )[:3]
    elif escalate_to_role == "on_call":
        # Find any active clinical staff
        target_users = User.objects.filter(
            hospital=hospital,
            role__in=["doctor", "nurse"],
            is_active=True,
        )[:5]
    
    escalated_to_names = [u.full_name for u in target_users]
    
    # Update alert with escalation info
    escalation_details = {
        "escalated_by": str(request.user.id),
        "escalated_by_name": request.user.full_name,
        "escalation_reason": escalation_reason,
        "escalate_to_role": escalate_to_role,
        "escalated_to_user_ids": [str(u.id) for u in target_users],
        "escalated_at": timezone.now().isoformat(),
    }
    
    # Store escalation in alert message (append)
    original_message = alert.message
    alert.message = f"{original_message}\n\n[ESCALATED at {timezone.now().strftime('%Y-%m-%d %H:%M')}]\nReason: {escalation_reason}\nEscalated to: {escalate_to_role}"
    alert.severity = "critical"
    alert.save(update_fields=["message", "severity"])
    
    # Create escalation audit log
    AuditLog.log_action(
        user=request.user,
        action="ESCALATE_ALERT",
        resource_type="clinical_alert",
        resource_id=str(alert_id),
        hospital=hospital,
        request=request,
        details=escalation_details,
    )
    
    # Create notification entries for target users (using existing alert system)
    for target_user in target_users:
        ClinicalAlert.objects.create(
            patient=alert.patient,
            hospital=hospital,
            severity="critical",
            message=f"ESCALATED ALERT: {escalation_reason}\n\nOriginal alert: {original_message}",
            created_by=request.user,
            resource_type="escalation",
            resource_id=alert.id,
        )
    
    return Response({
        "alert_id": str(alert.id),
        "escalated_at": timezone.now().isoformat(),
        "escalated_to_role": escalate_to_role,
        "escalated_to_users": escalated_to_names,
        "escalation_reason": escalation_reason,
        "status": "escalated",
    })
