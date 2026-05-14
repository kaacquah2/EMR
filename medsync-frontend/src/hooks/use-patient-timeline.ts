"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";
import type {
  TimelineEvent,
  TimelineEncounterEvent,
  TimelineAdmissionEvent,
  TimelineLabResultEvent,
  TimelineVitalEvent,
  TimelinePrescriptionEvent,
  TimelineAlertEvent,
  Encounter,
  LabResult,
  Vital,
  Prescription,
  ClinicalAlert,
} from "@/lib/types";

interface PatientAdmission {
  id: string;
  patient_id: string;
  ward_id: string;
  ward_name?: string;
  hospital_id: string;
  admitted_by: string;
  admitted_by_name?: string;
  admitted_at: string;
  discharged_at: string | null;
  discharge_reason?: string | null;
  created_at: string;
}

interface ApiResponse<T> {
  data: T[];
}

/**
 * Formats vital signs into a human-readable summary
 */
function formatVitalSummary(vital: Vital): string {
  const parts: string[] = [];
  if (vital.bp_systolic && vital.bp_diastolic) {
    parts.push(`BP: ${vital.bp_systolic}/${vital.bp_diastolic}`);
  }
  if (vital.pulse_bpm) parts.push(`HR: ${vital.pulse_bpm}`);
  if (vital.resp_rate) parts.push(`RR: ${vital.resp_rate}`);
  if (vital.temperature_c) parts.push(`Temp: ${vital.temperature_c}°C`);
  if (vital.spo2_percent) parts.push(`O₂: ${vital.spo2_percent}%`);
  return parts.length > 0 ? parts.join(", ") : "Vital signs recorded";
}

/**
 * Determines severity of a lab result based on status
 */
function getLabResultSeverity(
  status: string
): "normal" | "abnormal" | "critical" {
  if (status === "critical") return "critical";
  if (status === "abnormal") return "abnormal";
  return "normal";
}

/**
 * Transforms a raw Encounter into a TimelineEncounterEvent
 */
function transformEncounter(encounter: Encounter): TimelineEncounterEvent {
  return {
    type: "encounter",
    id: encounter.id,
    date: encounter.encounter_date,
    encounter,
    provider: encounter.assigned_doctor_name || encounter.created_by,
  };
}

/**
 * Transforms a raw PatientAdmission into a TimelineAdmissionEvent
 */
function transformAdmission(
  admission: PatientAdmission
): TimelineAdmissionEvent {
  return {
    type: "admission",
    id: admission.id,
    date: admission.admitted_at,
    admission_date: admission.admitted_at,
    discharge_date: admission.discharged_at,
    ward_name: admission.ward_name,
    reason: admission.discharge_reason || undefined,
    provider: admission.admitted_by_name || undefined,
  };
}

/**
 * Transforms a raw LabResult into a TimelineLabResultEvent
 */
function transformLabResult(labResult: LabResult): TimelineLabResultEvent {
  return {
    type: "lab_result",
    id: labResult.lab_result_id,
    date: labResult.result_date || labResult.created_at,
    lab_result: labResult,
    test_name: labResult.test_name,
    result_value: labResult.result_value,
    reference_range: labResult.reference_range,
    status: getLabResultSeverity(labResult.status),
    severity: getLabResultSeverity(labResult.status),
  };
}

/**
 * Transforms a raw Vital into a TimelineVitalEvent
 */
function transformVital(vital: Vital): TimelineVitalEvent {
  return {
    type: "vital",
    id: vital.vital_id,
    date: vital.created_at,
    vital,
    summary: formatVitalSummary(vital),
  };
}

/**
 * Transforms a raw Prescription into a TimelinePrescriptionEvent
 */
function transformPrescription(
  prescription: Prescription
): TimelinePrescriptionEvent {
  return {
    type: "prescription",
    id: prescription.prescription_id,
    date: prescription.created_at,
    prescription,
    drug_name: prescription.drug_name,
    dosage: prescription.dosage,
    frequency: prescription.frequency,
    dispense_status: prescription.dispense_status,
  };
}

/**
 * Transforms a raw ClinicalAlert into a TimelineAlertEvent
 */
function transformAlert(alert: ClinicalAlert): TimelineAlertEvent {
  return {
    type: "alert",
    id: alert.id,
    date: alert.created_at,
    alert,
    message: alert.message,
    severity: alert.severity,
  };
}

/**
 * Extracts the date from a timeline event for sorting
 */
function getEventDate(event: TimelineEvent): Date {
  return new Date(event.date);
}

/**
 * Hook to fetch and merge patient timeline events from multiple endpoints
 * @param patientId - The patient ID to fetch timeline for
 * @returns Object with events, loading, error, and refetch method
 */
export function usePatientTimeline(patientId: string | null) {
  const api = useApi();
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchTimeline = useCallback(async () => {
    if (!patientId) {
      setEvents([]);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Fetch all timeline data in parallel
      const [encountersRes, admissionsRes, labResultsRes, vitalsRes, prescriptionsRes, alertsRes] =
        await Promise.all([
          api
            .get<ApiResponse<Encounter>>(
              `/patients/${patientId}/encounters`
            )
            .catch(() => ({ data: [] })),
          api
            .get<ApiResponse<PatientAdmission>>(
              `/patients/${patientId}/admissions`
            )
            .catch(() => ({ data: [] })),
          api
            .get<ApiResponse<LabResult>>(
              `/patients/${patientId}/lab-results`
            )
            .catch(() => ({ data: [] })),
          api
            .get<ApiResponse<Vital>>(
              `/patients/${patientId}/vitals`
            )
            .catch(() => ({ data: [] })),
          api
            .get<ApiResponse<Prescription>>(
              `/patients/${patientId}/prescriptions`
            )
            .catch(() => ({ data: [] })),
          api
            .get<ApiResponse<ClinicalAlert>>(
              `/patients/${patientId}/alerts`
            )
            .catch(() => ({ data: [] })),
        ]);

      // Transform all events
      const transformedEvents: TimelineEvent[] = [];

      // Transform encounters
      if (Array.isArray(encountersRes.data)) {
        transformedEvents.push(
          ...encountersRes.data.map((e) => transformEncounter(e))
        );
      }

      // Transform admissions
      if (Array.isArray(admissionsRes.data)) {
        transformedEvents.push(
          ...admissionsRes.data.map((a) => transformAdmission(a))
        );
      }

      // Transform lab results
      if (Array.isArray(labResultsRes.data)) {
        transformedEvents.push(
          ...labResultsRes.data.map((l) => transformLabResult(l))
        );
      }

      // Transform vitals
      if (Array.isArray(vitalsRes.data)) {
        transformedEvents.push(
          ...vitalsRes.data.map((v) => transformVital(v))
        );
      }

      // Transform prescriptions
      if (Array.isArray(prescriptionsRes.data)) {
        transformedEvents.push(
          ...prescriptionsRes.data.map((p) => transformPrescription(p))
        );
      }

      // Transform alerts
      if (Array.isArray(alertsRes.data)) {
        transformedEvents.push(
          ...alertsRes.data.map((a) => transformAlert(a))
        );
      }

      // Sort by date descending (newest first)
      const sortedEvents = transformedEvents.sort((a, b) => {
        const dateA = getEventDate(a);
        const dateB = getEventDate(b);
        return dateB.getTime() - dateA.getTime();
      });

      setEvents(sortedEvents);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to load patient timeline";
      setError(errorMessage);
      setEvents([]);
    } finally {
      setLoading(false);
    }
  }, [api, patientId]);

  useEffect(() => {
    fetchTimeline();
  }, [fetchTimeline]);

  return {
    events,
    loading,
    error,
    refetch: fetchTimeline,
  };
}
