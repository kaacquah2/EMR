"use client";

import useSWR from 'swr';
import { useCallback } from "react";
import { useApi } from "./use-api";
import type { Patient, PaginatedResponse } from "@/lib/types";

export function usePatientSearch() {
  const api = useApi();
  
  // UX-01: memoize fetcher to prevent React Compiler skip
  const fetcher = useCallback((url: string) => api.get<PaginatedResponse<Patient>>(url), [api]);
  
  const { data, error, isLoading, mutate } = useSWR<PaginatedResponse<Patient>>(
    undefined, 
    fetcher,
    { revalidateOnFocus: false }
  );

  const search = useCallback(
    async (query: string, type: "ghana_id" | "name" | "dob" = "name") => {
      if (!query.trim()) {
        mutate({ data: [], next_cursor: undefined, has_more: false }, false);
        return;
      }
      
      const params = new URLSearchParams();
      if (type === "ghana_id") params.set("ghana_health_id", query);
      else if (type === "dob") params.set("dob", query);
      else params.set("name", query);
      
      const url = `/patients/search?${params}`;
      await mutate(fetcher(url), {
        revalidate: false,
        populateCache: true,
      });
    },
    [mutate, fetcher]
  );

  return { 
    results: data?.data || [], 
    loading: isLoading, 
    error: error?.message || null, 
    search 
  };
}

export function usePatient(id: string | null) {
  const api = useApi();
  
  const { data, error, isLoading, mutate } = useSWR<Patient>(
    id ? `/patients/${id}` : undefined,
    (url: string) => api.get<Patient>(url),
    {
      dedupingInterval: 60000, // SWR uses dedupingInterval for "stale time"
      revalidateOnFocus: true,
    }
  );

  return { 
    patient: data || null, 
    loading: isLoading, 
    error: error?.message || null, 
    fetch: mutate 
  };
}

