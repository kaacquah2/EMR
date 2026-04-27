"""
Utilities for vital signs tracking, overdue detection, and critical vital assessment.
Centralizes logic used across dashboard, ward, and nurse views.
"""

from datetime import timedelta
from django.db.models import OuterRef, Subquery
from django.utils import timezone

from records.models import MedicalRecord

# Configuration constants
VITALS_OVERDUE_THRESHOLD_HOURS = 4
VITALS_CRITICAL_THRESHOLD_HOURS = 8
VITALS_URGENT_THRESHOLD_HOURS = 4
SPO2_CRITICAL_THRESHOLD = 88
BP_SYSTOLIC_CRITICAL_THRESHOLD = 180
BP_DIASTOLIC_CRITICAL_THRESHOLD = 110


def get_vitals_overdue_cutoff(hours_threshold=VITALS_OVERDUE_THRESHOLD_HOURS):
    """Get the datetime cutoff for vitals overdue detection."""
    return timezone.now() - timedelta(hours=hours_threshold)


def get_last_vitals_timestamp(patient):
    """
    Get the timestamp of the last recorded vital for a patient.
    Returns None if no vitals have been recorded.
    """
    latest_vital_record = MedicalRecord.objects.filter(
        patient=patient,
        record_type="vital_signs"
    ).order_by("-created_at").first()

    return latest_vital_record.created_at if latest_vital_record else None


def is_vitals_overdue(admission, hours_threshold=VITALS_OVERDUE_THRESHOLD_HOURS):
    """
    Check if a patient's vital signs are overdue.
    A vital is overdue if:
    - No vital has been recorded (last_vitals_at is None), OR
    - Last vital was recorded more than hours_threshold ago

    Returns: (is_overdue: bool, hours_overdue: float or None)
    """
    last_vitals_at = get_last_vitals_timestamp(admission.patient)
    cutoff = get_vitals_overdue_cutoff(hours_threshold)

    if last_vitals_at is None:
        # No vitals recorded - calculate from admission time
        hours_overdue = (timezone.now() - admission.admitted_at).total_seconds() / 3600
        return True, hours_overdue

    if last_vitals_at < cutoff:
        # Last vital is older than threshold
        hours_overdue = (timezone.now() - last_vitals_at).total_seconds() / 3600
        return True, hours_overdue

    # Within threshold
    return False, None


def get_vitals_overdue_priority(hours_overdue):
    """
    Classify priority level based on hours overdue.
    - critical: >8 hours overdue
    - high: 4-8 hours overdue
    - medium: <4 hours (but still overdue)
    """
    if hours_overdue > VITALS_CRITICAL_THRESHOLD_HOURS:
        return "critical"
    elif hours_overdue > VITALS_URGENT_THRESHOLD_HOURS:
        return "high"
    else:
        return "medium"


def is_critical_vital(vital):
    """
    Check if a vital reading indicates critical status.
    Critical thresholds:
    - SpO2 < 88%
    - BP systolic > 180
    - BP diastolic > 110
    """
    if vital is None:
        return False

    if vital.spo2_percent is not None and vital.spo2_percent < SPO2_CRITICAL_THRESHOLD:
        return True

    if vital.bp_systolic is not None and vital.bp_systolic > BP_SYSTOLIC_CRITICAL_THRESHOLD:
        return True

    if vital.bp_diastolic is not None and vital.bp_diastolic > BP_DIASTOLIC_CRITICAL_THRESHOLD:
        return True

    return False


def get_latest_vital(patient):
    """
    Get the latest Vital object for a patient.
    Returns None if no vitals recorded.
    """
    try:
        vital_record = MedicalRecord.objects.filter(
            patient=patient,
            record_type="vital_signs"
        ).select_related('vital').order_by("-created_at").first()

        return vital_record.vital if vital_record else None
    except Exception:
        return None


def should_highlight_bed_as_watch(admission, critical_alerts_exist=False,
                                  hours_threshold=VITALS_OVERDUE_THRESHOLD_HOURS):
    """
    Determine if a bed should be highlighted as "watch" status.
    Returns True if:
    - Vitals are overdue AND threshold exceeded, OR
    - Active critical alerts exist
    """
    is_overdue, _ = is_vitals_overdue(admission, hours_threshold)

    if critical_alerts_exist:
        return True

    return is_overdue


def should_highlight_bed_as_critical(admission, hours_threshold=VITALS_OVERDUE_THRESHOLD_HOURS):
    """
    Determine if a bed should be highlighted as "critical" status.
    Returns True if:
    - Latest vital reading shows critical values (SpO2 < 88%, BP > 180)
    """
    latest_vital = get_latest_vital(admission.patient)
    return is_critical_vital(latest_vital)


def get_vitals_needed_for_patient(patient):
    """
    Get list of vital types needed for a patient.
    Standard vital types are:
    - temperature
    - blood_pressure
    - heart_rate
    - respiratory_rate
    - oxygen_saturation
    """
    return [
        "temperature",
        "blood_pressure",
        "heart_rate",
        "respiratory_rate",
        "oxygen_saturation"
    ]


def annotate_admissions_with_vitals_status(admissions_queryset, hours_threshold=VITALS_OVERDUE_THRESHOLD_HOURS):
    """
    Annotate a PatientAdmission queryset with latest vitals timestamp.
    Useful for efficient batch queries in list views.

    Returns queryset with annotated 'last_vitals_at' field.
    """

    last_vitals_subquery = Subquery(
        MedicalRecord.objects.filter(
            patient_id=OuterRef('patient_id'),
            record_type="vital_signs"
        ).order_by("-created_at").values("created_at")[:1]
    )

    return admissions_queryset.annotate(last_vitals_at=last_vitals_subquery)


def calculate_qsofa(systolic_bp, respiratory_rate, gcs_score=15):
    """
    Calculate qSOFA (Quick Sequential Organ Failure Assessment) score.
    Score >=2 indicates high risk of sepsis.
    
    Criteria (1 point each):
    - Systolic BP <= 100 mmHg
    - Respiratory rate >= 22/min
    - Altered mental status (GCS < 15)
    
    Args:
        systolic_bp: Systolic blood pressure in mmHg (int or None)
        respiratory_rate: Respiratory rate in breaths/min (int or None)
        gcs_score: Glasgow Coma Scale (0-15, default 15=alert)
    
    Returns: 
        tuple (score: int, criteria_met: list[str])
    """
    score = 0
    criteria_met = []
    
    if systolic_bp is not None and systolic_bp <= 100:
        score += 1
        criteria_met.append(f"Low systolic BP: {systolic_bp} mmHg (≤100)")
    
    if respiratory_rate is not None and respiratory_rate >= 22:
        score += 1
        criteria_met.append(f"High respiratory rate: {respiratory_rate}/min (≥22)")
    
    if gcs_score is not None and gcs_score < 15:
        score += 1
        criteria_met.append(f"Altered mental status: GCS {gcs_score} (<15)")
    
    return score, criteria_met


def calculate_news2(
    respiratory_rate, spo2, on_supplemental_o2, systolic_bp,
    pulse, consciousness_level, temperature
):
    """
    Calculate NEWS2 (National Early Warning Score 2).
    Comprehensive scoring system for acute illness severity assessment.
    
    Args:
        respiratory_rate: Breaths per minute (int or None)
        spo2: Oxygen saturation percentage (float or None, 0-100)
        on_supplemental_o2: Whether patient is on supplemental oxygen (bool)
        systolic_bp: Systolic blood pressure mmHg (int or None)
        pulse: Heart rate beats per minute (int or None)
        consciousness_level: Consciousness level - 'A' (Alert), 'C' (Confusion), 'V', 'P', 'U' (str or None)
        temperature: Body temperature Celsius (float or None)
    
    Returns: 
        tuple (score: int, risk_level: str)
        Risk levels: "low" (0-4), "medium" (5-6), "high" (7+)
    """
    score = 0
    
    # Respiratory rate scoring
    if respiratory_rate is not None:
        if respiratory_rate <= 8:
            score += 3
        elif respiratory_rate <= 11:
            score += 1
        elif respiratory_rate <= 20:
            score += 0
        elif respiratory_rate <= 24:
            score += 2
        else:  # >=25
            score += 3
    
    # SpO2 scoring (Scale 1 for non-COPD patients)
    if spo2 is not None:
        spo2_val = float(spo2) if spo2 else None
        if spo2_val and spo2_val <= 91:
            score += 3
        elif spo2_val and spo2_val <= 93:
            score += 2
        elif spo2_val and spo2_val <= 95:
            score += 1
        elif spo2_val:
            score += 0
    
    # Supplemental oxygen - only if patient is hypoxic
    # If on supplemental O2 and SpO2 not recorded, add 2 points for safety
    if on_supplemental_o2:
        score += 2
    
    # Systolic BP
    if systolic_bp is not None:
        if systolic_bp <= 90:
            score += 3
        elif systolic_bp <= 100:
            score += 2
        elif systolic_bp <= 110:
            score += 1
        elif systolic_bp <= 219:
            score += 0
        else:  # >=220
            score += 3
    
    # Pulse
    if pulse is not None:
        if pulse <= 40:
            score += 3
        elif pulse <= 50:
            score += 1
        elif pulse <= 90:
            score += 0
        elif pulse <= 110:
            score += 1
        elif pulse <= 130:
            score += 2
        else:  # >=131
            score += 3
    
    # Consciousness (A=Alert, C/V/P/U=Altered)
    if consciousness_level and consciousness_level.upper() != 'A':
        score += 3
    
    # Temperature
    if temperature is not None:
        temp_val = float(temperature) if temperature else None
        if temp_val and temp_val <= 35.0:
            score += 3
        elif temp_val and temp_val <= 36.0:
            score += 1
        elif temp_val and temp_val <= 38.0:
            score += 0
        elif temp_val and temp_val <= 39.0:
            score += 1
        elif temp_val:  # >=39.1
            score += 2
    
    # Determine risk level
    if score >= 7:
        risk_level = "high"
    elif score >= 5:
        risk_level = "medium"
    else:
        risk_level = "low"
    
    return score, risk_level
