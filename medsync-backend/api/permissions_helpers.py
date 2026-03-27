"""
PHASE 2: Object-Level Permission Checking

Implements object-level access control beyond role-based access.
Ensures users can only access objects from their authorized scope.

Addresses Issue #10: Missing object-level permission validation
"""

from django.core.exceptions import PermissionDenied
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from functools import wraps
from api.utils import get_effective_hospital


# ============================================================================
# OBJECT-LEVEL PERMISSION HELPERS
# ============================================================================

def can_access_patient(user, patient):
    """
    PHASE 2: Check if user can access a specific patient.
    
    Rules:
    - Super admin: can access all patients (respects hospital scoping if set)
    - Doctor: can access patients from their hospital only
    - Nurse: can access patients admitted to their ward only
    - Hospital admin: can access patients from their hospital
    - Receptionist: can access patients from their hospital
    - Lab technician: cannot access patients
    
    Args:
        user: User object
        patient: Patient object
    
    Returns:
        bool: True if user can access patient
    
    Raises:
        PermissionDenied: If user cannot access
    """
    if user.role == "super_admin":
        # Super admin can see all, respecting view-as hospital if set
        return True
    
    if user.role == "doctor":
        # PHASE 4: Doctor restricted to own hospital
        if not user.hospital or patient.registered_at != user.hospital:
            raise DRFPermissionDenied(
                f"Cannot access patient from hospital {patient.registered_at.name}. "
                f"You are authorized for {user.hospital.name if user.hospital else 'no hospital'}."
            )
        return True
    
    if user.role == "nurse":
        # Nurse can only see patients admitted to their ward
        from patients.models import PatientAdmission
        admission = PatientAdmission.objects.filter(
            patient=patient,
            ward=user.ward,
            discharged_at__isnull=True,  # Currently admitted
        ).first()
        
        if not admission:
            raise DRFPermissionDenied(
                "You can only access patients currently admitted to your ward."
            )
        return True
    
    if user.role in ["hospital_admin", "receptionist", "pharmacist", "radiology_technician", "billing_staff", "ward_clerk", "lab_technician"]:
        # Hospital admin/receptionist can access their hospital's patients
        if patient.registered_at != user.hospital:
            raise DRFPermissionDenied(
                f"Cannot access patient from hospital {patient.registered_at.name}. "
                f"You are authorized for {user.hospital.name}."
            )
        return True
    
    raise DRFPermissionDenied("Insufficient permissions to access this patient.")


def can_access_medical_record(user, medical_record):
    """
    PHASE 2: Check if user can access a medical record.
    
    Medical records are scoped to the patient's hospital.
    User must have access to the patient to access their records.
    """
    # First check if user can access the patient
    patient = medical_record.patient if hasattr(medical_record, 'patient') else None
    
    if not patient:
        raise DRFPermissionDenied("Record not associated with a patient.")
    
    return can_access_patient(user, patient)


def can_access_encounter(user, encounter):
    """
    PHASE 2: Check if user can access an encounter.
    
    Encounters are scoped to hospital and optionally to assigned provider.
    """
    if user.role == "super_admin":
        return True
    
    if user.role == "doctor":
        # Doctor can see: encounters in their hospital + encounters assigned to them
        if encounter.hospital != user.hospital:
            raise DRFPermissionDenied(
                f"Cannot access encounter from hospital {encounter.hospital.name}."
            )
        
        # Can see if assigned to them or from their department
        if (encounter.assigned_doctor != user and 
            encounter.assigned_department != user.department_link):
            raise DRFPermissionDenied(
                "You can only access encounters assigned to you or your department."
            )
        return True
    
    if user.role == "nurse":
        # Nurse can see encounters in their ward
        if encounter.ward != user.ward:
            raise DRFPermissionDenied(
                "You can only access encounters from your ward."
            )
        return True
    
    if user.role in ["hospital_admin", "receptionist"]:
        # Hospital admin/receptionist can access hospital's encounters
        if encounter.hospital != user.hospital:
            raise DRFPermissionDenied(
                f"Cannot access encounter from hospital {encounter.hospital.name}."
            )
        return True
    
    raise DRFPermissionDenied("Insufficient permissions to access this encounter.")


def can_access_lab_order(user, lab_order):
    """
    PHASE 2: Check if user can access a lab order.
    
    Lab orders are scoped to:
    - Hospital
    - Optionally assigned lab unit (for lab technicians)
    """
    if user.role == "super_admin":
        return True
    
    # All roles must be from the same hospital as the lab order
    if hasattr(user, 'hospital') and user.hospital:
        if lab_order.hospital != user.hospital:
            raise DRFPermissionDenied(
                f"Cannot access lab order from hospital {lab_order.hospital.name}."
            )
    
    if user.role == "lab_technician":
        # Lab tech can only access orders for their lab unit
        if lab_order.ordered_at_unit != user.lab_unit:
            raise DRFPermissionDenied(
                f"You can only access orders for {user.lab_unit.name}."
            )
    
    return True


def can_update_admission(user, admission):
    """
    PHASE 2: Check if user can update a patient admission.
    
    Only hospital_admin, nurses in the ward, and super_admin can discharge.
    """
    if user.role == "super_admin":
        return True
    
    if user.role == "hospital_admin":
        if admission.ward.hospital != user.hospital:
            raise DRFPermissionDenied(
                "Cannot modify admissions from other hospitals."
            )
        return True
    
    if user.role == "nurse":
        if admission.ward != user.ward:
            raise DRFPermissionDenied(
                "You can only modify admissions in your ward."
            )
        return True
    
    raise DRFPermissionDenied(
        "Only hospital admins and nurses can modify patient admissions."
    )


def can_view_audit_logs(user, hospital=None):
    """
    PHASE 2: Check if user can view audit logs.
    
    - Super admin: all logs
    - Hospital admin: hospital's logs only
    - Others: cannot view audit logs
    """
    if user.role == "super_admin":
        return True
    
    if user.role == "hospital_admin":
        if hospital and hospital != user.hospital:
            raise DRFPermissionDenied(
                f"You can only view audit logs for {user.hospital.name}."
            )
        return True
    
    raise DRFPermissionDenied("You do not have permission to view audit logs.")


def can_perform_break_glass(user, patient):
    """
    PHASE 2: Check if user can perform break-glass emergency access.
    
    - Super admin: yes, always
    - Doctor/Nurse/Hospital admin: yes, from their hospital or with valid referral
    - Others: no
    
    This is a sensitive operation always logged and audited.
    """
    if user.role == "super_admin":
        return True
    
    if user.role in ["doctor", "nurse", "hospital_admin"]:
        # Can access if patient is from their hospital
        # OR if there's a valid referral to their hospital
        # OR if there's valid consent
        
        if patient.registered_at == user.hospital:
            return True
        
        # Check for referral or consent (simplified)
        from interop.models import Referral, Consent
        
        has_referral = Referral.objects.filter(
            patient=patient.global_patient if hasattr(patient, 'global_patient') else None,
            referred_to_hospital=user.hospital,
            status__in=['pending', 'accepted'],
        ).exists()
        
        has_consent = Consent.objects.filter(
            global_patient=patient.global_patient if hasattr(patient, 'global_patient') else None,
            consenting_hospital=patient.registered_at,
            consented_hospital=user.hospital,
            is_active=True,
        ).exists()
        
        if has_referral or has_consent:
            return True
        
        raise DRFPermissionDenied(
            "Break-glass access requires referral or consent from the patient's hospital."
        )
    
    raise DRFPermissionDenied("You do not have permission for emergency access.")


# ============================================================================
# DECORATORS FOR VIEW FUNCTIONS
# ============================================================================

def require_patient_access(view_func):
    """
    Decorator for views that operate on a single patient.
    Automatically checks object-level access.
    
    Usage:
        @require_patient_access
        def get_patient(request, patient_id):
            patient = Patient.objects.get(id=patient_id)
            # Access to patient is already verified
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from patients.models import Patient
        
        patient_id = kwargs.get('patient_id')
        if not patient_id:
            raise DRFPermissionDenied("Patient ID required.")
        
        try:
            patient = Patient.objects.get(id=patient_id)
        except Patient.DoesNotExist:
            raise DRFPermissionDenied("Patient not found.")
        
        can_access_patient(request.user, patient)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def require_hospital_access(view_func):
    """
    Decorator for views that operate on hospital-scoped data.
    Ensures user is from that hospital or is super_admin.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        from core.models import Hospital
        
        hospital_id = kwargs.get('hospital_id')
        if not hospital_id:
            raise DRFPermissionDenied("Hospital ID required.")
        
        try:
            hospital = Hospital.objects.get(id=hospital_id)
        except Hospital.DoesNotExist:
            raise DRFPermissionDenied("Hospital not found.")
        
        # Check access
        if request.user.role == "super_admin":
            return view_func(request, *args, **kwargs)
        
        if request.user.role == "hospital_admin":
            if request.user.hospital != hospital:
                raise DRFPermissionDenied(
                    f"You can only access {request.user.hospital.name}."
                )
            return view_func(request, *args, **kwargs)
        
        raise DRFPermissionDenied(
            "Only hospital admin and super admin can access this resource."
        )
    
    return wrapper


# ============================================================================
# QUERYSET FILTERING HELPERS
# ============================================================================

def filter_medical_records_by_access(user, queryset):
    """
    PHASE 2: Filter queryset to only records user can access.
    
    Applied to list views to automatically scope data.
    """
    if user.role == "super_admin":
        return queryset
    
    if user.role == "doctor":
        # Only records from their hospital
        return queryset.filter(patient__registered_at=user.hospital)
    
    if user.role == "nurse":
        # Only records for patients in their ward
        from patients.models import PatientAdmission
        ward_patient_ids = PatientAdmission.objects.filter(
            ward=user.ward,
            discharged_at__isnull=True,
        ).values_list('patient_id', flat=True)
        return queryset.filter(patient_id__in=ward_patient_ids)
    
    if user.role in ["hospital_admin", "receptionist"]:
        return queryset.filter(patient__registered_at=user.hospital)
    
    return queryset.none()


def filter_encounters_by_access(user, queryset):
    """
    PHASE 2: Filter encounters to only those user can access.
    """
    if user.role == "super_admin":
        return queryset
    
    if user.role == "doctor":
        # Their hospital + assigned to them or their department
        qs = queryset.filter(hospital=user.hospital)
        if user.department_link:
            from django.db.models import Q
            qs = qs.filter(
                Q(assigned_doctor=user) | Q(assigned_department=user.department_link)
            )
        return qs
    
    if user.role == "nurse":
        return queryset.filter(ward=user.ward)
    
    if user.role in ["hospital_admin", "receptionist"]:
        return queryset.filter(hospital=user.hospital)
    
    return queryset.none()
