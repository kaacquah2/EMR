"use client";

import { useState, useCallback, useEffect } from "react";
import { useApi } from "./use-api";
import { useAuth } from "@/lib/auth-context";

export function useDashboardMetrics() {
  const api = useApi();
  const { user } = useAuth();
  const [metrics, setMetrics] = useState<Record<string, unknown>>({});
  const [loading, setLoading] = useState(true);

  const fetch = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    try {
      const data = await api.get<Record<string, unknown>>("/dashboard/metrics");
      setMetrics(data || {});
    } catch {
      // Keep last-known metrics to avoid flashing "Error" on transient failures.
    } finally {
      setLoading(false);
    }
  }, [api, user]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { metrics, loading, fetch };
}
