"""
FHIR R4 API for MedSync Interoperability
- GET /fhir/Patient/<id> — Individual patient resource
- GET /fhir/Patient/<id>/$everything — Full Bundle with all clinical data
- GET /fhir/Encounter/<id> — Individual encounter
- GET /fhir/Condition/<id> — Individual diagnosis/condition
- GET /fhir/MedicationRequest/<id> — Individual prescription
- GET /fhir/Observation/<id> — Individual vital/lab observation
- GET /fhir/DiagnosticReport/<id> — Lab order with results

All endpoints enforce consent-based access for cross-facility reads.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from django.db.models import Q

from patients.models import Patient, PatientAdmission
from records.models import Encounter, Diagnosis, Prescription, Vital, LabOrder, LabResult
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
from interop.models import Consent, Referral

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
            is_active=True
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
                referred_to_hospital=request.user.hospital,
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
        pass
    
    # If SUMMARY scope, return only patient demographics
    if consent_scope == "SUMMARY":
        bundle = FHIRBundleSerializer.serialize(entries, bundle_type="document", total=len(entries))
        AuditLog.log_action(
            user=request.user,
            action="VIEW",
            resource_type="Patient",
            resource_id=str(patient.id),
            details=f"FHIR $everything export (SUMMARY scope)"
        )
        return bundle, consent_scope, None
    
    # FULL_RECORD: Include all clinical data
    try:
        # Encounters
        for enc in Encounter.objects.filter(patient=patient).order_by('-encounter_date')[:100]:
            try:
                entries.append(FHIREncounterSerializer.serialize(enc))
            except Exception:
                pass
        
        # Conditions (Diagnoses)
        for diag in Diagnosis.objects.filter(record__patient=patient).select_related('record').order_by('-record__created_at')[:100]:
            try:
                entries.append(FHIRConditionSerializer.serialize(diag))
            except Exception:
                pass
        
        # Prescriptions
        for rx in Prescription.objects.filter(record__patient=patient).select_related('record').order_by('-record__created_at')[:100]:
            try:
                entries.append(FHIRMedicationRequestSerializer.serialize(rx))
            except Exception:
                pass
        
        # Vitals
        for vital in Vital.objects.filter(record__patient=patient).select_related('record').order_by('-record__created_at')[:100]:
            try:
                entries.append(FHIRObservationSerializer.serialize_vital(vital))
            except Exception:
                pass
        
        # Lab Results
        for lab_result in LabResult.objects.filter(record__patient=patient).select_related('record').order_by('-result_date')[:100]:
            try:
                entries.append(FHIRObservationSerializer.serialize_lab_result(lab_result))
            except Exception:
                pass
        
        # Diagnostic Reports (Lab Orders)
        for lab_order in LabOrder.objects.filter(record__patient=patient).select_related('record').order_by('-created_at')[:100]:
            try:
                # Get associated results
                results = LabResult.objects.filter(lab_order=lab_order)
                entries.append(FHIRDiagnosticReportSerializer.serialize(lab_order, results=results))
            except Exception:
                pass
    
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
def fhir_patient_read(request, pk):
    """GET /fhir/Patient/<id> - Individual patient resource."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "forbidden"}]},
            status=status.HTTP_403_FORBIDDEN
        )
    
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
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
                details=f"Pushed {resource_type} to {target_url}"
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
    conditions = get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
    
    if patient_id:
        conditions = conditions.filter(patient_id=patient_id)
    
    entries = []
    for mr in conditions[:100]:
        diag = Diagnosis.objects.filter(record=mr).first()
        if diag:
            resource = FHIRConditionSerializer.serialize(diag)
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Condition/{diag.id}",
                "resource": resource,
                "search": {"mode": "match"}
            })
    
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": conditions.count(),
        "entry": entries
    }
    
    return Response(bundle, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fhir_medication_request_list(request):
    """GET /fhir/MedicationRequest — List prescriptions as FHIR Bundle searchset."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Filter by patient if provided
    patient_id = request.query_params.get('patient')
    rx_records = get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
    
    if patient_id:
        rx_records = rx_records.filter(patient_id=patient_id)
    
    entries = []
    for mr in rx_records[:100]:
        rx = Prescription.objects.filter(record=mr).first()
        if rx:
            resource = FHIRMedicationRequestSerializer.serialize(rx)
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/MedicationRequest/{rx.id}",
                "resource": resource,
                "search": {"mode": "match"}
            })
    
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": rx_records.count(),
        "entry": entries
    }
    
    return Response(bundle, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fhir_observation_list(request):
    """GET /fhir/Observation — List observations as FHIR Bundle searchset."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Insufficient permissions"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    # Filter by patient if provided
    patient_id = request.query_params.get('patient')
    vital_records = get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
    lab_records = get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
    
    if patient_id:
        vital_records = vital_records.filter(patient_id=patient_id)
        lab_records = lab_records.filter(patient_id=patient_id)
    
    entries = []
    
    # Add vitals
    for mr in vital_records[:50]:
        vital = Vital.objects.filter(record=mr).first()
        if vital:
            resource = FHIRObservationSerializer.serialize_vital(vital)
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Observation/{vital.id}",
                "resource": resource,
                "search": {"mode": "match"}
            })
    
    # Add lab results
    for mr in lab_records[:50]:
        lab_result = LabResult.objects.filter(record=mr).first()
        if lab_result:
            resource = FHIRObservationSerializer.serialize_lab_result(lab_result)
            entries.append({
                "fullUrl": f"http://{request.get_host()}/api/v1/fhir/Observation/{lab_result.id}",
                "resource": resource,
                "search": {"mode": "match"}
            })
    
    bundle = {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": entries
    }
    
    return Response(bundle, status=status.HTTP_200_OK)
