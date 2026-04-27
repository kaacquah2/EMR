"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "./use-api";

export interface NurseDashboardData {
  ward_id: string;
  ward_name: string;
  admitted_count: number;
  vitals_overdue_count: number;
  pending_dispense_count: number;
  current_shift: string;
  shift: {
    status: string;
    shift_id?: string;
    remaining_seconds?: number;
  };
  priority_worklist: Array<{
    type: "VITALS_DUE" | "DISPENSE";
    patient_id: string;
    patient_name: string;
    bed_code?: string | null;
    drug_name?: string;
    record_id?: string;
    last_recorded?: string | null;
  }>;
}

export interface NurseWorklistData {
  ward_id: string;
  ward_name: string;
  beds: Array<{
    bed_id: string;
    bed_code: string;
    status: "stable" | "watch" | "critical" | "available";
    patient_id?: string;
    patient_name?: string;
    admitted_at?: string;
    admitted_for?: string;
    last_vitals_at?: string | null;
    vitals_due?: boolean;
  }>;
  dispense_items: Array<{
    record_id: string;
    patient_id: string;
    patient_name: string;
    bed_code?: string | null;
    drug_name: string;
    dosage: string;
    frequency: string;
    route: string;
    written_by?: string | null;
    written_at: string;
    allergy_conflict: boolean;
    allergy_override_reason?: string | null;
  }>;
  incoming_nurse_candidates: Array<{ user_id: string; full_name: string }>;
  handover_pending_ack: Array<{
    note_id: string;
    patient_id: string;
    patient_name: string;
    outgoing_nurse_name?: string | null;
    content: string;
    signed_at?: string | null;
  }>;
}

export function useNurseDashboard() {
  const api = useApi();
  const [data, setData] = useState<NurseDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<NurseDashboardData>("/nurse/dashboard");
      setData(resp);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load nurse dashboard";
      setError(message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { data, loading, error, fetch };
}

export function useNurseWorklist() {
  const api = useApi();
  const [data, setData] = useState<NurseWorklistData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await api.get<NurseWorklistData>("/nurse/worklist");
      setData(resp);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to load nurse worklist";
      setError(message);
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  const dispense = useCallback(
    async (recordId: string) => {
      await api.post(`/records/prescription/${recordId}/dispense-by-nurse`, {});
      await fetch();
    },
    [api, fetch]
  );

  const acknowledgeHandover = useCallback(
    async (noteId: string) => {
      await api.post(`/nurse/handover/${noteId}/acknowledge`, {});
      await fetch();
    },
    [api, fetch]
  );

  return { data, loading, error, fetch, dispense, acknowledgeHandover };
}
