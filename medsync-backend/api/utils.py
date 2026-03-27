"""
Hospital-scoped data access helpers.
Super_admin with no hospital sees all; others restricted to request.user.hospital.
"""

# Audit log: never store PHI or raw tokens in resource_id. Use only opaque IDs (e.g. UUIDs).
AUDIT_RESOURCE_ID_MAX_LEN = 64


def sanitize_audit_resource_id(resource_id):
    """Redact resource_id if it could be a token or PHI. Call before writing to AuditLog."""
    if resource_id is None:
        return None
    s = str(resource_id).strip()
    if len(s) > AUDIT_RESOURCE_ID_MAX_LEN:
        return "[REDACTED]"
    return s


def get_client_ip(request):
    """Extract client IP address from request, accounting for proxies."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "")
    return ip


import hashlib
import uuid
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from core.models import AuditLog, Hospital
from patients.models import Patient, PatientAdmission
# Patient-facing encounter list: records.Encounter (patient, hospital).
# Interop/HIE: interop.Encounter (facility_patient, facility).
from records.models import MedicalRecord, LabOrder, LabResult, Encounter
from interop.models import GlobalPatient, Consent, BreakGlassLog, Referral

VIEW_AS_HOSPITAL_HEADER = "HTTP_X_VIEW_AS_HOSPITAL"


def get_effective_hospital(request):
    """
    For super_admin with no hospital: if request has X-View-As-Hospital header with a valid
    active hospital ID, return that hospital (and audit log once per request). Otherwise None.
    Non-super_admin or super_admin with a hospital: always return None (header ignored).
    
    ⚠️  SECURITY: Enforces SuperAdminHospitalAccess - super_admin can only view hospitals
    they are explicitly granted access to.
    """
    if not getattr(request, "user", None) or not request.user.is_authenticated:
        return None
    user = request.user
    if user.role != "super_admin" or user.hospital_id is not None:
        return None
    if getattr(request, "_effective_hospital_computed", False):
        return getattr(request, "effective_hospital", None)
    request._effective_hospital_computed = True
    request.effective_hospital = None
    raw = request.META.get(VIEW_AS_HOSPITAL_HEADER) or getattr(request, "headers", {}).get("X-View-As-Hospital")
    if not raw:
        return None
    try:
        hid = uuid.UUID(str(raw).strip())
    except (ValueError, TypeError):
        return None
    hospital = Hospital.objects.filter(id=hid, is_active=True).first()
    if not hospital:
        return None
    
    # ⚠️  SECURITY: Check if super_admin has access to this hospital
    from core.models import SuperAdminHospitalAccess
    from django.core.exceptions import PermissionDenied
    
    access = (
        SuperAdminHospitalAccess.objects.select_related("hospital")
        .filter(super_admin=user, hospital=hospital)
        .first()
    )
    has_access = bool(access) and hospital.is_active
    
    if not has_access:
        # Log the unauthorized access attempt
        audit_log(
            user,
            "VIEW_AS_HOSPITAL",
            resource_type="Hospital",
            resource_id=hospital.id,
            hospital=hospital,
            request=request,
            extra_data={
                "view_as_hospital_id": str(hospital.id),
                "view_as_hospital_name": hospital.name,
                "access_denied": True,
            },
        )
        raise PermissionDenied(f"Access to hospital {hid} not granted for super_admin {user.email}")
    
    request.effective_hospital = hospital
    # Mark grant accepted on first use (for dashboard pending-grants UI)
    if access and getattr(access, "accepted_at", None) is None:
        try:
            access.accepted_at = timezone.now()
            access.save(update_fields=["accepted_at"])
        except Exception:
            pass
    audit_log(
        user,
        "VIEW_AS_HOSPITAL",
        resource_type="Hospital",
        resource_id=hospital.id,
        hospital=hospital,
        request=request,
        extra_data={"view_as_hospital_id": str(hospital.id), "view_as_hospital_name": hospital.name},
    )
    return hospital


def get_request_hospital(request):
    """Hospital to use for this request: view-as when set for super_admin, else user's hospital. Use for scoping and for create/update."""
    eff = get_effective_hospital(request)
    if eff is not None:
        return eff
    if getattr(request, "user", None) and request.user.is_authenticated:
        return getattr(request.user, "hospital", None)
    return None


def _scope_hospital(user, effective_hospital):
    """Hospital to use for scoping: view-as for super_admin, else user's hospital."""
    if effective_hospital is not None and user.role == "super_admin" and user.hospital_id is None:
        return effective_hospital
    return user.hospital if user.hospital_id else None


def get_patient_queryset(user, effective_hospital=None):
    """
    Patients the user is allowed to see.
    
    PHASE 1: Multi-tenancy enforcement (Task 4)
    - Super_admin: all or effective_hospital when view-as.
    - Doctor: RESTRICTED to own hospital (HIPAA compliance, not system-wide)
    - Hospital_admin/Receptionist: own hospital.
    - Nurse: ward-admitted patients in own hospital only.
    - Lab_technician: patients with pending lab orders in their lab unit only.
    """
    qs = Patient.objects.all()
    hospital = _scope_hospital(user, effective_hospital)
    if user.role == "super_admin" and user.hospital_id is None and hospital is None:
        return qs
    if user.role == "doctor":
        # PHASE 1 FIXED: Restrict doctors to their own hospital (not system-wide)
        # This prevents cross-hospital data leakage and ensures HIPAA compliance
        if hospital:
            return qs.filter(registered_at=hospital)
        return qs.none()
    if user.role == "nurse" and user.ward_id:
        return qs.filter(
            id__in=PatientAdmission.objects.filter(
                ward=user.ward,
                discharged_at__isnull=True,
            ).values_list("patient_id", flat=True)
        )
    if user.role == "lab_technician":
        # Lab technicians can see only patients who currently have pending lab
        # orders in their assigned lab unit. This avoids over-broad access while
        # still enabling necessary workflow.
        from records.models import LabOrder

        if not getattr(user, "lab_unit_id", None):
            return qs.none()

        pending_patient_ids = LabOrder.objects.filter(
            lab_unit=user.lab_unit,
            result_submitted=False,
        ).values_list("record__patient_id", flat=True)

        return qs.filter(id__in=pending_patient_ids)
    if hospital:
        return qs.filter(registered_at=hospital)
    return qs.none()


def get_encounter_queryset(user, patient=None, effective_hospital=None):
    """Encounters scoped by hospital; optionally for one patient."""
    qs = Encounter.objects.all()
    hospital = _scope_hospital(user, effective_hospital)
    if user.role == "super_admin" and user.hospital_id is None and hospital is None:
        if patient is not None:
            return qs.filter(patient=patient)
        return qs
    if hospital:
        qs = qs.filter(hospital=hospital)
        if patient is not None:
            qs = qs.filter(patient=patient)
        return qs
    return qs.none()


def get_worklist_encounter_queryset(user, effective_hospital=None):
    """Encounters for doctor/nurse worklist. When view-as, super_admin sees that hospital's worklist (no department filter)."""
    hospital = _scope_hospital(user, effective_hospital)
    if not hospital:
        return Encounter.objects.none()
    qs = Encounter.objects.filter(
        hospital=hospital,
        status__in=("waiting", "in_consultation"),
    ).select_related("patient", "assigned_department", "assigned_doctor", "created_by")
    if user.role == "doctor" and not effective_hospital:
        qs = qs.filter(
            Q(assigned_doctor=user) | Q(assigned_department=user.department_link)
        )
    elif user.role == "nurse" and user.department_link_id and not effective_hospital:
        qs = qs.filter(assigned_department=user.department_link)
    return qs.order_by("-encounter_date")


def get_medical_record_queryset(user, patient=None, effective_hospital=None):
    """Medical records scoped by hospital; optionally for one patient."""
    qs = MedicalRecord.objects.all()
    hospital = _scope_hospital(user, effective_hospital)
    if user.role == "super_admin" and user.hospital_id is None and hospital is None:
        if patient is not None:
            return qs.filter(patient=patient)
        return qs
    if hospital:
        qs = qs.filter(hospital=hospital)
        if patient is not None:
            qs = qs.filter(patient=patient)
        return qs
    return qs.none()


def get_lab_order_queryset(user, effective_hospital=None):
    """Lab orders scoped by hospital; lab_technician sees only their lab_unit's orders."""
    qs = LabOrder.objects.all()
    hospital = _scope_hospital(user, effective_hospital)
    if user.role == "super_admin" and user.hospital_id is None and hospital is None:
        return qs
    if hospital:
        qs = qs.filter(record__hospital=hospital)
        if user.role == "lab_technician" and user.lab_unit_id and not effective_hospital:
            qs = qs.filter(lab_unit=user.lab_unit)
        return qs
    return qs.none()


def get_lab_result_queryset(user, effective_hospital=None):
    """Lab results scoped by hospital."""
    qs = LabResult.objects.all()
    hospital = _scope_hospital(user, effective_hospital)
    if user.role == "super_admin" and user.hospital_id is None and hospital is None:
        return qs
    if hospital:
        return qs.filter(record__hospital=hospital)
    return qs.none()


# ---- Interop: global patient and cross-facility access ----

# Break-glass access is considered valid for this many minutes after logging.
BREAK_GLASS_VALID_MINUTES = 15


def get_global_patient_queryset(user, effective_hospital=None):
    """GlobalPatients the user is allowed to see in search.
    Super_admin sees all or effective_hospital's links when view-as.
    """
    from interop.models import FacilityPatient

    qs = GlobalPatient.objects.all()
    hospital = _scope_hospital(user, effective_hospital)
    if user.role == "super_admin" and user.hospital_id is None and hospital is None:
        return qs
    if hospital:
        facility_patient_ids = FacilityPatient.objects.filter(
            facility=hospital, deleted_at__isnull=True
        ).values_list("global_patient_id", flat=True)
        return qs.filter(id__in=facility_patient_ids)
    return qs.none()


def can_access_cross_facility(user, global_patient_id, allow_break_glass=True, effective_hospital=None):
    """Check if user's facility may view this global patient's cross-facility data.
    Order: (0) super_admin with no facility = full access, (1) active consent, (2) accepted referral, (3) recent break-glass.
    Returns (allowed: bool, scope: str or None). scope is SUMMARY or FULL_RECORD.
    """
    try:
        gp = GlobalPatient.objects.get(id=global_patient_id)
    except GlobalPatient.DoesNotExist:
        return False, None

    facility = _scope_hospital(user, effective_hospital) or user.hospital
    if user.role == "super_admin" and not user.hospital_id and facility is None:
        return True, Consent.SCOPE_FULL_RECORD

    if not facility:
        return False, None

    now = timezone.now()

    # 1) Active consent for this facility
    consent = (
        Consent.objects.filter(
            global_patient=gp,
            granted_to_facility=facility,
            is_active=True,
        )
        .filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        .order_by("-created_at")
        .first()
    )
    if consent:
        return True, consent.scope

    # 2) Accepted referral to user's facility (grants SUMMARY only)
    if Referral.objects.filter(
        global_patient=gp,
        to_facility=facility,
        status__in=(Referral.STATUS_ACCEPTED, Referral.STATUS_COMPLETED),
    ).exists():
        return True, Consent.SCOPE_SUMMARY

    # 3) Recent break-glass by this user for this patient (FULL_RECORD)
    if allow_break_glass:
        cutoff = now - timedelta(minutes=BREAK_GLASS_VALID_MINUTES)
        if BreakGlassLog.objects.filter(
            global_patient=gp,
            facility=facility,
            accessed_by=user,
            created_at__gte=cutoff,
        ).exists():
            return True, Consent.SCOPE_FULL_RECORD

    return False, None


def get_hospital_for_super_admin_override(request, data):
    """
    Extract hospital from request for super_admin override, or from data dict.
    
    This consolidates the 5+ duplicate hospital override patterns throughout admin_views.py.
    
    Super_admin can override to any hospital via request data (hospital_id).
    Hospital_admin always uses their assigned hospital (cannot override).
    Other roles use their assigned hospital or raise error.
    
    Args:
        request: HttpRequest with authenticated user
        data: Request data dict (may contain hospital_id for super_admin)
    
    Returns:
        Hospital instance
        
    Raises:
        Http404: If requested hospital doesn't exist
        ValueError: If user has no hospital and isn't super_admin
    
    ⚠️  SECURITY: Only super_admin can override. Hospital_admin is scoped to their hospital.
    """
    from django.http import Http404
    
    user = request.user
    hospital = get_request_hospital(request)
    
    # If super_admin and trying to override hospital context
    if user.role == "super_admin" and not hospital:
        hospital_id = data.get("hospital_id")
        if hospital_id:
            try:
                return Hospital.objects.get(id=hospital_id)
            except Hospital.DoesNotExist:
                raise Http404("Hospital not found")
    
    if hospital:
        return hospital
    
    # Hospital_admin must have hospital assigned
    if user.role == "hospital_admin":
        raise ValueError("Hospital_admin must have hospital assigned")
    
    return hospital


def audit_log(user, action, resource_type=None, resource_id=None, hospital=None, request=None, extra_data=None):
    """
    Create a chained audit log entry with tamper-evident chain hashing.
    
    This is the single source of truth for audit logging across the system.
    Previously had duplicate implementations in admin_views.py and auth_views.py.
    
    Args:
        user: User performing the action
        action: Action name (e.g., "INVITE_USER", "LOGIN", "DELETE_RECORD")
        resource_type: Type of resource affected (optional, e.g., "user", "patient")
        resource_id: ID of resource affected (must be opaque, never PHI or tokens)
        hospital: Hospital context (optional)
        request: HttpRequest for IP and user agent (optional)
        extra_data: Additional JSON-serializable data to log (optional)
    
    Returns:
        None (creates AuditLog object as side effect)
    
    ⚠️  SECURITY: Never pass PHI or raw tokens in resource_id. Use sanitize_audit_resource_id().
    """
    resource_id = sanitize_audit_resource_id(resource_id)
    ip = request.META.get("REMOTE_ADDR", "127.0.0.1") if request else "127.0.0.1"
    ua = (request.META.get("HTTP_USER_AGENT") or "") if request else ""
    AuditLog.objects.create(
        user=user,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        hospital=hospital,
        ip_address=ip,
        user_agent=ua,
        extra_data=extra_data,
    )


def register_task_submission(celery_task_id, user, task_type="other", resource_type=None, resource_id=None, hospital=None, request=None):
    """
    Register a Celery task submission for tracking and permission checks.
    
    Call this after submitting a task to Celery to enable status/result endpoint access.
    
    Args:
        celery_task_id: ID returned by task.apply_async()
        user: User who submitted the task
        task_type: Task type identifier (export_pdf, ai_analysis, etc.)
        resource_type: Type of resource being operated on (patient, encounter, etc.)
        resource_id: ID of the resource being operated on
        hospital: Hospital context for the task
        request: Request object for IP/user-agent logging
    
    Returns:
        TaskSubmission instance
    """
    from core.models import TaskSubmission
    from datetime import timedelta
    
    ip = get_client_ip(request) if request else None
    ua = request.META.get("HTTP_USER_AGENT", "") if request else ""
    
    expires_at = timezone.now() + timedelta(hours=1)  # Results expire after 1 hour
    
    task_submission = TaskSubmission.objects.create(
        celery_task_id=celery_task_id,
        user=user,
        hospital=hospital,
        task_type=task_type,
        resource_type=resource_type,
        resource_id=sanitize_audit_resource_id(resource_id),
        submitted_at=timezone.now(),
        expires_at=expires_at,
        ip_address=ip,
        user_agent=ua,
    )
    
    return task_submission
