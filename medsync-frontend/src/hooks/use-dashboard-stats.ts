"use client";
import useSWR from "swr";
import { useApi } from "./use-api";
import type { DetailResponse } from "@/lib/types";

export interface DashboardStats {
  queue_count: number;
  critical_alerts: number;
  new_lab_results: number;
  pending_prescriptions: number;
  referrals_awaiting: number;
}

export function useDashboardStats() {
  const api = useApi();
  
  const { data, error, isLoading, mutate } = useSWR<DetailResponse<DashboardStats>>(
    "/dashboard",
    (url: string) => api.get<DetailResponse<DashboardStats>>(url),
    {
      revalidateOnFocus: true,
      dedupingInterval: 30000, // 30 seconds
    }
  );

  return {
    stats: data?.data || {
      queue_count: 0,
      critical_alerts: 0,
      new_lab_results: 0,
      pending_prescriptions: 0,
      referrals_awaiting: 0,
    },
    loading: isLoading,
    error: error?.message || null,
    refresh: mutate,
  };
}
