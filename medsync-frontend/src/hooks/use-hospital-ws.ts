"use client";

import { useEffect, useRef } from "react";
import { getWebSocketBase } from "@/lib/api-base";

export interface WSEvent {
  type: string;
  payload: unknown;
}

/**
 * Hook to manage a hospital-wide WebSocket connection.
 * 
 * @param hospitalId The hospital ID to subscribe to.
 * @param onMessage Callback for incoming messages.
 */
export function useHospitalWS(
  hospitalId: string | null | undefined,
  onMessage: (data: WSEvent) => void
) {
  const onMessageRef = useRef(onMessage);
  
  // Use useEffect to update the ref to avoid updating during render
  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    if (!hospitalId || typeof window === "undefined") return;

    const wsBase = getWebSocketBase();
    const wsUrl = `${wsBase}/ws/alerts/${hospitalId}/`;
    let ws: WebSocket | null = null;
    let reconnectTimeout: ReturnType<typeof setTimeout>;
    let isMounted = true;

    const connect = () => {
      if (!isMounted) return;

      try {
        ws = new WebSocket(wsUrl);

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            onMessageRef.current(data);
          } catch (e) {
            console.error("Failed to parse WS message", e);
          }
        };

        ws.onclose = (e) => {
          ws = null;
          if (isMounted && e.code !== 4003) { // 4003 is Forbidden
            reconnectTimeout = setTimeout(connect, 5000);
          }
        };

        ws.onerror = () => {
          ws?.close();
        };
      } catch (e) {
        console.error("WS connection error", e);
        if (isMounted) {
          reconnectTimeout = setTimeout(connect, 5000);
        }
      }
    };

    connect();

    return () => {
      isMounted = false;
      clearTimeout(reconnectTimeout);
      if (ws) {
        ws.close();
      }
    };
  }, [hospitalId]);
}
