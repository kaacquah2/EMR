"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "./use-api";
import { useResource } from "./use-resource";
import { getWebSocketBase } from "@/lib/api-base";
import type { ClinicalAlert } from "@/lib/types";

export function useAlerts(
  status?: string,
  severity?: string,
  hospitalId?: string | null
) {
  const params = new URLSearchParams();
  if (status) params.set("status", status);
  if (severity) params.set("severity", severity);
  const paramsStr = params.toString();
  const path = `/alerts${paramsStr ? `?${paramsStr}` : ""}`;

  const { data, loading, error, refetch } = useResource<{ data: ClinicalAlert[] }>(path);

  // Keep refetch stable for the WebSocket callback.
  const refetchRef = useRef(refetch);
  refetchRef.current = refetch;

  // Real-time: subscribe to the hospital WebSocket; refetch on any message.
  useEffect(() => {
    if (!hospitalId || typeof window === "undefined") return;
    const wsBase = getWebSocketBase();
    const wsUrl = `${wsBase}/ws/alerts/${hospitalId}/`;
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;

    const connect = () => {
      try {
        ws = new WebSocket(wsUrl);
        ws.onmessage = () => { refetchRef.current?.(); };
        ws.onclose = () => {
          ws = null;
          reconnectTimeout = setTimeout(connect, 5000);
        };
        ws.onerror = () => { ws?.close(); };
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

  return { alerts: data?.data ?? [], loading, error, fetch: refetch };
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
