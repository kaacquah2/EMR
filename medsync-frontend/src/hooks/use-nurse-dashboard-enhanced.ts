"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "./use-api";

/**
 * Enhanced nurse dashboard data combining bed grid, prescriptions, and alerts
 */

export interface BedData {
  bed_code: string;
  patient_id: string | null;
  patient_name: string | null;
  age: number | null;
  gender: string | null;
  admission_date: string | null;
  status: "stable" | "watch" | "critical" | "vacant";
  last_vitals_at: string | null;
  vitals_overdue: boolean;
  vitals_overdue_hours: number | null;
  active_alerts_count: number;
  pending_dispense_count: number;
}

export interface PendingPrescription {
  prescription_id: string;
  drug_name: string;
  dosage: string;
  route: string;
  frequency: string;
  patient_id: string;
  patient_name: string;
  bed_code: string | null;
  prescribed_by: string;
  created_at: string;
  allergy_conflict: boolean;
  allergy_override_reason: string | null;
  allergy_override_by: string | null;
}

export interface ActiveAlert {
  alert_id: string;
  type: string;
  severity: "critical" | "high" | "medium" | "low";
  patient_id: string;
  patient_name: string;
  bed_code: string | null;
  message: string;
  created_at: string;
}

export interface NurseDashboardEnhanced {
  beds: BedData[];
  pending_prescriptions: PendingPrescription[];
  active_alerts: ActiveAlert[];
  stats: {
    admitted_count: number;
    vitals_overdue_count: number;
    pending_dispense_count: number;
    active_alerts_count: number;
  };
  last_refreshed: Date;
}

/**
 * Fetches all enhanced nurse dashboard data from multiple endpoints
 * Combines bed grid, pending prescriptions, and active alerts
 */
export function useNurseDashboardEnhanced(wardId?: string) {
  const api = useApi();
  const [data, setData] = useState<NurseDashboardEnhanced | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!wardId) return;

    setLoading(true);
    setError(null);

    try {
      // Fetch all data in parallel
      const [bedsResp, prescriptionsResp, alertsResp] = await Promise.all([
        api.get<{ data: BedData[] }>(
          `/admissions/ward/${wardId}/dashboard`
        ),
        api.get<{ data: PendingPrescription[] }>(
          "/records/prescriptions/pending-by-ward"
        ),
        api.get<{ data: ActiveAlert[] }>(
          "/alerts/active-by-ward"
        ),
      ]);

      // Calculate stats
      const beds = bedsResp.data || [];
      const prescriptions = prescriptionsResp.data || [];
      const alerts = alertsResp.data || [];

      const admitted_count = beds.filter(b => b.patient_id).length;
      const vitals_overdue_count = beds.filter(
        b => b.vitals_overdue && b.patient_id
      ).length;
      const pending_dispense_count = prescriptions.length;
      const active_alerts_count = alerts.length;

      setData({
        beds,
        pending_prescriptions: prescriptions,
        active_alerts: alerts,
        stats: {
          admitted_count,
          vitals_overdue_count,
          pending_dispense_count,
          active_alerts_count,
        },
        last_refreshed: new Date(),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch dashboard data");
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [api, wardId]);

  useEffect(() => {
    if (wardId) {
      void fetch();
    }
  }, [fetch, wardId]);

  return { data, loading, error, fetch };
}

/**
 * Simple hook for just the bed grid data
 */
export function useWardBedGrid(wardId?: string) {
  const api = useApi();
  const [beds, setBeds] = useState<BedData[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    if (!wardId) return;
    try {
      const resp = await api.get<{ data: BedData[] }>(
        `/admissions/ward/${wardId}/dashboard`
      );
      setBeds(resp.data || []);
    } catch {
      setBeds([]);
    } finally {
      setLoading(false);
    }
  }, [api, wardId]);

  useEffect(() => {
    if (wardId) {
      void fetch();
    }
  }, [fetch, wardId]);

  return { beds, loading, fetch };
}

/**
 * Simple hook for pending prescriptions
 */
export function usePendingPrescriptions() {
  const api = useApi();
  const [prescriptions, setPrescriptions] = useState<PendingPrescription[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const resp = await api.get<{ data: PendingPrescription[] }>(
        "/records/prescriptions/pending-by-ward"
      );
      setPrescriptions(resp.data || []);
    } catch {
      setPrescriptions([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { prescriptions, loading, fetch };
}

/**
 * Simple hook for active alerts
 */
export function useActiveAlerts() {
  const api = useApi();
  const [alerts, setAlerts] = useState<ActiveAlert[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    try {
      const resp = await api.get<{ data: ActiveAlert[] }>(
        "/alerts/active-by-ward"
      );
      setAlerts(resp.data || []);
    } catch {
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void fetch();
  }, [fetch]);

  return { alerts, loading, fetch };
}
