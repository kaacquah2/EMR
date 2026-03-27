"use client";

import { useState, useCallback, useEffect, useRef } from "react";
import { useApi } from "./use-api";
import { getWebSocketBase } from "@/lib/api-base";
import type { ClinicalAlert } from "@/lib/types";

export function useAlerts(
  status?: string,
  severity?: string,
  hospitalId?: string | null
) {
  const api = useApi();
  const [alerts, setAlerts] = useState<ClinicalAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const fetchRef = useRef<(() => Promise<void>) | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (status) params.set("status", status);
      if (severity) params.set("severity", severity);
      const data = await api.get<{ data: ClinicalAlert[] }>(`/alerts?${params}`);
      setAlerts(data.data || []);
    } catch {
      setAlerts([]);
    } finally {
      setLoading(false);
    }
  }, [api, status, severity]);

  fetchRef.current = fetch;

  useEffect(() => {
    fetch();
  }, [fetch]);

  // Real-time: subscribe to WebSocket for this hospital; on message refetch alerts.
  useEffect(() => {
    if (!hospitalId || typeof window === "undefined") return;
    const wsBase = getWebSocketBase();
    const wsUrl = `${wsBase}/ws/alerts/${hospitalId}/`;
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = () => {
          fetchRef.current?.();
        };
        ws.onclose = () => {
          ws = null;
          reconnectTimeout = setTimeout(connect, 5000);
        };
        ws.onerror = () => {
          ws?.close();
        };
      } catch {
        reconnectTimeout = setTimeout(connect, 5000);
      }
    };
    connect();
    return () => {
      clearTimeout(reconnectTimeout);
      ws?.close();
    };
  }, [hospitalId]);

  return { alerts, loading, fetch };
}

export function useResolveAlert() {
  const api = useApi();
  const [loading, setLoading] = useState(false);

  const resolve = useCallback(
    async (id: string) => {
      setLoading(true);
      try {
        await api.patch<{ id: string; status: string; resolved_at: string }>(`/alerts/${id}/resolve`, {});
        return true;
      } catch {
        return false;
      } finally {
        setLoading(false);
      }
    },
    [api]
  );

  return { resolve, loading };
}
