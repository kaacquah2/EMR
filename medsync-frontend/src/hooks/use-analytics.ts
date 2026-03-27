"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";

export interface AnalyticsData {
  from: string;
  to: string;
  patients_total: number;
  encounters_total: number;
  patients_by_day?: { date: string; count: number }[];
  encounters_by_day?: { date: string; count: number }[];
}

/**
 * Dashboard analytics (patients/encounters by date). Backend allows only
 * super_admin, hospital_admin, doctor. Pass enabled: false for other roles to avoid 403.
 */
export function useDashboardAnalytics(
  from?: string,
  to?: string,
  groupBy?: string,
  enabled: boolean = true
) {
  const api = useApi();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(false);

  const fetch = useCallback(async () => {
    if (!enabled) return;
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (from) params.set("from", from);
      if (to) params.set("to", to);
      if (groupBy) params.set("group_by", groupBy);
      const result = await api.get<AnalyticsData>(`/dashboard/analytics?${params}`);
      setData(result);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [api, from, to, groupBy, enabled]);

  useEffect(() => {
    if (enabled) fetch();
  }, [enabled, fetch]);

  return { data, loading, fetch };
}
