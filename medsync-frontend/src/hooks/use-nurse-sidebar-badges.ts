import { useCallback, useState, useEffect } from "react";
import { useApi } from "./use-api";
import { usePollWhenVisible } from "./use-poll-when-visible";

interface NurseSidebarBadges {
  vitals_overdue_count: number;
  pending_dispense_count: number;
  active_alerts_count: number;
  loading: boolean;
  error: string | null;
}

export function useNurseSidebarBadges(enabled: boolean = true): NurseSidebarBadges {
  const api = useApi();
  const [result, setResult] = useState<NurseSidebarBadges>({
    vitals_overdue_count: 0,
    pending_dispense_count: 0,
    active_alerts_count: 0,
    loading: true,
    error: null,
  });

  const fetchBadges = useCallback(async () => {
    if (!enabled) {
      setResult({ vitals_overdue_count: 0, pending_dispense_count: 0, active_alerts_count: 0, loading: false, error: null });
      return;
    }

    try {
      // Fetch admissions dashboard data to get vitals overdue + alert counts
      const admissionsRes = await api.get<{
        data: Array<{
          vitals_overdue_hours: number | null;
          active_alerts_count: number;
          pending_dispense_count: number;
        }>;
      }>("/admissions/ward/dashboard");

      const admissions = Array.isArray(admissionsRes?.data) ? admissionsRes.data : [];

      // Count beds with vitals overdue
      const vitals_overdue_count = admissions.filter((a) => a.vitals_overdue_hours !== null).length;

      // Sum alert counts and dispense counts
      const active_alerts_count = admissions.reduce((sum, a) => sum + (a.active_alerts_count ?? 0), 0);
      const pending_dispense_count = admissions.reduce((sum, a) => sum + (a.pending_dispense_count ?? 0), 0);

      setResult({ vitals_overdue_count, pending_dispense_count, active_alerts_count, loading: false, error: null });
    } catch (err) {
      if (process.env.NODE_ENV === "development") {
        console.error("Failed to fetch nurse sidebar badges:", err);
      }
      setResult((prev) => ({ ...prev, loading: false, error: err instanceof Error ? err.message : "Unknown error" }));
    }
  }, [api, enabled]);

  // Initial fetch
  useEffect(() => {
    void fetchBadges();
  }, [fetchBadges]);

  // Poll every 60 seconds when visible
  usePollWhenVisible(fetchBadges, 60_000, enabled);

  return result;
}
