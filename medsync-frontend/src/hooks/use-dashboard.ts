"use client";

import useSWR from "swr";
import { useApi } from "./use-api";
import type { DetailResponse } from "@/lib/types";

export function useDashboardMetrics() {
  const api = useApi();
  
  const { data, error, isLoading, mutate } = useSWR<DetailResponse<Record<string, unknown>>>(
    "/dashboard/metrics",
    (url: string) => api.get<DetailResponse<Record<string, unknown>>>(url),
    {
      revalidateOnFocus: true,
      dedupingInterval: 60000,
    }
  );

  return { 
    metrics: data?.data || {}, 
    loading: isLoading, 
    error: error?.message || null, 
    fetch: mutate 
  };
}
