"""
AI-powered discharge summary generation service.

Gathers encounter context (diagnoses, prescriptions, vitals, nursing notes)
and delegates to the LLM client to produce a structured discharge summary.
"""

import logging
from django.utils.timezone import now, timedelta

logger = logging.getLogger(__name__)

DISCHARGE_SYSTEM_PROMPT = (
    "You are a clinical documentation assistant for a Ghanaian hospital EMR. "
    "Generate a professional discharge summary based on the provided encounter data. "
    "Always respond with valid JSON matching the specified schema exactly."
)


def build_discharge_prompt(context: dict) -> str:
    diagnoses_str = ", ".join(context.get("diagnoses") or []) or "None recorded"
    meds_str = ", ".join(context.get("prescriptions") or []) or "None"
    return f"""Generate a discharge summary for this patient encounter:

Patient: {context.get("age", "Unknown")} year-old {context.get("sex", "unknown")}
Encounter type: {context.get("encounter_type", "outpatient")}
Chief complaint: {context.get("chief_complaint") or "Not recorded"}
History of presenting illness: {context.get("hpi") or "Not recorded"}
Examination findings: {context.get("examination_findings") or "Not recorded"}
Assessment/Plan: {context.get("assessment_plan") or "Not recorded"}
Diagnoses: {diagnoses_str}
Medications prescribed: {meds_str}
Latest vitals: {context.get("vitals") or "Not recorded"}
Nursing notes: {context.get("nursing_notes") or "None"}

Return a JSON object with this exact structure:
{{
  "admission_summary": "2-3 sentence summary of the presentation and reason for encounter",
  "clinical_course": "Brief description of the clinical course during the encounter",
  "diagnoses_list": ["diagnosis 1", "diagnosis 2"],
  "investigations_summary": "Summary of investigations performed",
  "treatment_given": "Summary of treatment provided during the encounter",
  "discharge_medications": ["Drug name dose frequency duration", "..."],
  "follow_up_instructions": "Follow-up instructions for the patient",
  "condition_at_discharge": "Good|Fair|Improved|Stable"
}}"""


def get_encounter_context(encounter, patient) -> dict:
    """Gather clinical data from the encounter and patient for summary generation."""
    from records.models import Diagnosis, Prescription, MedicalRecord, NursingNote

    # Age
    age = None
    if patient.date_of_birth:
        today = now().date()
        dob = patient.date_of_birth
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    # Recent diagnoses for this patient at this hospital
    diagnoses = list(
        Diagnosis.objects.filter(
            record__patient=patient,
            record__hospital=encounter.hospital,
        )
        .order_by("-record__created_at")
        .values_list("icd10_description", flat=True)[:10]
    )

    # Active prescriptions from the last 7 days
    cutoff = now() - timedelta(days=7)
    rx_qs = (
        Prescription.objects.filter(
            record__patient=patient,
            record__hospital=encounter.hospital,
            record__created_at__gte=cutoff,
            dispense_status__in=["pending", "dispensed"],
        )
        .select_related("record")
        .order_by("-record__created_at")[:10]
    )
    prescriptions = [
        f"{rx.drug_name} {rx.dosage} {rx.frequency}"
        + (f" x{rx.duration_days}d" if rx.duration_days else "")
        for rx in rx_qs
    ]

    # Latest vital signs
    vitals_str = None
    latest_record = (
        MedicalRecord.objects.filter(
            patient=patient,
            hospital=encounter.hospital,
            record_type="vital_signs",
        )
        .order_by("-created_at")
        .first()
    )
    if latest_record:
        try:
            v = latest_record.vital
            parts = []
            if v.temperature_c:
                parts.append(f"Temp {v.temperature_c}°C")
            if v.bp_systolic and v.bp_diastolic:
                parts.append(f"BP {v.bp_systolic}/{v.bp_diastolic}")
            if v.pulse_bpm:
                parts.append(f"HR {v.pulse_bpm}bpm")
            if v.resp_rate:
                parts.append(f"RR {v.resp_rate}/min")
            if v.spo2_percent:
                parts.append(f"SpO2 {v.spo2_percent}%")
            if parts:
                vitals_str = ", ".join(parts)
        except Exception:
            pass

    # Recent nursing notes (last 2)
    notes_qs = (
        NursingNote.objects.filter(
            record__patient=patient,
            record__hospital=encounter.hospital,
        )
        .order_by("-record__created_at")[:2]
    )
    nursing_notes = ". ".join(n.content for n in notes_qs if n.content) or None

    return {
        "age": age,
        "sex": patient.gender,
        "encounter_type": encounter.encounter_type,
        "chief_complaint": encounter.chief_complaint,
        "hpi": encounter.hpi,
        "examination_findings": encounter.examination_findings,
        "assessment_plan": encounter.assessment_plan,
        "diagnoses": diagnoses,
        "prescriptions": prescriptions,
        "vitals": vitals_str,
        "nursing_notes": nursing_notes,
    }


def format_discharge_summary(result: dict) -> str:
    """Convert structured discharge summary dict to plain text for storage."""
    sections = []

    if result.get("admission_summary"):
        sections.append(f"ADMISSION SUMMARY\n{result['admission_summary']}")

    if result.get("clinical_course"):
        sections.append(f"CLINICAL COURSE\n{result['clinical_course']}")

    if result.get("diagnoses_list"):
        items = "\n".join(f"• {d}" for d in result["diagnoses_list"])
        sections.append(f"DIAGNOSES\n{items}")

    if result.get("investigations_summary"):
        sections.append(f"INVESTIGATIONS\n{result['investigations_summary']}")

    if result.get("treatment_given"):
        sections.append(f"TREATMENT GIVEN\n{result['treatment_given']}")

    if result.get("discharge_medications"):
        items = "\n".join(f"• {m}" for m in result["discharge_medications"])
        sections.append(f"DISCHARGE MEDICATIONS\n{items}")

    if result.get("follow_up_instructions"):
        sections.append(f"FOLLOW-UP\n{result['follow_up_instructions']}")

    if result.get("condition_at_discharge"):
        sections.append(f"CONDITION AT DISCHARGE: {result['condition_at_discharge']}")

    return "\n\n".join(sections)


def generate_discharge_summary(encounter, patient) -> dict:
    """Generate AI-powered discharge summary for an encounter."""
    from api.services.llm_client import llm_client, BedrockInvocationError

    context = get_encounter_context(encounter, patient)
    prompt = build_discharge_prompt(context)

    try:
        return llm_client.invoke_json(prompt=prompt, system=DISCHARGE_SYSTEM_PROMPT)
    except BedrockInvocationError:
        raise
    except Exception as e:
        logger.error("Unexpected error in generate_discharge_summary: %s", e, exc_info=True)
        raise
