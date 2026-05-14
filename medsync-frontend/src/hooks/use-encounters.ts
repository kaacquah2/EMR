"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";
import type { Encounter } from "@/lib/types";

export function useEncounters(patientId: string | null) {
  const api = useApi();
  const [encounters, setEncounters] = useState<Encounter[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!patientId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ data: Encounter[] }>(`/patients/${patientId}/encounters`);
      setEncounters(data.data || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load encounters");
      setEncounters([]);
    } finally {
      setLoading(false);
    }
  }, [api, patientId]);

  useEffect(() => {
    if (patientId) fetch();
  }, [patientId, fetch]);

  return { encounters, loading, error, fetch };
}

export function useCreateEncounter(patientId: string | null) {
  const api = useApi();
  const [loading, setLoading] = useState(false);

  const create = useCallback(
    async (body: {
      encounter_type?: string;
      notes?: string;
      assigned_department_id?: string;
      assigned_doctor_id?: string;
      status?: "waiting" | "in_consultation" | "completed";
      chief_complaint?: string;
      hpi?: string;
      examination_findings?: string;
      assessment_plan?: string;
      discharge_summary?: string;
    }) => {
      if (!patientId) throw new Error("Patient ID required");
      setLoading(true);
      try {
        const response = await api.post<{ data: Encounter }>(`/patients/${patientId}/encounters`, body);
        return response.data;
      } finally {
        setLoading(false);
      }
    },
    [api, patientId]
  );

  return { create, loading };
}

export function useUpdateEncounter(patientId: string | null, encounterId: string | null) {
  const api = useApi();
  const [loading, setLoading] = useState(false);

  const update = useCallback(
    async (body: { discharge_summary?: string; visit_status?: string }) => {
      if (!patientId || !encounterId) throw new Error("Patient ID and Encounter ID required");
      setLoading(true);
      try {
        const response = await api.patch<{ data: Encounter }>(
          `/patients/${patientId}/encounters/${encounterId}`,
          body
        );
        return response.data;
      } finally {
        setLoading(false);
      }
    },
    [api, patientId, encounterId]
  );

  return { update, loading };
}

export interface WorklistEncounter {
  id: string;
  patient_id: string;
  patient_name: string;
  ghana_health_id: string;
  encounter_type: string;
  encounter_date: string;
  status: string;
  assigned_department_id: string | null;
  assigned_department_name: string | null;
  assigned_doctor_id: string | null;
  assigned_doctor_name: string | null;
  created_by: string | null;
  notes: string | null;
  has_active_allergy?: boolean;
  triage_badge?: "waiting" | "consulting";
  pending_labs?: number;
  pending_prescriptions?: number;
  active_alerts?: number;
}

export interface WorklistSummary {
  queue_count: number;
  pending_labs: number;
  pending_prescriptions: number;
  alerts: number;
  referrals: number;
}

export function useWorklistEncounters() {
  const api = useApi();
  const [encounters, setEncounters] = useState<WorklistEncounter[]>([]);
  const [summary, setSummary] = useState<WorklistSummary>({
    queue_count: 0,
    pending_labs: 0,
    pending_prescriptions: 0,
    alerts: 0,
    referrals: 0,
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async (silent = false, filters?: { department_id?: string; encounter_type?: string }) => {
    if (!silent) {
      setLoading(true);
      setError(null);
    }
    try {
      const params = new URLSearchParams();
      if (filters?.department_id) params.set("department_id", filters.department_id);
      if (filters?.encounter_type) params.set("encounter_type", filters.encounter_type);
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const data = await api.get<{ data: WorklistEncounter[]; summary?: WorklistSummary }>(`/worklist/encounters${suffix}`);
      setEncounters(data.data || []);
      if (data.summary) setSummary(data.summary);
    } catch (err) {
      if (!silent) setError(err instanceof Error ? err.message : "Failed to load worklist encounters");
      setEncounters([]);
      setSummary({ queue_count: 0, pending_labs: 0, pending_prescriptions: 0, alerts: 0, referrals: 0 });
    } finally {
      if (!silent) setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { encounters, summary, loading, error, fetch };
}
