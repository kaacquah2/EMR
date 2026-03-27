"use client";

import { useState, useCallback } from "react";
import { useApi } from "./use-api";
import type { Patient, PaginatedResponse } from "@/lib/types";

export function usePatientSearch() {
  const api = useApi();
  const [results, setResults] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const search = useCallback(
    async (query: string, type: "ghana_id" | "name" | "dob" = "name") => {
      if (!query.trim()) {
        setResults([]);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const params = new URLSearchParams();
        if (type === "ghana_id") params.set("ghana_health_id", query);
        else if (type === "dob") params.set("dob", query);
        else params.set("name", query);
        const data = await api.get<PaginatedResponse<Patient>>(
          `/patients/search?${params}`
        );
        setResults(data.data || []);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Search failed");
        setResults([]);
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { results, loading, error, search };
}

export function usePatient(id: string | null) {
  const api = useApi();
  const [patient, setPatient] = useState<Patient | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!id) {
      setPatient(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Patient>(`/patients/${id}`);
      setPatient(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load patient");
      setPatient(null);
    } finally {
      setLoading(false);
    }
  }, [api, id]);

  return { patient, loading, error, fetch };
}
