"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";
import { useAuth } from "@/lib/auth-context";

export function useDashboardMetrics() {
  const api = useApi();
  const { user } = useAuth();
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<Record<string, unknown>>("/dashboard/metrics");
      setMetrics(data || {});
    } catch (err) {
      // Keep last-known metrics to avoid flashing "Error" on transient failures
      const message = err instanceof Error ? err.message : "Failed to load dashboard metrics";
      setError(message);
      if (process.env.NODE_ENV === 'development') {
        console.error("Dashboard metrics fetch failed:", message);
      }
    } finally {
      setLoading(false);
    }
  }, [api, user]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { metrics, loading, error, fetch };
}
