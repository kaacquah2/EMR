from decimal import Decimal
from django.utils import timezone
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from patients.models import Patient, Allergy, ClinicalAlert, PatientAdmission
from api.utils import get_patient_queryset, get_medical_record_queryset, get_effective_hospital, get_request_hospital
from records.models import (
    MedicalRecord,
    Diagnosis,
    Prescription,
    LabOrder,
    LabResult,
    LabTestType,
    Vital,
    NursingNote,
    RadiologyOrder,
)


GH_COMMON_ICD10_CODES = [
    ("B54", "Malaria, unspecified"),
    ("I10", "Essential (primary) hypertension"),
    ("E11.9", "Type 2 diabetes mellitus without complications"),
    ("J06.9", "Acute upper respiratory infection, unspecified"),
    ("J18.9", "Pneumonia, unspecified organism"),
]


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def icd10_autocomplete(request):
    if request.user.role not in ("doctor", "hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    query = (request.GET.get("q") or "").strip()
    if len(query) < 2:
        return Response({"data": []})
    upper_query = query.upper()
    data = []
    seen = set()
    for code, description in GH_COMMON_ICD10_CODES:
        if upper_query in code or query.lower() in description.lower():
            key = f"{code}|{description}"
            if key not in seen:
                data.append({"code": code, "description": description, "source": "gh_common"})
                seen.add(key)
    hist = (
        Diagnosis.objects.filter(
            Q(icd10_code__icontains=query) | Q(icd10_description__icontains=query)
        )
        .values("icd10_code", "icd10_description")
        .distinct()[:25]
    )
    for row in hist:
        code = (row.get("icd10_code") or "").strip()
        description = (row.get("icd10_description") or "").strip()
        if not code:
            continue
        key = f"{code}|{description}"
        if key in seen:
            continue
        data.append({"code": code, "description": description, "source": "historical"})
        seen.add(key)
    return Response({"data": data[:30]})


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def drug_autocomplete(request):
    if request.user.role not in ("doctor", "nurse", "pharmacist", "hospital_admin", "super_admin"):
        return Response({"message": "Permission denied"}, status=status.HTTP_403_FORBIDDEN)
    query = (request.GET.get("q") or "").strip()
    patient_id = (request.GET.get("patient_id") or "").strip()
    if len(query) < 2:
        return Response({"data": []})
    entries = (
        Prescription.objects.filter(drug_name__icontains=query)
        .values("drug_name")
        .annotate(count=Count("id"))
        .order_by("-count")[:30]
    )
    allergy_terms = []
    if patient_id:
        patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
        if patient:
            allergy_terms = [a.lower() for a in patient.allergy_set.filter(is_active=True).values_list("allergen", flat=True)]
    data = []
    for row in entries:
        name = (row.get("drug_name") or "").strip()
        if not name:
            continue
        lower_name = name.lower()
        allergy_flag = any(term in lower_name or lower_name in term for term in allergy_terms)
        data.append(
            {
                "name": name,
                "allergy_flag": allergy_flag,
                "match_source": "historical",
            }
        )
    return Response({"data": data})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_diagnosis(request):
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if patient.registered_at_id != hospital.id:
        return Response(
            {"message": "Patient is not registered at this hospital"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type="diagnosis",
        created_by=request.user,
    )
    from api.serializers import DiagnosisSerializer
    diag = Diagnosis.objects.create(
        record=record,
        icd10_code=data.get("icd10_code", ""),
        icd10_description=data.get("icd10_description", ""),
        severity=data.get("severity", "moderate"),
        onset_date=data.get("onset_date") or None,
        notes=data.get("notes") or None,
        is_chronic=data.get("is_chronic", False),
    )
    return Response(
        {"record_id": str(record.id), "diagnosis": DiagnosisSerializer(diag).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_prescription(request):
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if patient.registered_at_id != hospital.id:
        return Response(
            {"message": "Patient is not registered at this hospital"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    drug_name = (data.get("drug_name") or "").strip()
    allergies = patient.allergy_set.filter(is_active=True)
    conflict = None
    for a in allergies:
        if drug_name.lower() in a.allergen.lower() or a.allergen.lower() in drug_name.lower():
            conflict = {"allergen": a.allergen, "reaction": a.reaction_type, "severity": a.severity}
            break
    if conflict and not data.get("override_reason"):
        return Response(
            {
                "error": "ALLERGY_CONFLICT",
                "message": f"Drug conflicts with allergy: {conflict['allergen']}",
                "conflict": True,
                **conflict,
            },
            status=status.HTTP_409_CONFLICT,
        )
    record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type="prescription",
        created_by=request.user,
    )
    Prescription.objects.create(
        record=record,
        drug_name=drug_name,
        dosage=data.get("dosage", ""),
        frequency=data.get("frequency", ""),
        duration_days=data.get("duration_days"),
        route=data.get("route", "oral"),
        notes=data.get("notes") or None,
        allergy_conflict=bool(conflict),
        allergy_override_reason=data.get("override_reason") if conflict else None,
    )
    return Response({"record_id": str(record.id)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_lab_order(request):
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if patient.registered_at_id != hospital.id:
        return Response(
            {"message": "Patient is not registered at this hospital"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    test_name = (data.get("test_name") or data.get("test_type") or "").strip()
    if not test_name:
        return Response(
            {"message": "test_name or test_type required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    lab_unit = None
    test_type = LabTestType.objects.filter(
        lab_unit__hospital=hospital,
        test_name__iexact=test_name,
        is_active=True,
    ).select_related("lab_unit").first()
    if test_type:
        lab_unit = test_type.lab_unit
    record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type="lab_result",
        created_by=request.user,
    )
    urgency = (data.get("urgency") or "routine").strip()
    if urgency not in ("routine", "urgent", "stat"):
        urgency = "routine"
    lab_order = LabOrder.objects.create(
        record=record,
        test_name=test_name,
        urgency=urgency,
        notes=data.get("notes") or None,
        lab_unit=lab_unit,
        status="ordered",
    )
    LabResult.objects.create(
        record=record,
        lab_order=lab_order,
        test_name=test_name,
        status="pending",
    )
    return Response({"record_id": str(record.id)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_vitals(request):
    if request.user.role not in ("doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if patient.registered_at_id != hospital.id:
        return Response(
            {"message": "Patient is not registered at this hospital"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type="vital_signs",
        created_by=request.user,
    )
    w = data.get("weight_kg")
    h = data.get("height_cm")
    bmi = None
    if w and h and float(h) > 0:
        bmi = round(float(w) / (float(h) / 100) ** 2, 1)
    vital = Vital.objects.create(
        record=record,
        temperature_c=data.get("temperature_c"),
        pulse_bpm=data.get("pulse_bpm"),
        resp_rate=data.get("resp_rate"),
        bp_systolic=data.get("bp_systolic"),
        bp_diastolic=data.get("bp_diastolic"),
        spo2_percent=data.get("spo2_percent"),
        weight_kg=data.get("weight_kg"),
        height_cm=data.get("height_cm"),
        bmi=bmi,
        recorded_by=request.user,
    )
    critical_flags = []
    spo2 = data.get("spo2_percent")
    temp = data.get("temperature_c")
    pulse = data.get("pulse_bpm")
    try:
        if spo2 is not None and float(spo2) < 92:
            critical_flags.append("spo2")
        if temp is not None and (float(temp) > 38.5 or float(temp) < 35.0):
            critical_flags.append("temperature")
        if pulse is not None and (float(pulse) > 120 or float(pulse) < 50):
            critical_flags.append("pulse")
    except (TypeError, ValueError):
        pass
    if critical_flags:
        severity = "critical" if (spo2 is not None and float(spo2) < 88) else "high"
        alert_msg = "Critical vitals detected"
        if spo2 is not None and float(spo2) < 92:
            alert_msg = f"Low Oxygen Saturation: SpO2 {spo2}%"
        ClinicalAlert.objects.create(
            patient=patient,
            hospital=hospital,
            severity=severity,
            message=alert_msg,
            created_by=request.user,
            resource_type="vitals",
            resource_id=record.id,
        )
        if bool(data.get("critical_action_confirmed")):
            from api.utils import audit_log
            audit_log(
                request.user,
                "CRITICAL_VITALS_CONFIRMED",
                "vital_signs",
                str(record.id),
                hospital,
                request,
                extra_data={"critical_flags": critical_flags, "vital_id": str(vital.id)},
            )
    return Response({"record_id": str(record.id)}, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_vitals_batch(request):
    """Submit multiple vital sign readings in one request (for monitoring stations/ward).
    
    Request body:
    {
        "vitals": [
            {
                "patient_id": "uuid",
                "temperature_c": 37.2,
                "pulse_bpm": 78,
                "resp_rate": 18,
                "bp_systolic": 120,
                "bp_diastolic": 80,
                "spo2_percent": 98,
                "weight_kg": 70.5,
                "height_cm": 175,
                "notes": "..."  (optional)
            },
            { ... }
        ]
    }
    
    Returns:
    {
        "created": 18,
        "failed": 2,
        "items": [
            {"patient_id": "...", "status": "created", "record_id": "..."},
            {"patient_id": "...", "status": "error", "message": "..."},
            ...
        ]
    }
    """
    if request.user.role not in ("doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    vitals_list = request.data.get("vitals", request.data if isinstance(request.data, list) else [])
    if not vitals_list:
        return Response(
            {"message": "vitals list required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    from django.utils import timezone
    from api.utils import audit_log
    from api.signals_alerts import broadcast_alert_created

    results = {"created": 0, "failed": 0, "items": []}
    
    for vital_data in vitals_list:
        try:
            patient_id = vital_data.get("patient_id")
            if not patient_id:
                results["failed"] += 1
                results["items"].append({
                    "patient_id": None,
                    "status": "error",
                    "message": "patient_id required"
                })
                continue
            
            patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
            if not patient:
                results["failed"] += 1
                results["items"].append({
                    "patient_id": patient_id,
                    "status": "error",
                    "message": "Patient not found or access denied"
                })
                continue
            if request.user.role == "nurse":
                # Spec: batch vitals must be restricted to the nurse's ward only.
                active_in_ward = PatientAdmission.objects.filter(
                    patient=patient,
                    ward=request.user.ward,
                    discharged_at__isnull=True,
                ).exists()
                if not active_in_ward:
                    results["failed"] += 1
                    results["items"].append({
                        "patient_id": patient_id,
                        "status": "error",
                        "message": "Patient outside nurse ward scope",
                        "status_code": 403,
                    })
                    continue
            
            if patient.registered_at_id != hospital.id:
                results["failed"] += 1
                results["items"].append({
                    "patient_id": patient_id,
                    "status": "error",
                    "message": "Patient not registered at this hospital"
                })
                continue
            
            # Validate vital values
            temp = vital_data.get("temperature_c")
            if temp and (float(temp) < 35 or float(temp) > 42):
                results["failed"] += 1
                results["items"].append({
                    "patient_id": patient_id,
                    "status": "error",
                    "message": "Temperature must be between 35-42°C"
                })
                continue
            
            pulse = vital_data.get("pulse_bpm")
            if pulse and (float(pulse) < 40 or float(pulse) > 200):
                results["failed"] += 1
                results["items"].append({
                    "patient_id": patient_id,
                    "status": "error",
                    "message": "Pulse must be between 40-200 bpm"
                })
                continue
            
            systolic = vital_data.get("bp_systolic")
            if systolic and (float(systolic) < 70 or float(systolic) > 250):
                results["failed"] += 1
                results["items"].append({
                    "patient_id": patient_id,
                    "status": "error",
                    "message": "Systolic BP must be between 70-250 mmHg"
                })
                continue
            
            spO2 = vital_data.get("spo2_percent")
            if spO2 and (float(spO2) < 75 or float(spO2) > 100):
                results["failed"] += 1
                results["items"].append({
                    "patient_id": patient_id,
                    "status": "error",
                    "message": "SpO2 must be between 75-100%"
                })
                continue
            
            # Create medical record
            record = MedicalRecord.objects.create(
                patient=patient,
                hospital=hospital,
                record_type="vital_signs",
                created_by=request.user,
            )
            
            # Calculate BMI
            w = vital_data.get("weight_kg")
            h = vital_data.get("height_cm")
            bmi = None
            if w and h and float(h) > 0:
                bmi = round(float(w) / (float(h) / 100) ** 2, 1)
            
            # Create vital record
            vital = Vital.objects.create(
                record=record,
                temperature_c=temp,
                pulse_bpm=pulse,
                resp_rate=vital_data.get("resp_rate"),
                bp_systolic=systolic,
                bp_diastolic=vital_data.get("bp_diastolic"),
                spo2_percent=spO2,
                weight_kg=w,
                height_cm=h,
                bmi=bmi,
                recorded_by=request.user,
            )
            
            # Check for critical values and create alerts (real-time broadcast via Channels)
            if temp and float(temp) > 39:
                alert = ClinicalAlert.objects.create(
                    patient=patient,
                    hospital=hospital,
                    severity="high",
                    message=f"High Fever: Temperature {temp}°C",
                    created_by=request.user,
                    resource_type="vitals",
                    resource_id=record.id,
                )
                broadcast_alert_created(alert)
            if spO2 and float(spO2) < 90:
                alert = ClinicalAlert.objects.create(
                    patient=patient,
                    hospital=hospital,
                    severity="critical",
                    message=f"Low Oxygen Saturation: SpO2 {spO2}%",
                    created_by=request.user,
                    resource_type="vitals",
                    resource_id=record.id,
                )
                broadcast_alert_created(alert)
            if pulse and (float(pulse) > 130 or float(pulse) < 50):
                alert = ClinicalAlert.objects.create(
                    patient=patient,
                    hospital=hospital,
                    severity="high",
                    message=f"Abnormal Heart Rate: Pulse {pulse} bpm",
                    created_by=request.user,
                    resource_type="vitals",
                    resource_id=record.id,
                )
                broadcast_alert_created(alert)
            
            results["created"] += 1
            results["items"].append({
                "patient_id": patient_id,
                "status": "created",
                "record_id": str(record.id),
            })
            
            # Audit log each successful creation
            audit_log(
                request.user,
                "VITALS_CREATED",
                "vital_signs",
                str(record.id),
                hospital,
                request,
            )
            
        except (ValueError, TypeError) as e:
            results["failed"] += 1
            results["items"].append({
                "patient_id": vital_data.get("patient_id"),
                "status": "error",
                "message": f"Invalid data: {str(e)}"
            })
        except Exception as e:
            results["failed"] += 1
            results["items"].append({
                "patient_id": vital_data.get("patient_id"),
                "status": "error",
                "message": str(e)
            })
    
    # Audit the batch operation
    audit_log(
        request.user,
        "VITALS_BATCH_CREATED",
        "vital_signs",
        None,
        hospital,
        request,
        extra_data={"created": results["created"], "failed": results["failed"], "total": len(vitals_list)}
    )
    
    if request.user.role == "nurse" and results["failed"] > 0 and results["created"] == 0:
        return Response(results, status=status.HTTP_403_FORBIDDEN)
    return Response(results, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_allergy(request):
    if request.user.role not in ("doctor", "nurse"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    data = request.data
    patient_id = data.get("patient_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    allergy = Allergy.objects.create(
        patient=patient,
        allergen=data.get("allergen", ""),
        reaction_type=data.get("reaction_type", ""),
        severity=data.get("severity", "moderate"),
        notes=data.get("notes") or None,
        recorded_by=request.user,
    )
    from api.serializers import AllergySerializer
    return Response(AllergySerializer(allergy).data, status=status.HTTP_201_CREATED)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_nursing_note(request):
    if request.user.role != "nurse":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital:
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    data = request.data
    patient_id = data.get("patient_id")
    if not patient_id:
        return Response(
            {"message": "patient_id required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient:
        return Response(
            {"message": "Patient not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if patient.registered_at_id != hospital.id:
        return Response(
            {"message": "Patient is not registered at this hospital"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    note_type = (data.get("note_type") or "observation").strip().lower()
    if note_type not in ("observation", "handover", "incident"):
        return Response(
            {"message": "note_type must be observation, handover, or incident"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    incoming_nurse_id = data.get("incoming_nurse_id")
    if note_type == "handover":
        if not incoming_nurse_id:
            return Response(
                {"message": "incoming_nurse_id is required for handover notes"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from core.models import User
        incoming_nurse = User.objects.filter(
            id=incoming_nurse_id,
            role="nurse",
            hospital=hospital,
        ).first()
        if not incoming_nurse:
            return Response(
                {"message": "incoming_nurse_id must reference a nurse in this hospital"},
                status=status.HTTP_400_BAD_REQUEST,
            )
    record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type="nursing_note",
        created_by=request.user,
    )
    note = NursingNote.objects.create(
        record=record,
        content=data.get("content", ""),
        note_type=note_type,
        incoming_nurse_id=incoming_nurse_id if note_type == "handover" else None,
    )
    from api.utils import audit_log
    audit_log(
        request.user,
        "NURSING_NOTE_CREATED",
        resource_type="nursing_note",
        resource_id=record.id,
        hospital=hospital,
        request=request,
        extra_data={
            "note_type": note_type,
            "incoming_nurse_id": str(incoming_nurse_id) if incoming_nurse_id else None,
        },
    )
    return Response(
        {
            "record_id": str(record.id),
            "note_id": str(note.id),
            "note_type": note_type,
            "incoming_nurse_id": str(incoming_nurse_id) if incoming_nurse_id else None,
            "outgoing_signed_at": note.outgoing_signed_at.isoformat() if note.outgoing_signed_at else None,
            "acknowledged_at": note.acknowledged_at.isoformat() if note.acknowledged_at else None,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def amend_record(request, record_id):
    """Create an amendment of an existing record: new record linked from original, original marked is_amended. Doctor only per spec."""
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    record = get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request)).filter(id=record_id).select_related("patient", "hospital").first()
    if not record:
        return Response(
            {"message": "Record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    req_hospital = get_request_hospital(request)
    if req_hospital and record.hospital_id != req_hospital.id:
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    data = request.data
    reason = (data.get("amendment_reason") or "").strip()
    if not reason:
        return Response(
            {"message": "amendment_reason required"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    patient = record.patient
    hospital = record.hospital
    record_type = record.record_type
    new_record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type=record_type,
        created_by=request.user,
        amendment_reason=reason,
        is_amended=False,
        amended_record=None,
    )
    if record_type == "diagnosis" and hasattr(record, "diagnosis"):
        d = record.diagnosis
        Diagnosis.objects.create(
            record=new_record,
            icd10_code=data.get("icd10_code") or d.icd10_code,
            icd10_description=data.get("icd10_description") or d.icd10_description,
            severity=data.get("severity") or d.severity,
            onset_date=data.get("onset_date") or d.onset_date,
            notes=data.get("notes") if "notes" in data else d.notes,
            is_chronic=data.get("is_chronic", d.is_chronic),
        )
    elif record_type == "prescription" and hasattr(record, "prescription"):
        p = record.prescription
        Prescription.objects.create(
            record=new_record,
            drug_name=data.get("drug_name") or p.drug_name,
            dosage=data.get("dosage") or p.dosage,
            frequency=data.get("frequency") or p.frequency,
            duration_days=data.get("duration_days") if data.get("duration_days") is not None else p.duration_days,
            route=data.get("route") or p.route,
            notes=data.get("notes") if "notes" in data else p.notes,
            dispense_status=p.dispense_status,
        )
    elif record_type == "vital_signs" and hasattr(record, "vital"):
        v = record.vital
        Vital.objects.create(
            record=new_record,
            temperature_c=data.get("temperature_c") if data.get("temperature_c") is not None else v.temperature_c,
            pulse_bpm=data.get("pulse_bpm") if data.get("pulse_bpm") is not None else v.pulse_bpm,
            resp_rate=data.get("resp_rate") if data.get("resp_rate") is not None else v.resp_rate,
            bp_systolic=data.get("bp_systolic") if data.get("bp_systolic") is not None else v.bp_systolic,
            bp_diastolic=data.get("bp_diastolic") if data.get("bp_diastolic") is not None else v.bp_diastolic,
            spo2_percent=data.get("spo2_percent") if data.get("spo2_percent") is not None else v.spo2_percent,
            weight_kg=data.get("weight_kg") if data.get("weight_kg") is not None else v.weight_kg,
            height_cm=data.get("height_cm") if data.get("height_cm") is not None else v.height_cm,
            bmi=data.get("bmi") if data.get("bmi") is not None else v.bmi,
            recorded_by=request.user,
        )
    elif record_type == "nursing_note" and hasattr(record, "nursingnote"):
        n = record.nursingnote
        NursingNote.objects.create(
            record=new_record,
            content=data.get("content") or n.content,
        )
    elif record_type == "lab_result":
        if hasattr(record, "labresult"):
            lr = record.labresult
            lab_order = LabOrder.objects.create(
                record=new_record,
                test_name=data.get("test_name") or lr.test_name,
                urgency=data.get("urgency", "routine"),
                notes=data.get("notes"),
            )
            LabResult.objects.create(
                record=new_record,
                lab_order=lab_order,
                test_name=data.get("test_name") or lr.test_name,
                result_value=data.get("result_value") if data.get("result_value") is not None else lr.result_value,
                reference_range=data.get("reference_range") if data.get("reference_range") is not None else lr.reference_range,
                status=lr.status,
                lab_tech=lr.lab_tech,
            )
        else:
            LabResult.objects.create(record=new_record, test_name=data.get("test_name", ""), status="pending")
    else:
        new_record.delete()
        return Response(
            {"message": "Amendment not supported for this record type"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    record.is_amended = True
    record.amended_record = new_record
    record.save(update_fields=["is_amended", "amended_record"])
    from api.serializers import MedicalRecordSerializer
    return Response(
        {"message": "Amendment created", "amended_record_id": str(new_record.id), "record": MedicalRecordSerializer(new_record).data},
        status=status.HTTP_201_CREATED,
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated])
def prescription_dispense(request, record_id):
    """Update prescription dispense status (pharmacy: prescribed -> dispensed | cancelled)."""
    if request.user.role != "pharmacist":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    record = (
        get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
        .filter(id=record_id, record_type="prescription")
        .select_related("patient", "hospital")
        .first()
    )
    if not record:
        return Response(
            {"message": "Prescription record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    try:
        prescription = record.prescription
    except Prescription.DoesNotExist:
        return Response(
            {"message": "Prescription not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    new_status = (request.data.get("dispense_status") or "").strip().lower()
    if new_status not in ("dispensed", "cancelled"):
        return Response(
            {"message": "dispense_status must be 'dispensed' or 'cancelled'"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    prescription.dispense_status = new_status
    prescription.save(update_fields=["dispense_status"])
    from api.integrations import notify_pharmacy_dispense
    notify_pharmacy_dispense(
        record.id, prescription.id, prescription.dispense_status, record.hospital_id
    )
    return Response({
        "record_id": str(record.id),
        "dispense_status": prescription.dispense_status,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def prescription_dispense_by_nurse(request, record_id):
    """Spec endpoint for nurse dispense action with ward and hospital checks."""
    if request.user.role != "nurse":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    record = (
        get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
        .filter(id=record_id, record_type="prescription")
        .select_related("patient", "hospital")
        .first()
    )
    if not record:
        return Response(
            {"message": "Prescription record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    if not request.user.ward_id:
        return Response(
            {"message": "Nurse has no ward assignment"},
            status=status.HTTP_403_FORBIDDEN,
        )
    active_in_ward = PatientAdmission.objects.filter(
        patient_id=record.patient_id,
        ward_id=request.user.ward_id,
        discharged_at__isnull=True,
    ).exists()
    if not active_in_ward:
        return Response(
            {"message": "Patient is not in nurse ward scope"},
            status=status.HTTP_403_FORBIDDEN,
        )
    try:
        prescription = record.prescription
    except Prescription.DoesNotExist:
        return Response(
            {"message": "Prescription not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    # Mandatory safety check: block administration when active allergy signals exist.
    active_allergy_alert = ClinicalAlert.objects.filter(
        patient_id=record.patient_id,
        status="active",
        resource_type__in=("allergy", "medication"),
    ).exists()
    allergy_terms = list(
        Allergy.objects.filter(
            patient_id=record.patient_id,
            is_active=True,
        ).values_list("allergen", flat=True)
    )
    rx_name = (prescription.drug_name or "").strip().lower()
    direct_allergy_conflict = any(
        term and (term.lower() in rx_name or rx_name in term.lower())
        for term in allergy_terms
    )
    if active_allergy_alert or direct_allergy_conflict or bool(getattr(prescription, "allergy_conflict", False)):
        return Response(
            {
                "error": "ALLERGY_SAFETY_BLOCK",
                "message": "Medication administration blocked due to active allergy risk. Clinical review required.",
            },
            status=status.HTTP_409_CONFLICT,
        )

    prescription.dispense_status = "dispensed"
    prescription.save(update_fields=["dispense_status"])
    return Response(
        {
            "record_id": str(record.id),
            "dispense_status": prescription.dispense_status,
            "dispensed_by": str(request.user.id),
            "dispensed_at": timezone.now().isoformat(),
        }
    )


def _radiology_queryset(user):
    """Radiology orders scoped by hospital."""
    qs = RadiologyOrder.objects.all()
    if user.role == "super_admin" and not user.hospital_id:
        return qs
    if user.hospital_id:
        return qs.filter(hospital=user.hospital)
    return qs.none()


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def create_radiology_order(request):
    """Create a radiology/imaging order (placeholder: study type, optional encounter)."""
    if request.method == "GET":
        if request.user.role not in ("radiology_technician", "super_admin", "hospital_admin"):
            return Response(
                {"message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN,
            )
        qs = _radiology_queryset(request.user).select_related("patient").order_by("-created_at")[:100]
        return Response(
            {
                "data": [
                    {
                        "order_id": str(order.id),
                        "patient_id": str(order.patient_id),
                        "patient_name": order.patient.full_name,
                        "study_type": order.study_type,
                        "status": order.status,
                        "attachment_url": order.attachment_url,
                        "created_at": order.created_at.isoformat() if order.created_at else None,
                    }
                    for order in qs
                ]
            }
        )

    if request.user.role not in ("super_admin", "hospital_admin", "doctor"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    hospital = get_request_hospital(request)
    if not hospital and request.user.role != "super_admin":
        return Response(
            {"message": "No hospital assigned"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if not hospital and request.user.role == "super_admin" and request.data.get("hospital_id"):
        from core.models import Hospital
        try:
            hospital = Hospital.objects.get(id=request.data.get("hospital_id"))
        except Hospital.DoesNotExist:
            return Response({"message": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
    if not hospital:
        return Response({"message": "hospital_id required"}, status=status.HTTP_400_BAD_REQUEST)
    patient_id = request.data.get("patient_id")
    if not patient_id:
        return Response({"message": "patient_id required"}, status=status.HTTP_400_BAD_REQUEST)
    patient = get_patient_queryset(request.user, get_effective_hospital(request)).filter(id=patient_id).first()
    if not patient or patient.registered_at_id != hospital.id:
        return Response({"message": "Patient not found or not at this hospital"}, status=status.HTTP_404_NOT_FOUND)
    study_type = (request.data.get("study_type") or request.data.get("study_name") or "").strip()
    if not study_type:
        return Response({"message": "study_type required"}, status=status.HTTP_400_BAD_REQUEST)
    encounter_id = request.data.get("encounter_id")
    encounter = None
    if encounter_id:
        from api.utils import get_encounter_queryset
        encounter = get_encounter_queryset(request.user, patient=patient, effective_hospital=get_effective_hospital(request)).filter(id=encounter_id).first()
    order = RadiologyOrder.objects.create(
        patient=patient,
        hospital=hospital,
        encounter=encounter,
        study_type=study_type,
        status="ordered",
        created_by=request.user,
    )
    return Response(
        {"id": str(order.id), "patient_id": str(order.patient_id), "study_type": order.study_type, "status": order.status},
        status=status.HTTP_201_CREATED,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def radiology_order_attachment(request, order_id):
    """Update radiology order attachment URL (e.g. after upload)."""
    if request.user.role not in ("super_admin", "hospital_admin", "doctor", "radiology_technician"):
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    order = _radiology_queryset(request.user).filter(id=order_id).first()
    if not order:
        return Response({"message": "Radiology order not found"}, status=status.HTTP_404_NOT_FOUND)
    url = (request.data.get("attachment_url") or "").strip() or None
    order.attachment_url = url
    up = ["attachment_url"]
    if request.data.get("status") in ("in_progress", "completed"):
        order.status = request.data.get("status")
        up.append("status")
    order.save(update_fields=up)
    from api.integrations import notify_pacs_result
    notify_pacs_result(order.id, order.attachment_url, order.status, order.hospital_id)
    return Response({"id": str(order.id), "attachment_url": order.attachment_url, "status": order.status})


# PHASE 6: Doctor Clinical Workflow Enhancements


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def doctor_favorite_prescriptions(request):
    """Get doctor's most frequently prescribed drugs (favorites)."""
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    hospital = get_request_hospital(request)
    if not hospital:
        return Response({"data": []})
    
    # Get 10 most frequently prescribed drugs by this doctor
    from django.db.models import Count
    
    favorites = (
        Prescription.objects
        .filter(record__created_by=request.user, record__hospital=hospital, record__record_type="prescription")
        .values("drug_name", "dosage", "frequency", "route")
        .annotate(count=Count("id"))
        .order_by("-count")[:10]
    )
    
    return Response({"data": list(favorites)})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def doctor_prescription_refill(request, record_id):
    """Refill a previous prescription (copy and create new record)."""
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    record = (
        get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
        .filter(id=record_id, record_type="prescription")
        .select_related("patient", "hospital", "prescription")
        .first()
    )
    
    if not record:
        return Response(
            {"message": "Prescription record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    orig_prescription = record.prescription
    patient = record.patient
    hospital = record.hospital
    
    # Create new medical record for refill
    new_record = MedicalRecord.objects.create(
        patient=patient,
        hospital=hospital,
        record_type="prescription",
        created_by=request.user,
    )
    
    # Copy prescription with optional overrides
    new_prescription = Prescription.objects.create(
        record=new_record,
        drug_name=request.data.get("drug_name") or orig_prescription.drug_name,
        dosage=request.data.get("dosage") or orig_prescription.dosage,
        frequency=request.data.get("frequency") or orig_prescription.frequency,
        duration_days=request.data.get("duration_days") if request.data.get("duration_days") is not None else orig_prescription.duration_days,
        route=request.data.get("route") or orig_prescription.route,
        notes=(request.data.get("notes") or f"Refilled from prescription {record_id}"),
        dispense_status="prescribed",
    )
    
    from api.serializers import PrescriptionSerializer
    return Response(
        {
            "message": "Prescription refilled",
            "original_record_id": str(record_id),
            "new_record_id": str(new_record.id),
            "prescription": PrescriptionSerializer(new_prescription).data,
        },
        status=status.HTTP_201_CREATED,
    )


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def doctor_amendment_history(request, record_id):
    """View amendment history for a record (original + all amendments)."""
    if request.user.role != "doctor":
        return Response(
            {"message": "Permission denied"},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    record = (
        get_medical_record_queryset(request.user, effective_hospital=get_effective_hospital(request))
        .filter(id=record_id)
        .first()
    )
    
    if not record:
        return Response(
            {"message": "Record not found"},
            status=status.HTTP_404_NOT_FOUND,
        )
    
    history = []
    
    # Current record
    history.append({
        "record_id": str(record.id),
        "version": "current",
        "amendment_reason": record.amendment_reason,
        "created_by": record.created_by.full_name,
        "created_at": record.created_at.isoformat(),
        "is_amended": record.is_amended,
    })
    
    # Follow amendment chain (if this record amended another)
    if record.amended_record_id:
        amended = record.amended_record
        while amended:
            history.append({
                "record_id": str(amended.id),
                "version": "previous",
                "amendment_reason": amended.amendment_reason,
                "created_by": amended.created_by.full_name,
                "created_at": amended.created_at.isoformat(),
                "is_amended": amended.is_amended,
            })
            if amended.amended_record_id:
                amended = amended.amended_record
            else:
                break
    
    return Response({"record_id": record_id, "amendment_history": history})
