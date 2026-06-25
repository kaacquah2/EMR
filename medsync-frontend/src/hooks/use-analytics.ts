"use client";

import { useResource } from "./use-resource";

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
  const params = new URLSearchParams();
  if (from) params.set("from", from);
  if (to) params.set("to", to);
  if (groupBy) params.set("group_by", groupBy);
  const paramsStr = params.toString();
  const path = `/dashboard/analytics${paramsStr ? `?${paramsStr}` : ""}`;

  const { data, loading, refetch } = useResource<AnalyticsData>(
    enabled ? path : null
  );

  return { data: data ?? null, loading, fetch: refetch };
}
