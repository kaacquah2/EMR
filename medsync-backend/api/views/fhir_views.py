"""
FHIR R4 API for MedSync Interoperability
- GET  /fhir/Patient/<id>                  — Individual patient resource
- GET  /fhir/Patient/<id>/$everything      — Full Bundle with all clinical data
- GET  /fhir/Encounter/<id>                — Individual encounter
- GET  /fhir/Condition/<id>                — Individual diagnosis/condition
- GET  /fhir/MedicationRequest/<id>        — Individual prescription
- POST /fhir/MedicationRequest             — Create prescription from FHIR resource
- GET  /fhir/Observation/<id>              — Individual vital/lab observation
- POST /fhir/Observation                   — Create vital signs from FHIR resource
- GET  /fhir/DiagnosticReport/<id>         — Lab order with results

All endpoints enforce consent-based access for cross-facility reads.
Write endpoints require doctor or hospital_admin role within the same facility.
"""

import logging
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q

from django.db import transaction
from core.models import AuditLog
from patients.models import Patient, PatientAdmission
from records.models import Encounter, Diagnosis, Prescription, Vital, LabOrder, LabResult
from records.models.base import MedicalRecord
from api.fhir.serializers import (
    FHIRPatientSerializer,
    FHIREncounterSerializer,
    FHIRConditionSerializer,
    FHIRMedicationRequestSerializer,
    FHIRObservationSerializer,
    FHIRDiagnosticReportSerializer,
    FHIRBundleSerializer,
)
from api.utils import (
    get_patient_queryset,
    get_encounter_queryset,
    get_medical_record_queryset,
    get_effective_hospital,
)
from api.audit_logging import audit_log_extended
from api.decorators import requires_step_up
from interop.models import Consent, Referral

logger = logging.getLogger(__name__)

_FHIR_ALLOWED_ROLES = (
    "super_admin", "hospital_admin", "doctor", "nurse", "receptionist"
)


def _can_access_patient_fhir(request, patient):
    """
    Check if user can access patient via FHIR.
    Enforces hospital scoping and cross-facility consent rules.
    """
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return False, "Role not authorized for FHIR access"
    
    # Same hospital = automatic access
    if patient.registered_at == request.user.hospital or request.user.role == "super_admin":
        return True, None
    
    # Cross-facility: check consent or referral
    if request.user.role in ["doctor", "nurse", "hospital_admin"]:
        # Check if there's valid consent
        valid_consent = Consent.objects.filter(
            global_patient__facility_profiles__patient=patient,
            granted_to_facility=request.user.hospital,
            is_active=True,
            withdrawn_at__isnull=True,
        ).exclude(
            expires_at__lt=timezone.now()
        ).first()
        
        if valid_consent:
            return True, valid_consent.scope  # Return scope (SUMMARY or FULL_RECORD)
        
        # Check if there's a referral
        from interop.models import GlobalPatient
        try:
            gp = GlobalPatient.objects.get(facility_profiles__patient=patient)
            referral = Referral.objects.filter(
                global_patient=gp,
                to_facility=request.user.hospital,
                status__in=['PENDING', 'ACCEPTED']
            ).first()
            if referral:
                return True, "FULL_RECORD"
        except GlobalPatient.DoesNotExist:
            pass
        
        return False, "No consent or referral for cross-facility access"
    
    return False, "Access denied"


def _build_everything_bundle(request, patient):
    """
    Build a complete FHIR Bundle containing all of a patient's clinical data.
    Returns (bundle, consent_scope, error_message).
    """
    can_access, scope_or_error = _can_access_patient_fhir(request, patient)
    if not can_access:
        return None, None, scope_or_error
    
    consent_scope = scope_or_error if scope_or_error in ["SUMMARY", "FULL_RECORD"] else "FULL_RECORD"
    
    entries = []
    
    # Patient (always include)
    try:
        patient_resource = FHIRPatientSerializer.serialize(patient)
        entries.append(patient_resource)
    except Exception as e:
        logger.error(f"Failed to serialize FHIR Patient {patient.id}: {e}", exc_info=True)
    
    # If SUMMARY scope, return only patient demographics
    if consent_scope == "SUMMARY":
        bundle = FHIRBundleSerializer.serialize(entries, bundle_type="document", total=len(entries))
        AuditLog.log_action(
            user=request.user,
            action="VIEW",
            resource_type="Patient",
            resource_id=str(patient.id),
            extra_data={"note": "FHIR $everything export (SUMMARY scope)"},
        )
        return bundle, consent_scope, None
    
    # FULL_RECORD: Include all clinical data
    try:
        # Encounters
        for enc in Encounter.objects.filter(patient=patient).order_by('-encounter_date')[:100]:
            try:
                entries.append(FHIREncounterSerializer.serialize(enc))
            except Exception as e:
                logger.error(f"Failed to serialize FHIR Encounter {enc.id}: {e}", exc_info=True)
        
        # Conditions (Diagnoses)
        for diag in Diagnosis.objects.filter(record__patient=patient).select_related('record').order_by('-record__created_at')[:100]:
            try:
                entries.append(FHIRConditionSerializer.serialize(diag))
            except Exception as e:
                logger.error(f"Failed to serialize FHIR Condition for diagnosis {diag.id}: {e}", exc_info=True)
        
        # Prescriptions
        for rx in Prescription.objects.filter(record__patient=patient).select_related('record').order_by('-record__created_at')[:100]:
            try:
                entries.append(FHIRMedicationRequestSerializer.serialize(rx))
            except Exception as e:
                logger.error(f"Failed to serialize FHIR MedicationRequest for prescription {rx.id}: {e}", exc_info=True)
        
        # Vitals
        for vital in Vital.objects.filter(record__patient=patient).select_related('record').order_by('-record__created_at')[:100]:
            try:
                entries.append(FHIRObservationSerializer.serialize_vital(vital))
            except Exception as e:
                logger.error(f"Failed to serialize FHIR Observation for vital {vital.id}: {e}", exc_info=True)
        
        # Lab Results
        for lab_result in LabResult.objects.filter(record__patient=patient).select_related('record').order_by('-result_date')[:100]:
            try:
                entries.append(FHIRObservationSerializer.serialize_lab_result(lab_result))
            except Exception as e:
                logger.error(f"Failed to serialize FHIR Observation for lab result {lab_result.id}: {e}", exc_info=True)
        
        # Diagnostic Reports (Lab Orders)
        for lab_order in LabOrder.objects.filter(record__patient=patient).select_related('record').order_by('-created_at')[:100]:
            try:
                # Get associated results
                results = LabResult.objects.filter(lab_order=lab_order)
                entries.append(FHIRDiagnosticReportSerializer.serialize(lab_order, results=results))
            except Exception as e:
                logger.error(f"Failed to serialize FHIR DiagnosticReport for lab order {lab_order.id}: {e}", exc_info=True)
    
    except Exception as e:
        return None, consent_scope, f"Error building bundle: {str(e)}"
    
    bundle = FHIRBundleSerializer.serialize(entries, bundle_type="document", total=len(entries))
    
    # Audit the export
    audit_log_extended(
        user=request.user,
        action="VIEW",
        resource_type="Patient",
        resource_id=str(patient.id),
        hospital=request.user.hospital if hasattr(request.user, 'hospital') else None,
        request=request,
        extra_data={"reason": f"FHIR $everything export ({consent_scope} scope, {len(entries)} resources)"}
    )
    
    return bundle, consent_scope, None


# ============================================================================
# FHIR Patient Endpoints
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_patient_read(request, pk):
    """GET /fhir/Patient/<id> - Individual patient resource."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        if Patient.objects.filter(id=pk).exists():
            return Response(
                {
                    "resourceType": "OperationOutcome",
                    "issue": [{"severity": "error", "code": "forbidden", "diagnostics": "Cross-facility access denied"}],
                },
                status=status.HTTP_403_FORBIDDEN,
            )
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND
        )

    can_access, error = _can_access_patient_fhir(request, patient)
    if not can_access:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        resource = FHIRPatientSerializer.serialize(patient)
        return Response(resource)
    except Exception as e:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_patient_everything(request, pk):
    """
    GET /fhir/Patient/<id>/$everything
    
    Returns a complete clinical document Bundle containing:
    - Patient demographics
    - All encounters
    - All diagnoses (conditions)
    - All prescriptions (medication requests)
    - All vitals and lab results (observations)
    - All lab orders (diagnostic reports)
    
    Enforces consent-based access for cross-facility reads.
    """
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    patient = Patient.objects.filter(id=pk).first()
    if not patient:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND
        )
    
    bundle, scope, error = _build_everything_bundle(request, patient)
    
    if error:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    response = Response(bundle, content_type="application/fhir+json")
    response['Content-Disposition'] = f'attachment; filename="patient-{patient.id}-$everything.json"'
    return response


# ============================================================================
# FHIR Encounter Endpoints
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_encounter_read(request, pk):
    """GET /fhir/Encounter/<id> - Individual encounter resource."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    enc = Encounter.objects.filter(id=pk).first()
    if not enc:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND
        )
    
    can_access, error = _can_access_patient_fhir(request, enc.patient)
    if not can_access:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        resource = FHIREncounterSerializer.serialize(enc)
        return Response(resource)
    except Exception as e:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# FHIR Condition Endpoints
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_condition_read(request, pk):
    """GET /fhir/Condition/<id> - Individual condition/diagnosis resource."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    diag = Diagnosis.objects.filter(id=pk).select_related('record').first()
    if not diag:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND
        )
    
    can_access, error = _can_access_patient_fhir(request, diag.record.patient)
    if not can_access:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        resource = FHIRConditionSerializer.serialize(diag)
        return Response(resource)
    except Exception as e:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# FHIR MedicationRequest Endpoints
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_medication_request_read(request, pk):
    """GET /fhir/MedicationRequest/<id> - Individual medication request/prescription."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    rx = Prescription.objects.filter(id=pk).select_related('record').first()
    if not rx:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND
        )
    
    can_access, error = _can_access_patient_fhir(request, rx.record.patient)
    if not can_access:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        resource = FHIRMedicationRequestSerializer.serialize(rx)
        return Response(resource)
    except Exception as e:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# FHIR Observation Endpoints
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_observation_read(request, pk):
    """GET /fhir/Observation/<id> - Individual observation (vital or lab result)."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # Try to find as Vital first
    vital = Vital.objects.filter(id=pk).select_related('record').first()
    if vital:
        can_access, error = _can_access_patient_fhir(request, vital.record.patient)
        if not can_access:
            return Response(
                {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            resource = FHIRObservationSerializer.serialize_vital(vital)
            return Response(resource)
        except Exception as e:
            return Response(
                {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    # Try to find as LabResult
    lab_result = LabResult.objects.filter(id=pk).select_related('record').first()
    if lab_result:
        can_access, error = _can_access_patient_fhir(request, lab_result.record.patient)
        if not can_access:
            return Response(
                {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
                status=status.HTTP_403_FORBIDDEN
            )
        try:
            resource = FHIRObservationSerializer.serialize_lab_result(lab_result)
            return Response(resource)
        except Exception as e:
            return Response(
                {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    return Response(
        {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
        status=status.HTTP_404_NOT_FOUND
    )


# ============================================================================
# FHIR DiagnosticReport Endpoints
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
@requires_step_up(action="export_fhir")
def fhir_diagnostic_report_read(request, pk):
    """GET /fhir/DiagnosticReport/<id> - Individual lab order/diagnostic report."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    lab_order = LabOrder.objects.filter(id=pk).select_related('record').first()
    if not lab_order:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND
        )
    
    can_access, error = _can_access_patient_fhir(request, lab_order.record.patient)
    if not can_access:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden", "diagnostics": error}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    try:
        results = LabResult.objects.filter(lab_order=lab_order)
        resource = FHIRDiagnosticReportSerializer.serialize(lab_order, results=results)
        return Response(resource)
    except Exception as e:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception", "diagnostics": str(e)}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


# ============================================================================
# HL7 ADT Export
# ============================================================================

@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hl7_adt_list(request):
    """GET /hl7/adt?patient=<id> - HL7 v2.5 ADT A01 admission message."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    patient_id = request.GET.get("patient")
    if not patient_id:
        return Response({"data": []})
    
    patient = Patient.objects.filter(id=patient_id).first()
    if not patient:
        return Response({"data": []})
    
    can_access, error = _can_access_patient_fhir(request, patient)
    if not can_access:
        return Response({"data": []})
    
    lines = [
        "MSH|^~\\&|MEDSYNC|FACILITY|||20250101000000||ADT^A01|1|P|2.5",
        f"PID|1||{patient.id}||{patient.full_name.replace('^', ' ')}^^{patient.gender or 'U'}|{patient.date_of_birth.isoformat() if patient.date_of_birth else ''}|||{patient.ghana_health_id or ''}^^^GHA^GH",
        "PV1|1|O"
    ]
    return Response({"data": lines, "format": "HL7v2.5 ADT A01"})


# ============================================================================
# FHIR Push (Outbound HIE)
# ============================================================================

def _is_safe_fhir_url(url: str) -> bool:
    import urllib.parse
    import socket
    import ipaddress

    try:
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return False
        
        hostname = parsed.hostname
        if not hostname:
            return False
        
        # Resolve hostname to IP to prevent loopback/private range bypasses
        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            return False
        
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_link_local:
            return False
            
        return True
    except Exception:
        return False


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fhir_push(request):
    """
    POST /interop/fhir-push
    
    Push a FHIR resource to an external URL.
    Body: {target_url, resource_type, resource_id}
    """
    if request.user.role not in ("super_admin", "hospital_admin", "doctor"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    target_url = (request.data.get("target_url") or "").strip()
    resource_type = (request.data.get("resource_type") or "").strip()
    resource_id = request.data.get("resource_id")
    
    if not target_url or not resource_type or not resource_id:
        return Response(
            {"message": "target_url, resource_type, and resource_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # SSRF Validation check
    if not _is_safe_fhir_url(target_url):
        return Response(
            {"message": "Invalid or unsafe target_url. Only public HTTP/HTTPS endpoints are allowed."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    if resource_type not in ("Patient", "Encounter", "Condition", "MedicationRequest", "Observation", "DiagnosticReport"):
        return Response(
            {"message": f"resource_type must be one of: Patient, Encounter, Condition, MedicationRequest, Observation, DiagnosticReport"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    resource = None
    patient = None
    
    try:
        if resource_type == "Patient":
            patient = Patient.objects.filter(id=resource_id).first()
            if patient:
                resource = FHIRPatientSerializer.serialize(patient)
        elif resource_type == "Encounter":
            enc = Encounter.objects.filter(id=resource_id).first()
            if enc:
                patient = enc.patient
                resource = FHIREncounterSerializer.serialize(enc)
        elif resource_type == "Condition":
            diag = Diagnosis.objects.filter(id=resource_id).select_related('record').first()
            if diag:
                patient = diag.record.patient
                resource = FHIRConditionSerializer.serialize(diag)
        elif resource_type == "MedicationRequest":
            rx = Prescription.objects.filter(id=resource_id).select_related('record').first()
            if rx:
                patient = rx.record.patient
                resource = FHIRMedicationRequestSerializer.serialize(rx)
        elif resource_type == "Observation":
            vital = Vital.objects.filter(id=resource_id).select_related('record').first()
            if vital:
                patient = vital.record.patient
                resource = FHIRObservationSerializer.serialize_vital(vital)
            else:
                lab_result = LabResult.objects.filter(id=resource_id).select_related('record').first()
                if lab_result:
                    patient = lab_result.record.patient
                    resource = FHIRObservationSerializer.serialize_lab_result(lab_result)
        elif resource_type == "DiagnosticReport":
            lab_order = LabOrder.objects.filter(id=resource_id).select_related('record').first()
            if lab_order:
                patient = lab_order.record.patient
                results = LabResult.objects.filter(lab_order=lab_order)
                resource = FHIRDiagnosticReportSerializer.serialize(lab_order, results=results)
        
        if not resource or not patient:
            return Response(
                {"message": "Resource not found"},
                status=status.HTTP_404_NOT_FOUND,
            )
        
        # Check access
        can_access, error = _can_access_patient_fhir(request, patient)
        if not can_access:
            return Response(
                {"message": "Access denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        
        # Perform the push
        import json
        import urllib.request
        import urllib.error
        
        data = json.dumps(resource).encode("utf-8")
        req = urllib.request.Request(
            target_url,
            data=data,
            headers={"Content-Type": "application/fhir+json"},
            method="POST",
        )
        
        with urllib.request.urlopen(req, timeout=10) as resp:
            AuditLog.log_action(
                user=request.user,
                action="CREATE",
                resource_type=resource_type,
                resource_id=str(resource_id),
                extra_data={"note": f"Pushed {resource_type} to {target_url}"},
            )
            return Response(
                {"message": "Pushed successfully", "status": resp.status},
                status=status.HTTP_200_OK,
            )
    
    except urllib.error.HTTPError as e:
        return Response(
            {"message": f"Target returned {e.code}", "detail": e.read().decode()[:500]},
            status=status.HTTP_502_BAD_GATEWAY,
        )
    except Exception as e:
        return Response(
            {"message": "Push failed", "detail": str(e)[:200]},
            status=status.HTTP_502_BAD_GATEWAY,
        )


# ============================================================================
# FHIR List Endpoints (searchset bundles)
# ============================================================================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fhir_patient_list(request):
    """GET /fhir/Patient — List patients as FHIR Bundle searchset."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    patients = get_patient_queryset(request.user, get_effective_hospital(request))
    entries = []
    for patient in patients[:100]:  # Limit to 100 for performance
        resource = FHIRPatientSerializer.serialize(patient)
        entries.append({
            "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Patient/{patient.id}",
            "resource": resource,
            "search": {"mode": "match"}
        })
    
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": patients.count(),
        "entry": entries
    }
    
    return Response(bundle, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fhir_encounter_list(request):
    """GET /fhir/Encounter — List encounters as FHIR Bundle searchset."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Filter by patient if provided
    patient_id = request.query_params.get('patient')
    encounters = get_encounter_queryset(request.user, get_effective_hospital(request))
    
    if patient_id:
        encounters = encounters.filter(patient_id=patient_id)
    
    entries = []
    for enc in encounters[:100]:
        resource = FHIREncounterSerializer.serialize(enc)
        entries.append({
            "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Encounter/{enc.id}",
            "resource": resource,
            "search": {"mode": "match"}
        })
    
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": encounters.count(),
        "entry": entries
    }
    
    return Response(bundle, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fhir_condition_list(request):
    """GET /fhir/Condition — List conditions as FHIR Bundle searchset."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Filter by patient if provided
    patient_id = request.query_params.get('patient')
    records = get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
    
    if patient_id:
        records = records.filter(patient_id=patient_id)
    
    diagnoses_qs = Diagnosis.objects.filter(record__in=records)
    total_count = diagnoses_qs.count()
    diagnoses = diagnoses_qs.select_related('record', 'record__patient').order_by('-record__created_at')[:100]
    
    entries = []
    for diag in diagnoses:
        resource = FHIRConditionSerializer.serialize(diag)
        entries.append({
            "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Condition/{diag.id}",
            "resource": resource,
            "search": {"mode": "match"}
        })
    
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": total_count,
        "entry": entries
    }
    
    return Response(bundle, status=status.HTTP_200_OK)


_FHIR_WRITE_ROLES = ("doctor", "hospital_admin", "super_admin")


def _observation_list_body(request):
    """Return a FHIR Bundle searchset of observations for the current user."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

    patient_id = request.query_params.get("patient")
    eff = get_effective_hospital(request)
    vital_records = get_medical_record_queryset(request.user, effective_hospital=eff)
    lab_records   = get_medical_record_queryset(request.user, effective_hospital=eff)
    if patient_id:
        vital_records = vital_records.filter(patient_id=patient_id)
        lab_records   = lab_records.filter(patient_id=patient_id)

    entries = []
    for mr in vital_records[:50]:
        vital = Vital.objects.filter(record=mr).first()
        if vital:
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Observation/{vital.id}",
                "resource": FHIRObservationSerializer.serialize_vital(vital),
                "search": {"mode": "match"},
            })
    for mr in lab_records[:50]:
        lab_result = LabResult.objects.filter(record=mr).first()
        if lab_result:
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Observation/{lab_result.id}",
                "resource": FHIRObservationSerializer.serialize_lab_result(lab_result),
                "search": {"mode": "match"},
            })
    return Response({"resourceType": "Bundle", "type": "searchset",
                     "total": len(entries), "entry": entries})


def _medication_request_list_body(request):
    """Return a FHIR Bundle searchset of prescriptions for the current user."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Insufficient permissions"}, status=status.HTTP_403_FORBIDDEN)

    patient_id = request.query_params.get("patient")
    eff = get_effective_hospital(request)
    rx_records = get_medical_record_queryset(request.user, effective_hospital=eff)
    if patient_id:
        rx_records = rx_records.filter(patient_id=patient_id)

    entries = []
    for mr in rx_records[:100]:
        rx = Prescription.objects.filter(record=mr).first()
        if rx:
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/MedicationRequest/{rx.id}",
                "resource": FHIRMedicationRequestSerializer.serialize(rx),
                "search": {"mode": "match"},
            })
    return Response({"resourceType": "Bundle", "type": "searchset",
                     "total": rx_records.count(), "entry": entries})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def fhir_observation_list_create(request):
    """
    GET  /fhir/Observation  — list observations as FHIR Bundle searchset
    POST /fhir/Observation  — create a vital-signs Observation from FHIR R4
    """
    if request.method == "GET":
        return _observation_list_body(request)
    # POST: delegate to the standalone create handler (no double-wrap — same request object)
    return _fhir_observation_create_body(request)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def fhir_medication_request_list_create(request):
    """
    GET  /fhir/MedicationRequest  — list prescriptions as FHIR Bundle searchset
    POST /fhir/MedicationRequest  — create a prescription from FHIR R4
    """
    if request.method == "GET":
        return _medication_request_list_body(request)
    return _fhir_medication_request_create_body(request)


def _fhir_observation_create_body(request):
    """
    POST /fhir/Observation

    Create a vital-signs Observation from an inbound FHIR R4 resource.
    The subject reference must resolve to a patient in the caller's facility.
    Accepted coding system: LOINC (http://loinc.org).

    Supported components (all optional, at least one required):
      8310-5  body temperature (°C)
      8867-4  heart rate (bpm)
      9279-1  respiratory rate (/min)
      55284-4 blood pressure systolic (mmHg)  — use component
      8480-6  blood pressure systolic  (mmHg)
      8462-4  blood pressure diastolic (mmHg)
      59408-9 O2 saturation (%)
      29463-7 body weight (kg)
      8302-2  body height (cm)
    """
    if request.user.role not in _FHIR_WRITE_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data
    if data.get("resourceType") != "Observation":
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "invalid",
             "diagnostics": "resourceType must be 'Observation'"}]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Resolve patient from subject reference
    subject_ref = (data.get("subject") or {}).get("reference", "")
    patient_id = subject_ref.replace("Patient/", "").strip()
    if not patient_id:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "required",
             "diagnostics": "subject.reference (Patient/<id>) is required"}]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found",
             "diagnostics": f"Patient {patient_id} not found in your facility"}]},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Map LOINC codes → Vital fields
    LOINC_MAP = {
        "8310-5":  "temperature_c",
        "8867-4":  "pulse_bpm",
        "9279-1":  "resp_rate",
        "8480-6":  "bp_systolic",
        "55284-4": "bp_systolic",
        "8462-4":  "bp_diastolic",
        "59408-9": "spo2_percent",
        "29463-7": "weight_kg",
        "8302-2":  "height_cm",
    }

    vital_kwargs: dict = {}

    def _extract_value(comp):
        qty = comp.get("valueQuantity") or {}
        try:
            return float(qty.get("value", 0)) or None
        except (TypeError, ValueError):
            return None

    def _extract_code(comp):
        coding = (comp.get("code") or {}).get("coding") or []
        for c in coding:
            if c.get("system") == "http://loinc.org":
                return c.get("code")
        return None

    # Top-level observation
    top_code = _extract_code(data)
    top_value = _extract_value(data)
    if top_code and top_code in LOINC_MAP and top_value is not None:
        vital_kwargs[LOINC_MAP[top_code]] = top_value

    # Components (e.g. blood pressure panel)
    for comp in data.get("component") or []:
        code = _extract_code(comp)
        val = _extract_value(comp)
        if code and code in LOINC_MAP and val is not None:
            vital_kwargs[LOINC_MAP[code]] = val

    if not vital_kwargs:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "required",
             "diagnostics": "No recognised LOINC-coded vital values found in resource"}]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    hospital = get_effective_hospital(request) or request.user.hospital

    try:
        with transaction.atomic():
            record = MedicalRecord.objects.create(
                patient=patient,
                hospital=hospital,
                record_type="vital_signs",
                created_by=request.user,
            )
            vital = Vital.objects.create(record=record, recorded_by=request.user, **vital_kwargs)
    except Exception as exc:
        logger.error("FHIR Observation create failed: %s", exc, exc_info=True)
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception",
             "diagnostics": "Internal error creating Observation"}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    audit_log_extended(
        user=request.user,
        action="CREATE",
        resource_type="Observation",
        resource_id=str(vital.id),
        hospital=hospital,
        request=request,
        extra_data={"source": "FHIR_write", "patient_id": str(patient.id)},
    )

    resource = FHIRObservationSerializer.serialize_vital(vital)
    return Response(resource, status=status.HTTP_201_CREATED)


def _fhir_medication_request_create_body(request):
    """
    POST /fhir/MedicationRequest

    Create a prescription from an inbound FHIR R4 MedicationRequest resource.
    The subject reference must resolve to a patient in the caller's facility.
    Requires doctor or hospital_admin role.
    """
    if request.user.role not in _FHIR_WRITE_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN,
        )

    data = request.data
    if data.get("resourceType") != "MedicationRequest":
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "invalid",
             "diagnostics": "resourceType must be 'MedicationRequest'"}]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Resolve patient
    subject_ref = (data.get("subject") or {}).get("reference", "")
    patient_id = subject_ref.replace("Patient/", "").strip()
    if not patient_id:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "required",
             "diagnostics": "subject.reference (Patient/<id>) is required"}]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found",
             "diagnostics": f"Patient {patient_id} not found in your facility"}]},
            status=status.HTTP_404_NOT_FOUND,
        )

    # Extract medication name
    med_coding = ((data.get("medicationCodeableConcept") or {}).get("coding") or [{}])[0]
    drug_name = (
        med_coding.get("display")
        or (data.get("medicationCodeableConcept") or {}).get("text")
        or ""
    ).strip()
    if not drug_name:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "required",
             "diagnostics": "medicationCodeableConcept.coding[0].display or .text is required"}]},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Extract dosage instructions
    dosage_instructions = (data.get("dosageInstruction") or [{}])[0]
    dose_qty = (dosage_instructions.get("doseAndRate") or [{}])[0].get("doseQuantity") or {}
    dosage = (
        f"{dose_qty.get('value', '')} {dose_qty.get('unit', '')}".strip()
        or dosage_instructions.get("text")
        or "as directed"
    )
    frequency = (
        (dosage_instructions.get("timing") or {}).get("code", {}).get("text")
        or dosage_instructions.get("text")
        or "as directed"
    )
    route_text = (dosage_instructions.get("route") or {}).get("text", "oral").lower()
    route_map = {"intravenous": "iv", "intramuscular": "im", "topical": "topical", "inhalation": "inhalation"}
    route = route_map.get(route_text, "oral")

    duration_days = None
    bounds = (dosage_instructions.get("timing") or {}).get("repeat", {}).get("boundsDuration") or {}
    if bounds.get("unit") == "d" and bounds.get("value"):
        try:
            duration_days = int(bounds["value"])
        except (TypeError, ValueError):
            pass

    priority_raw = (data.get("priority") or "routine").lower()
    priority = priority_raw if priority_raw in ("routine", "urgent", "stat") else "routine"

    hospital = get_effective_hospital(request) or request.user.hospital

    try:
        with transaction.atomic():
            record = MedicalRecord.objects.create(
                patient=patient,
                hospital=hospital,
                record_type="prescription",
                created_by=request.user,
            )
            rx = Prescription.objects.create(
                record=record,
                patient=patient,
                hospital=hospital,
                drug_name=drug_name,
                dosage=dosage,
                frequency=frequency,
                route=route,
                duration_days=duration_days,
                priority=priority,
                dispense_status="pending",
                status="pending",
            )
    except Exception as exc:
        logger.error("FHIR MedicationRequest create failed: %s", exc, exc_info=True)
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "exception",
             "diagnostics": "Internal error creating MedicationRequest"}]},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    audit_log_extended(
        user=request.user,
        action="CREATE",
        resource_type="MedicationRequest",
        resource_id=str(rx.id),
        hospital=hospital,
        request=request,
        extra_data={"source": "FHIR_write", "patient_id": str(patient.id), "drug": drug_name},
    )

    resource = FHIRMedicationRequestSerializer.serialize(rx)
    return Response(resource, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_capability_statement(request):
    """
    FHIR R4 CapabilityStatement (mandatory metadata for partner discovery).
    GET /api/v1/fhir/metadata
    """
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {
                "resourceType": "OperationOutcome",
                "issue": [{"severity": "error", "code": "forbidden"}],
            },
            status=status.HTTP_403_FORBIDDEN,
        )

    base = request.build_absolute_uri("/api/v1/fhir").rstrip("/")
    now = timezone.now().isoformat()

    resources = [
        ("Patient", ["read"], [{"name": "everything", "definition": f"{base}/Patient/{{id}}/$everything"}]),
        ("Encounter", ["read"], []),
        ("Condition", ["read"], []),
        ("MedicationRequest", ["read", "create"], []),
        ("Observation", ["read", "create"], []),
        ("DiagnosticReport", ["read"], []),
        ("Bundle", ["read"], []),
        ("CapabilityStatement", ["read"], []),
    ]

    statement = {
        "resourceType": "CapabilityStatement",
        "id": "medsync",
        "url": f"{base}/metadata",
        "version": "1.0.0",
        "name": "MedSyncEMR",
        "title": "MedSync EMR FHIR R4 Server",
        "status": "active",
        "date": now,
        "publisher": "MedSync",
        "description": "Inter-hospital EMR FHIR read API for Ghana health facilities.",
        "kind": "instance",
        "software": {"name": "MedSync", "version": "1.0"},
        "implementation": {"description": "MedSync Django REST FHIR layer", "url": base},
        "fhirVersion": "4.0.1",
        "format": ["json"],
        "rest": [
            {
                "mode": "server",
                "documentation": "Read-only FHIR R4 resources with consent enforcement.",
                "security": {
                    "service": [
                        {
                            "coding": [
                                {
                                    "system": "http://hl7.org/fhir/restful-security-service",
                                    "code": "OAuth",
                                }
                            ]
                        }
                    ],
                    "description": "JWT bearer authentication via MedSync API.",
                },
                "resource": [
                    {
                        "type": rtype,
                        "interaction": [{"code": code} for code in interactions],
                        **({"operation": operations} if operations else {}),
                        "versioning": "no-version",
                        "readHistory": False,
                    }
                    for rtype, interactions, operations in resources
                ],
            }
        ],
    }
    return Response(statement, status=status.HTTP_200_OK)
