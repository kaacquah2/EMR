from django.conf import settings
from django.utils import timezone
from datetime import datetime

def _get_base_url():
    return getattr(settings, "BASE_URL", "https://api.medsync.com")

def _nullify_none(obj):
    """Recursively remove None values from dict (FHIR doesn't allow nulls in JSON)."""
    if isinstance(obj, dict):
        return {k: _nullify_none(v) for k, v in obj.items() if v is not None}
    elif isinstance(obj, list):
        return [_nullify_none(v) for v in obj if v is not None]
    return obj

class FHIRPatientSerializer:
    @staticmethod
    def serialize(patient):
        """Serialize Patient to FHIR R4 Patient resource with all required/extended fields."""
        identifiers = [
            {
                "system": "https://ghanahealth.org/ghana-health-id",
                "value": patient.ghana_health_id,
                "use": "official"
            }
        ]
        if patient.national_id:
            identifiers.append({
                "system": "https://ghanahealth.org/national-id",
                "value": patient.national_id
            })
        if patient.nhis_number:
            identifiers.append({
                "system": "https://ghanahealth.org/nhis",
                "value": patient.nhis_number
            })
        if patient.passport_number:
            identifiers.append({
                "system": "http://unstats.un.org/unsd/methods/m49/iso3166.htm",
                "value": patient.passport_number
            })
        
        telecom = []
        if patient.phone:
            telecom.append({
                "system": "phone",
                "value": patient.phone,
                "use": "home"
            })
        
        resource = {
            "resourceType": "Patient",
            "id": str(patient.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"],
                "lastUpdated": patient.updated_at.isoformat() if patient.updated_at else None
            },
            "identifier": identifiers,
            "active": not patient.is_archived,
            "name": [
                {
                    "use": "official",
                    "text": patient.full_name,
                    "family": patient.full_name.split()[-1] if patient.full_name else None,
                    "given": patient.full_name.split()[:-1] if len(patient.full_name.split()) > 1 else [patient.full_name]
                }
            ],
            "telecom": telecom,
            "gender": patient.gender if patient.gender in ["male", "female", "other", "unknown"] else "unknown",
            "birthDate": patient.date_of_birth.isoformat() if patient.date_of_birth else None,
            "address": [
                {
                    "use": "home",
                    "type": "physical",
                    "text": f"{patient.registered_at.name}, Ghana" if patient.registered_at else "Ghana"
                }
            ] if patient.registered_at else [],
            "maritalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/v3-MaritalStatus",
                        "code": "U",
                        "display": "unmarried"
                    }
                ]
            },
            "contact": [
                {
                    "relationship": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0131",
                                    "code": "E",
                                    "display": "Emergency Contact"
                                }
                            ]
                        }
                    ],
                    "telecom": telecom
                }
            ] if telecom else [],
            "generalPractitioner": [
                {
                    "reference": f"Practitioner/{patient.created_by.id}",
                    "display": patient.created_by.full_name if patient.created_by else None
                }
            ] if patient.created_by else [],
            "managingOrganization": {
                "reference": f"Organization/{patient.registered_at.id}",
                "display": patient.registered_at.name if patient.registered_at else None
            } if patient.registered_at else None
        }
        
        if patient.blood_group and patient.blood_group != "unknown":
            resource["extension"] = [
                {
                    "url": "http://hl7.org/fhir/StructureDefinition/patient-birthPlace",
                    "valueAddress": {
                        "country": "GH"
                    }
                },
                {
                    "url": "http://fhir.nhs.uk/StructureDefinition/Extension-UKCore-BloodType",
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": _blood_group_to_snomed(patient.blood_group),
                                "display": patient.blood_group
                            }
                        ]
                    }
                }
            ]
        
        return _nullify_none(resource)

def _blood_group_to_snomed(blood_group):
    """Map blood group to SNOMED CT code."""
    mapping = {
        "A+": "365629006", "A-": "365629006",
        "B+": "365628003", "B-": "365628003",
        "AB+": "365627008", "AB-": "365627008",
        "O+": "365626007", "O-": "365626007",
    }
    return mapping.get(blood_group, "365626007")


class FHIREncounterSerializer:
    @staticmethod
    def serialize(encounter):
        """Serialize Encounter to FHIR R4 Encounter resource with full details."""
        status_map = {
            "waiting": "arrived",
            "in_consultation": "in-progress",
            "completed": "finished"
        }
        fhir_status = status_map.get(encounter.status, "arrived")
        
        visit_status_map = {
            "registered": "arrived",
            "waiting_triage": "arrived",
            "waiting_doctor": "arrived",
            "in_consultation": "in-progress",
            "sent_to_lab": "in-progress",
            "admitted": "in-progress",
            "discharged": "finished",
        }
        fhir_status = visit_status_map.get(encounter.visit_status, fhir_status)
        
        encounter_type_map = {
            "outpatient": "AMB",
            "inpatient": "IMP",
            "emergency": "EMER",
            "follow_up": "AMB",
            "consultation": "AMB",
            "other": "AMB"
        }
        encounter_class_code = encounter_type_map.get(encounter.encounter_type, "AMB")
        
        resource = {
            "resourceType": "Encounter",
            "id": str(encounter.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Encounter"],
                "lastUpdated": encounter.updated_at.isoformat() if encounter.updated_at else None
            },
            "status": fhir_status,
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": encounter_class_code,
                "display": encounter.encounter_type.replace("_", " ").title()
            },
            "type": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                            "code": encounter_class_code,
                            "display": encounter.encounter_type.replace("_", " ").title()
                        }
                    ],
                    "text": encounter.encounter_type
                }
            ] if encounter.encounter_type else [],
            "subject": {
                "reference": f"Patient/{encounter.patient_id}",
                "display": encounter.patient.full_name if encounter.patient else None
            },
            "period": {
                "start": encounter.encounter_date.isoformat() if encounter.encounter_date else None,
                "end": encounter.updated_at.isoformat() if encounter.status == "completed" else None
            },
            "length": {
                "value": 0,
                "unit": "minutes",
                "system": "http://unitsofmeasure.org",
                "code": "min"
            } if encounter.status == "completed" else None,
            "reasonCode": [
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "display": encounter.chief_complaint or encounter.notes or "Check-up"
                        }
                    ],
                    "text": encounter.chief_complaint or encounter.notes or ""
                }
            ] if encounter.chief_complaint or encounter.notes else [],
            "participant": [
                {
                    "type": [
                        {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v3-ParticipationType",
                                    "code": "PPRF",
                                    "display": "primary performer"
                                }
                            ]
                        }
                    ],
                    "individual": {
                        "reference": f"Practitioner/{encounter.assigned_doctor.id}",
                        "display": encounter.assigned_doctor.full_name if encounter.assigned_doctor else None
                    }
                }
            ] if encounter.assigned_doctor else [],
            "location": [
                {
                    "location": {
                        "reference": f"Location/{encounter.hospital.id}",
                        "display": encounter.hospital.name if encounter.hospital else None
                    },
                    "status": "completed"
                }
            ] if encounter.hospital else [],
            "serviceProvider": {
                "reference": f"Organization/{encounter.hospital.id}",
                "display": encounter.hospital.name if encounter.hospital else None
            } if encounter.hospital else None,
            "text": {
                "status": "generated",
                "div": f"<div xmlns='http://www.w3.org/1999/xhtml'>{encounter.notes or 'Encounter'}</div>" if encounter.notes else None
            } if encounter.notes else None
        }
        
        return _nullify_none(resource)


class FHIRConditionSerializer:
    @staticmethod
    def serialize(diagnosis):
        """Serialize Diagnosis to FHIR R4 Condition with full clinical details."""
        rec = diagnosis.record
        
        severity_map = {
            "mild": "255604002",
            "moderate": "6736007",
            "severe": "24484000",
            "critical": "276654001"
        }
        severity_snomed = severity_map.get(diagnosis.severity, "255604002")
        
        resource = {
            "resourceType": "Condition",
            "id": str(diagnosis.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Condition"],
                "lastUpdated": rec.created_at.isoformat() if rec.created_at else None
            },
            "clinicalStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                        "code": "active" if not diagnosis.is_chronic or rec.created_at > timezone.now() else "active",
                        "display": "Active"
                    }
                ]
            },
            "verificationStatus": {
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                        "code": "confirmed",
                        "display": "Confirmed"
                    }
                ]
            },
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                            "code": "encounter-diagnosis" if not diagnosis.is_chronic else "problem-list-item",
                            "display": "Encounter Diagnosis" if not diagnosis.is_chronic else "Problem List Item"
                        }
                    ]
                }
            ],
            "severity": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": severity_snomed,
                        "display": diagnosis.severity.title()
                    }
                ]
            } if diagnosis.severity else None,
            "code": {
                "coding": [
                    {
                        "system": "http://hl7.org/fhir/sid/icd-10",
                        "code": diagnosis.icd10_code,
                        "display": diagnosis.icd10_description
                    }
                ],
                "text": diagnosis.icd10_description
            },
            "subject": {
                "reference": f"Patient/{rec.patient_id}",
                "display": rec.patient.full_name if rec.patient else None
            },
            "encounter": {
                "reference": f"Encounter/{rec.id}" if hasattr(rec, 'encounter_id') else None
            } if hasattr(rec, 'encounter_id') else None,
            "onsetDateTime": diagnosis.onset_date.isoformat() if diagnosis.onset_date else None,
            "recordedDate": rec.created_at.isoformat() if rec.created_at else None,
            "recorder": {
                "reference": f"Practitioner/{rec.created_by.id}",
                "display": rec.created_by.full_name if rec.created_by else None
            } if rec.created_by else None,
            "note": [
                {
                    "text": diagnosis.notes,
                    "time": rec.created_at.isoformat() if rec.created_at else None
                }
            ] if diagnosis.notes else [],
            "extension": [
                {
                    "url": "http://hl7.org/fhir/StructureDefinition/condition-dueTo",
                    "valueCodeableConcept": {
                        "text": "Medical condition"
                    }
                }
            ] if diagnosis.is_chronic else None
        }
        
        return _nullify_none(resource)


class FHIRMedicationRequestSerializer:
    @staticmethod
    def serialize(prescription):
        """Serialize Prescription to FHIR R4 MedicationRequest with full pharmacy details."""
        rec = prescription.record
        
        status_map = {
            "pending": "active",
            "dispensed": "completed",
            "cancelled": "cancelled"
        }
        fhir_status = status_map.get(prescription.dispense_status, "unknown")
        
        priority_map = {
            'routine': 'routine',
            'urgent': 'urgent',
            'stat': 'asap'
        }
        fhir_priority = priority_map.get(prescription.priority, 'routine')
        
        route_map = {
            "oral": "26643006",
            "iv": "47625008",
            "im": "78421000",
            "topical": "359540000",
            "inhalation": "447694001",
            "other": "38239002"
        }
        route_snomed = route_map.get(prescription.route, "38239002")
        
        resource = {
            "resourceType": "MedicationRequest",
            "id": str(prescription.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/MedicationRequest"],
                "lastUpdated": rec.created_at.isoformat() if rec.created_at else None
            },
            "status": fhir_status,
            "statusReason": {
                "text": prescription.dispense_notes
            } if prescription.dispense_status == "cancelled" and prescription.dispense_notes else None,
            "intent": "order",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/medicationrequest-category",
                            "code": "outpatient",
                            "display": "Outpatient"
                        }
                    ]
                }
            ],
            "priority": fhir_priority,
            "medicationCodeableConcept": {
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "display": prescription.drug_name
                    }
                ],
                "text": prescription.drug_name
            },
            "subject": {
                "reference": f"Patient/{rec.patient_id}",
                "display": rec.patient.full_name if rec.patient else None
            },
            "encounter": {
                "reference": f"Encounter/{rec.id}"
            } if hasattr(rec, 'encounter_id') else None,
            "authoredOn": rec.created_at.isoformat() if rec.created_at else None,
            "requester": {
                "reference": f"Practitioner/{rec.created_by.id}",
                "display": rec.created_by.full_name if rec.created_by else None
            } if rec.created_by else None,
            "performer": {
                "reference": f"Practitioner/{prescription.dispensed_by.id}",
                "display": prescription.dispensed_by.full_name if prescription.dispensed_by else None
            } if prescription.dispensed_by else None,
            "reasonCode": [
                {
                    "text": prescription.notes
                }
            ] if prescription.notes else [],
            "dosageInstruction": [
                {
                    "sequence": 1,
                    "text": f"{prescription.dosage} {prescription.frequency}",
                    "timing": {
                        "repeat": {
                            "frequency": _frequency_to_timing_frequency(prescription.frequency),
                            "duration": prescription.duration_days,
                            "durationUnit": "d"
                        } if prescription.frequency and prescription.duration_days else {}
                    },
                    "route": {
                        "coding": [
                            {
                                "system": "http://snomed.info/sct",
                                "code": route_snomed,
                                "display": prescription.route.title()
                            }
                        ],
                        "text": prescription.route
                    },
                    "doseAndRate": [
                        {
                            "doseQuantity": {
                                "value": _extract_numeric_dosage(prescription.dosage),
                                "unit": _extract_dosage_unit(prescription.dosage),
                                "system": "http://unitsofmeasure.org"
                            }
                        }
                    ] if prescription.dosage else []
                }
            ],
            "dispenseRequest": {
                "validityPeriod": {
                    "start": rec.created_at.isoformat() if rec.created_at else None,
                    "end": rec.created_at.isoformat() if rec.created_at and prescription.duration_days else None
                },
                "numberOfRepeatsAllowed": 0 if prescription.duration_days else None,
                "quantity": {
                    "value": prescription.dispensed_quantity,
                    "unit": "unit"
                } if prescription.dispensed_quantity else None,
                "expectedSupplyDuration": {
                    "value": prescription.duration_days,
                    "unit": "days",
                    "system": "http://unitsofmeasure.org",
                    "code": "d"
                } if prescription.duration_days else None,
                "performer": {
                    "reference": f"Organization/{rec.hospital.id}",
                    "display": rec.hospital.name if rec.hospital else None
                } if rec.hospital else None
            } if fhir_status != "cancelled" else None,
            "substitution": {
                "allowed": True,
                "reason": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ActReason",
                            "code": "ALLRG",
                            "display": "Allergy"
                        }
                    ]
                }
            } if prescription.allergy_conflict else None,
            "note": [
                {
                    "text": prescription.dispense_notes
                }
            ] if prescription.dispense_notes else []
        }
        
        return _nullify_none(resource)

def _frequency_to_timing_frequency(frequency_str):
    """Map frequency string (e.g., 'twice daily') to FHIR timing frequency."""
    freq_map = {
        'once': 1,
        'twice': 2,
        'three': 3,
        'four': 4,
        'daily': 1,
    }
    for key, val in freq_map.items():
        if key in frequency_str.lower():
            return val
    return 1

def _extract_numeric_dosage(dosage_str):
    """Extract numeric value from dosage string."""
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', dosage_str)
    return float(match.group(1)) if match else None

def _extract_dosage_unit(dosage_str):
    """Extract unit from dosage string (mg, ml, tablet, etc)."""
    import re
    match = re.search(r'(\d+(?:\.\d+)?)\s*([a-zA-Z]+)', dosage_str)
    return match.group(2).lower() if match else "unit"


class FHIRObservationSerializer:
    @staticmethod
    def serialize_vital(vital):
        """Serialize Vital to FHIR R4 Observation with multi-component vitals panel."""
        rec = vital.record
        components = []
        
        if vital.temperature_c is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8310-5", "display": "Body temperature"}],
                    "text": "Body temperature"
                },
                "valueQuantity": {
                    "value": float(vital.temperature_c),
                    "unit": "°C",
                    "system": "http://unitsofmeasure.org",
                    "code": "Cel"
                }
            })
        if vital.pulse_bpm is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8867-4", "display": "Heart rate"}],
                    "text": "Heart rate"
                },
                "valueQuantity": {
                    "value": vital.pulse_bpm,
                    "unit": "beats/minute",
                    "system": "http://unitsofmeasure.org",
                    "code": "/min"
                }
            })
        if vital.resp_rate is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "9279-1", "display": "Respiratory rate"}],
                    "text": "Respiratory rate"
                },
                "valueQuantity": {
                    "value": vital.resp_rate,
                    "unit": "breaths/minute",
                    "system": "http://unitsofmeasure.org",
                    "code": "/min"
                }
            })
        if vital.bp_systolic is not None or vital.bp_diastolic is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "55284-4", "display": "Blood pressure systolic and diastolic"}],
                    "text": "Blood pressure"
                },
                "component": [
                    {
                        "code": {
                            "coding": [{"system": "http://loinc.org", "code": "8480-6", "display": "Systolic blood pressure"}],
                            "text": "Systolic"
                        },
                        "valueQuantity": {
                            "value": vital.bp_systolic,
                            "unit": "mmHg",
                            "system": "http://unitsofmeasure.org",
                            "code": "mm[Hg]"
                        }
                    } if vital.bp_systolic else None,
                    {
                        "code": {
                            "coding": [{"system": "http://loinc.org", "code": "8462-4", "display": "Diastolic blood pressure"}],
                            "text": "Diastolic"
                        },
                        "valueQuantity": {
                            "value": vital.bp_diastolic,
                            "unit": "mmHg",
                            "system": "http://unitsofmeasure.org",
                            "code": "mm[Hg]"
                        }
                    } if vital.bp_diastolic else None
                ]
            })
        if vital.spo2_percent is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "2708-6", "display": "Oxygen saturation in Arterial blood"}],
                    "text": "SpO2"
                },
                "valueQuantity": {
                    "value": float(vital.spo2_percent),
                    "unit": "%",
                    "system": "http://unitsofmeasure.org",
                    "code": "%"
                }
            })
        if vital.weight_kg is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "29463-7", "display": "Body weight"}],
                    "text": "Body weight"
                },
                "valueQuantity": {
                    "value": float(vital.weight_kg),
                    "unit": "kg",
                    "system": "http://unitsofmeasure.org",
                    "code": "kg"
                }
            })
        if vital.height_cm is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "8302-2", "display": "Body height"}],
                    "text": "Body height"
                },
                "valueQuantity": {
                    "value": float(vital.height_cm),
                    "unit": "cm",
                    "system": "http://unitsofmeasure.org",
                    "code": "cm"
                }
            })
        if vital.bmi is not None:
            components.append({
                "code": {
                    "coding": [{"system": "http://loinc.org", "code": "39156-5", "display": "Body mass index (BMI)"}],
                    "text": "BMI"
                },
                "valueQuantity": {
                    "value": float(vital.bmi),
                    "unit": "kg/m²",
                    "system": "http://unitsofmeasure.org",
                    "code": "kg/m2"
                }
            })
        
        resource = {
            "resourceType": "Observation",
            "id": str(vital.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/vitalsigns"],
                "lastUpdated": rec.created_at.isoformat() if rec.created_at else None
            },
            "status": "final",
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "85353-1",
                        "display": "Vital signs, weight, height, head circumference, oxygen saturation and BMI panel"
                    }
                ]
            },
            "subject": {
                "reference": f"Patient/{rec.patient_id}",
                "display": rec.patient.full_name if rec.patient else None
            },
            "encounter": {
                "reference": f"Encounter/{rec.id}"
            } if hasattr(rec, 'encounter_id') else None,
            "effectiveDateTime": rec.created_at.isoformat() if rec.created_at else None,
            "issued": rec.created_at.isoformat() if rec.created_at else None,
            "performer": [
                {
                    "reference": f"Practitioner/{vital.recorded_by.id}",
                    "display": vital.recorded_by.full_name if vital.recorded_by else None
                }
            ] if vital.recorded_by else [],
            "component": components if components else [{"code": {"text": "Vital signs"}, "valueString": "Recorded"}]
        }
        
        return _nullify_none(resource)

    @staticmethod
    def serialize_lab_result(lab_result):
        """Serialize LabResult to FHIR R4 Observation for individual lab values."""
        rec = lab_result.record
        
        status_map = {
            "pending": "registered",
            "resulted": "final",
            "verified": "amended"
        }
        fhir_status = status_map.get(lab_result.status, "unknown")
        
        resource = {
            "resourceType": "Observation",
            "id": str(lab_result.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Observation"],
                "lastUpdated": lab_result.result_date.isoformat() if lab_result.result_date else None
            },
            "status": fhir_status,
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "laboratory",
                            "display": "Laboratory"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "display": lab_result.test_name
                    }
                ],
                "text": lab_result.test_name
            },
            "subject": {
                "reference": f"Patient/{rec.patient_id}",
                "display": rec.patient.full_name if rec.patient else None
            },
            "encounter": {
                "reference": f"Encounter/{rec.id}"
            } if hasattr(rec, 'encounter_id') else None,
            "effectiveDateTime": lab_result.result_date.isoformat() if lab_result.result_date else None,
            "issued": lab_result.result_date.isoformat() if lab_result.result_date else None,
            "performer": [
                {
                    "reference": f"Practitioner/{lab_result.lab_tech.id}",
                    "display": lab_result.lab_tech.full_name if lab_result.lab_tech else None
                }
            ] if lab_result.lab_tech else [],
            "valueString": lab_result.result_value,
            "referenceRange": [
                {
                    "text": lab_result.reference_range,
                    "low": {
                        "value": _extract_numeric_dosage(lab_result.reference_range.split("-")[0]) if lab_result.reference_range and "-" in lab_result.reference_range else None
                    },
                    "high": {
                        "value": _extract_numeric_dosage(lab_result.reference_range.split("-")[1]) if lab_result.reference_range and "-" in lab_result.reference_range else None
                    }
                }
            ] if lab_result.reference_range else [],
            "interpretation": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation",
                            "code": "N",
                            "display": "Normal"
                        }
                    ]
                }
            ]
        }
        
        return _nullify_none(resource)


class FHIRDiagnosticReportSerializer:
    @staticmethod
    def serialize(lab_order, results=None):
        """Serialize LabOrder to FHIR R4 DiagnosticReport with linked observations."""
        rec = lab_order.record
        
        status_map = {
            "ordered": "registered",
            "collected": "partial",
            "in_progress": "partial",
            "resulted": "final",
            "verified": "amended"
        }
        fhir_status = status_map.get(lab_order.status, "unknown")

        resource = {
            "resourceType": "DiagnosticReport",
            "id": str(lab_order.id),
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/DiagnosticReport"],
                "lastUpdated": lab_order.resulted_at.isoformat() if lab_order.resulted_at else rec.created_at.isoformat() if rec.created_at else None
            },
            "status": fhir_status,
            "category": [
                {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                            "code": "LAB",
                            "display": "Laboratory"
                        }
                    ]
                }
            ],
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "display": lab_order.test_name
                    }
                ],
                "text": lab_order.test_name
            },
            "subject": {
                "reference": f"Patient/{rec.patient_id}",
                "display": rec.patient.full_name if rec.patient else None
            },
            "encounter": {
                "reference": f"Encounter/{rec.id}"
            } if hasattr(rec, 'encounter_id') else None,
            "effectiveDateTime": lab_order.collection_time.isoformat() if lab_order.collection_time else (rec.created_at.isoformat() if rec.created_at else None),
            "issued": lab_order.resulted_at.isoformat() if lab_order.resulted_at else (lab_order.started_at.isoformat() if lab_order.started_at else None),
            "performer": [
                {
                    "reference": f"Organization/{rec.hospital.id}",
                    "display": rec.hospital.name if rec.hospital else None
                }
            ] if rec.hospital else [],
            "resultsInterpreter": [
                {
                    "reference": f"Practitioner/{lab_order.assigned_to.id}",
                    "display": lab_order.assigned_to.full_name if lab_order.assigned_to else None
                }
            ] if lab_order.assigned_to else [],
            "specimen": [
                {
                    "reference": f"Specimen/{lab_order.id}",
                    "display": "Lab specimen"
                }
            ],
            "result": [
                {
                    "reference": f"Observation/{res.id}",
                    "display": res.test_name
                }
                for res in (results or [])
            ],
            "conclusion": f"Lab test {lab_order.test_name} completed with results" if lab_order.status == "resulted" or lab_order.status == "verified" else None,
            "conclusionCode": [
                {
                    "coding": [
                        {
                            "system": "http://snomed.info/sct",
                            "code": "371508000",
                            "display": "Laboratory procedure"
                        }
                    ]
                }
            ] if lab_order.status == "resulted" or lab_order.status == "verified" else None,
            "note": [
                {
                    "text": lab_order.notes
                }
            ] if lab_order.notes else []
        }
        
        return _nullify_none(resource)

class FHIRBundleSerializer:
    @staticmethod
    def serialize(entries, bundle_type="searchset", total=None):
        """Serialize list of FHIR resources into a Bundle with proper entries."""
        base_url = _get_base_url()
        
        bundle_entries = []
        for i, resource in enumerate(entries):
            entry = {
                "fullUrl": f"{base_url}/fhir/{resource['resourceType']}/{resource['id']}",
                "resource": resource,
                "search": {
                    "mode": "match",
                    "score": 1.0 - (i * 0.01)  # Scores decrease for order relevance
                } if bundle_type == "searchset" else None,
                "request": {
                    "method": "POST",
                    "url": resource['resourceType']
                } if bundle_type == "transaction" else None
            }
            bundle_entries.append(_nullify_none(entry))
        
        bundle = {
            "resourceType": "Bundle",
            "id": _generate_bundle_id(),
            "meta": {
                "lastUpdated": timezone.now().isoformat(),
                "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"]
            },
            "type": bundle_type,
            "total": total if total is not None else len(entries),
            "entry": bundle_entries
        }
        
        return _nullify_none(bundle)

def _generate_bundle_id():
    """Generate a unique Bundle ID."""
    import uuid
    return str(uuid.uuid4())
