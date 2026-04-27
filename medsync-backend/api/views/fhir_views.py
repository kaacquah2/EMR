"""
FHIR R4-style API for interoperability.
- Patient: GET /fhir/Patient, GET /fhir/Patient/<id>
- Encounter: GET /fhir/Encounter?patient=<id>, GET /fhir/Encounter/<id>
- Condition: GET /fhir/Condition?patient=<id>, GET /fhir/Condition/<id>
- MedicationRequest: GET /fhir/MedicationRequest?patient=<id>, GET /fhir/MedicationRequest/<id>
- Observation: GET /fhir/Observation?patient=<id>, GET /fhir/Observation/<id>
HL7: GET /hl7/adt?patient=<id> returns pipe-delimited ADT-style patient list.
Scoped by facility; requires authentication.
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from records.models import Diagnosis, Prescription, Vital
from api.utils import (
    get_patient_queryset,
    get_encounter_queryset,
    get_medical_record_queryset,
    get_effective_hospital,
)

_FHIR_ALLOWED_ROLES = (
    "super_admin", "hospital_admin", "doctor", "nurse", "receptionist"
)


def _patient_to_fhir(patient):
    """Map internal Patient to FHIR R4 Patient resource (minimal)."""
    return {
        "resourceType": "Patient",
        "id": str(patient.id),
        "identifier": [
            {"system": "https://ghanahealth.org/ghana-health-id", "value": patient.ghana_health_id},
        ],
        "name": [{"use": "official", "text": patient.full_name}],
        "gender": patient.gender if patient.gender != "unknown" else "unknown",
        "birthDate": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
        "telecom": [{"system": "phone", "value": patient.phone}] if patient.phone else [],
    }


def _encounter_to_fhir(enc):
    """Map records.Encounter to FHIR R4 Encounter (minimal)."""
    return {
        "resourceType": "Encounter",
        "id": str(enc.id),
        "status": "finished",
        "class": {"system": "http://terminology.hl7.org/CodeSystem/v3-ActCode", "code": enc.encounter_type},
        "type": [{"text": enc.encounter_type}],
        "subject": {"reference": f"Patient/{enc.patient_id}"},
        "period": {"start": enc.encounter_date.isoformat()},
        "reasonCode": [{"text": enc.notes}] if enc.notes else [],
    }


def _diagnosis_to_fhir(diagnosis):
    """Map records.Diagnosis to FHIR R4 Condition (minimal)."""
    rec = diagnosis.record
    return {
        "resourceType": "Condition",
        "id": str(diagnosis.id),
        "clinicalStatus": {"coding": [{"code": "active"}]},
        "code": {
            "coding": [
                {
                    "system": "http://hl7.org/fhir/sid/icd-10",
                    "code": diagnosis.icd10_code,
                    "display": diagnosis.icd10_description
                }
            ]
        },
        "subject": {"reference": f"Patient/{rec.patient_id}"},
        "onsetDateTime": diagnosis.onset_date.isoformat() if diagnosis.onset_date else None,
        "note": [{"text": diagnosis.notes}] if diagnosis.notes else [],
    }


def _prescription_to_fhir(prescription):
    """Map records.Prescription to FHIR R4 MedicationRequest (minimal)."""
    rec = prescription.record
    return {
        "resourceType": "MedicationRequest",
        "id": str(prescription.id),
        "status": prescription.dispense_status,
        "intent": "order",
        "medicationCodeableConcept": {"text": prescription.drug_name},
        "subject": {"reference": f"Patient/{rec.patient_id}"},
        "dosageInstruction": [
            {
                "text": f"{prescription.dosage} {prescription.frequency}",
                "route": {"text": prescription.route},
                **(
                    {
                        "timing": {
                            "repeat": {
                                "duration": prescription.duration_days,
                                "durationUnit": "d"
                            }
                        }
                    }
                    if prescription.duration_days
                    else {}
                ),
            }
        ],
        "note": [{"text": prescription.notes}] if prescription.notes else [],
    }


def _vital_to_fhir(vital):
    """Map records.Vital to FHIR R4 Observation (multi-component)."""
    rec = vital.record
    components = []
    if vital.temperature_c is not None:
        components.append({"code": {"text": "Body temperature"}, "valueQuantity": {
                          "value": float(vital.temperature_c), "unit": "Cel"}})
    if vital.pulse_bpm is not None:
        components.append({"code": {"text": "Heart rate"}, "valueQuantity": {"value": vital.pulse_bpm, "unit": "/min"}})
    if vital.resp_rate is not None:
        components.append({"code": {"text": "Respiratory rate"}, "valueQuantity": {
                          "value": vital.resp_rate, "unit": "/min"}})
    if vital.bp_systolic is not None or vital.bp_diastolic is not None:
        components.append({"code": {"text": "Blood pressure"},
                           "valueString": f"{vital.bp_systolic or ''}/{vital.bp_diastolic or ''} mmHg"})
    if vital.spo2_percent is not None:
        components.append({"code": {"text": "SpO2"}, "valueQuantity": {
                          "value": float(vital.spo2_percent), "unit": "%"}})
    if vital.weight_kg is not None:
        components.append({"code": {"text": "Body weight"}, "valueQuantity": {
                          "value": float(vital.weight_kg), "unit": "kg"}})
    if vital.height_cm is not None:
        components.append({"code": {"text": "Body height"}, "valueQuantity": {
                          "value": float(vital.height_cm), "unit": "cm"}})
    if vital.bmi is not None:
        components.append({"code": {"text": "BMI"}, "valueQuantity": {"value": float(vital.bmi), "unit": "kg/m2"}})
    return {
        "resourceType": "Observation",
        "id": str(vital.id),
        "status": "final",
        "code": {"coding": [{"system": "http://loinc.org", "code": "85353-1", "display": "Vital signs panel"}]},
        "subject": {"reference": f"Patient/{rec.patient_id}"},
        "effectiveDateTime": rec.created_at.isoformat() if rec.created_at else None,
        "component": components if components else [{"code": {"text": "Vital signs"}, "valueString": "Recorded"}],
    }


def _fhir_bundle(entries, base_path):
    return {
        "resourceType": "Bundle",
        "type": "searchset",
        "total": len(entries),
        "entry": [{"fullUrl": f"{base_path}/{r['id']}", "resource": r} for r in entries],
    }


# ----- Patient -----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_patient_list(request):
    """GET /fhir/Patient - search by identifier (e.g. Ghana Health ID)."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    identifier = request.GET.get("identifier")
    if not identifier:
        return Response(_fhir_bundle([], "/fhir/Patient"))
    qs = get_patient_queryset(
        request.user,
        get_effective_hospital(request)).filter(
        ghana_health_id__icontains=identifier)[
            :20]
    entries = [_patient_to_fhir(p) for p in qs]
    return Response(_fhir_bundle(entries, "/fhir/Patient"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_patient_read(request, pk):
    """GET /fhir/Patient/<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=pk).first()
    if not patient:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(_patient_to_fhir(patient))


# ----- Encounter -----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_encounter_list(request):
    """GET /fhir/Encounter?patient=<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    patient_id = request.GET.get("patient")
    if not patient_id:
        return Response(_fhir_bundle([], "/fhir/Encounter"))
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(_fhir_bundle([], "/fhir/Encounter"))
    qs = get_encounter_queryset(request.user, patient=patient,
                                effective_hospital=get_effective_hospital(request)).order_by("-encounter_date")[:50]
    entries = [_encounter_to_fhir(e) for e in qs]
    return Response(_fhir_bundle(entries, "/fhir/Encounter"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_encounter_read(request, pk):
    """GET /fhir/Encounter/<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    enc = get_encounter_queryset(request.user, effective_hospital=get_effective_hospital(request)).filter(id=pk).first()
    if not enc:
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(_encounter_to_fhir(enc))


# ----- Condition (Diagnosis) -----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_condition_list(request):
    """GET /fhir/Condition?patient=<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    patient_id = request.GET.get("patient")
    if not patient_id:
        return Response(_fhir_bundle([], "/fhir/Condition"))
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(_fhir_bundle([], "/fhir/Condition"))
    mr_qs = get_medical_record_queryset(
        request.user,
        patient=patient,
        effective_hospital=get_effective_hospital(request)).filter(
        record_type="diagnosis")
    qs = Diagnosis.objects.filter(record__in=mr_qs).select_related("record")[:50]
    entries = [_diagnosis_to_fhir(d) for d in qs]
    return Response(_fhir_bundle(entries, "/fhir/Condition"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_condition_read(request, pk):
    """GET /fhir/Condition/<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    diagnosis = Diagnosis.objects.filter(id=pk).select_related("record").first()
    if not diagnosis or not get_medical_record_queryset(
            request.user,
            patient=diagnosis.record.patient,
            effective_hospital=get_effective_hospital(request)).filter(
            id=diagnosis.record_id).exists():
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(_diagnosis_to_fhir(diagnosis))


# ----- MedicationRequest (Prescription) -----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_medication_request_list(request):
    """GET /fhir/MedicationRequest?patient=<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    patient_id = request.GET.get("patient")
    if not patient_id:
        return Response(_fhir_bundle([], "/fhir/MedicationRequest"))
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(_fhir_bundle([], "/fhir/MedicationRequest"))
    mr_qs = get_medical_record_queryset(
        request.user,
        patient=patient,
        effective_hospital=get_effective_hospital(request)).filter(
        record_type="prescription")
    qs = Prescription.objects.filter(record__in=mr_qs).select_related("record")[:50]
    entries = [_prescription_to_fhir(p) for p in qs]
    return Response(_fhir_bundle(entries, "/fhir/MedicationRequest"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_medication_request_read(request, pk):
    """GET /fhir/MedicationRequest/<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    prescription = Prescription.objects.filter(id=pk).select_related("record").first()
    if not prescription or not get_medical_record_queryset(
            request.user,
            patient=prescription.record.patient,
            effective_hospital=get_effective_hospital(request)).filter(
            id=prescription.record_id).exists():
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(_prescription_to_fhir(prescription))


# ----- Observation (Vital) -----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_observation_list(request):
    """GET /fhir/Observation?patient=<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    patient_id = request.GET.get("patient")
    if not patient_id:
        return Response(_fhir_bundle([], "/fhir/Observation"))
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(_fhir_bundle([], "/fhir/Observation"))
    mr_qs = get_medical_record_queryset(
        request.user,
        patient=patient,
        effective_hospital=get_effective_hospital(request)).filter(
        record_type="vital_signs")
    qs = Vital.objects.filter(record__in=mr_qs).select_related("record")[:50]
    entries = [_vital_to_fhir(v) for v in qs]
    return Response(_fhir_bundle(entries, "/fhir/Observation"))


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def fhir_observation_read(request, pk):
    """GET /fhir/Observation/<id>."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    vital = Vital.objects.filter(id=pk).select_related("record").first()
    if not vital or not get_medical_record_queryset(
            request.user,
            patient=vital.record.patient,
            effective_hospital=get_effective_hospital(request)).filter(
            id=vital.record_id).exists():
        return Response(
            {"resourceType": "OperationOutcome", "issue": [{"severity": "error", "code": "not-found"}]},
            status=status.HTTP_404_NOT_FOUND,
        )
    return Response(_vital_to_fhir(vital))


# ----- HL7 ADT-style -----
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def hl7_adt_list(request):
    """GET /hl7/adt?patient=<id> - pipe-delimited ADT-style lines (A01 admit)."""
    if request.user.role not in _FHIR_ALLOWED_ROLES:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN
        )
    patient_id = request.GET.get("patient")
    if not patient_id:
        return Response({"data": []})
    patient = (
        get_patient_queryset(request.user, get_effective_hospital(request))
        .filter(id=patient_id)
        .first()
    )
    if not patient:
        return Response({"data": []})
    # Minimal ADT A01-style: MSH|^~\\&|MEDSYC|FAC|... | PID|1||<id>|<ghana_health_id>^^^GHA^GH|<name>^...
    lines = []
    msh = "MSH|^~\\&|MEDSYC|FACILITY|||20250101000000||ADT^A01|1|P|2.5"
    pid = f"PID|1||{
        patient.id}||{
        patient.full_name.replace(
            '^',
            ' ')}^^{
                patient.gender or 'U'}|{
                    patient.date_of_birth.isoformat() if patient.date_of_birth else ''}|||{
                        patient.ghana_health_id or ''}^^^GHA^GH"
    pv1 = "PV1|1|O"
    lines.extend([msh, pid, pv1])
    return Response({"data": lines, "format": "HL7v2.5 ADT A01"})


# ----- Outbound FHIR push (HIE / external EHR) -----
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def fhir_push(request):
    """
    Push a FHIR resource to an external URL. Body: target_url, resource_type
    (Patient|Encounter|Condition|MedicationRequest|Observation), resource_id.
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
    if resource_type not in ("Patient", "Encounter", "Condition", "MedicationRequest", "Observation"):
        return Response(
            {"message": "resource_type must be Patient, Encounter, Condition, MedicationRequest, or Observation"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    effective = get_effective_hospital(request)
    resource = None
    if resource_type == "Patient":
        patient = get_patient_queryset(request.user, effective).filter(id=resource_id).first()
        if patient:
            resource = _patient_to_fhir(patient)
    elif resource_type == "Encounter":
        enc = get_encounter_queryset(request.user, effective_hospital=effective).filter(id=resource_id).first()
        if enc:
            resource = _encounter_to_fhir(enc)
    elif resource_type == "Condition":
        diag = Diagnosis.objects.filter(id=resource_id).select_related("record").first()
        if diag and get_medical_record_queryset(
                request.user,
                patient=diag.record.patient,
                effective_hospital=effective).filter(
                id=diag.record_id).exists():
            resource = _diagnosis_to_fhir(diag)
    elif resource_type == "MedicationRequest":
        from records.models import Prescription
        rx = Prescription.objects.filter(id=resource_id).select_related("record").first()
        if rx and get_medical_record_queryset(
                request.user,
                patient=rx.record.patient,
                effective_hospital=effective).filter(
                id=rx.record_id).exists():
            resource = _prescription_to_fhir(rx)
    elif resource_type == "Observation":
        vital = Vital.objects.filter(id=resource_id).select_related("record").first()
        if vital and get_medical_record_queryset(
                request.user,
                patient=vital.record.patient,
                effective_hospital=effective).filter(
                id=vital.record_id).exists():
            resource = _vital_to_fhir(vital)
    if not resource:
        return Response(
            {"message": "Resource not found or access denied"},
            status=status.HTTP_404_NOT_FOUND,
        )
    import json
    import urllib.request
    import urllib.error
    try:
        data = json.dumps(resource).encode("utf-8")
        req = urllib.request.Request(
            target_url,
            data=data,
            headers={"Content-Type": "application/fhir+json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
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
