"use client";

import { useState, useEffect } from "react";

export type ConnectionStatus = "online" | "offline" | "degraded";

interface ConnectionStatusResult {
  status: ConnectionStatus;
  lastOnline: Date | null;
  pendingSyncCount: number;
  setPendingSyncCount: (count: number) => void;
}

export function useConnectionStatus(): ConnectionStatusResult {
  const [status, setStatus] = useState<ConnectionStatus>("online");
  const [lastOnline, setLastOnline] = useState<Date | null>(null);
  const [pendingSyncCount, setPendingSyncCount] = useState(0);
  const [initialized, setInitialized] = useState(false);

  useEffect(() => {
    // Handle online/offline events
    const handleOnline = () => {
      setStatus("online");
      setLastOnline(new Date());
    };

    const handleOffline = () => {
      setStatus("offline");
    };

    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    // Initialize from navigator and check connection quality
    const initializeConnection = async () => {
      if (typeof navigator !== "undefined") {
        const isOnline = navigator.onLine;
        if (isOnline) {
          setLastOnline(new Date());
          // Check connection quality on initialization
          try {
            const start = Date.now();
            const controller = new AbortController();
            const timeout = setTimeout(() => controller.abort(), 5000);
            
            await fetch("/api/v1/health", {
              method: "HEAD",
              signal: controller.signal,
            });
            
            clearTimeout(timeout);
            const latency = Date.now() - start;
            
            // If latency > 3s, consider degraded
            setStatus(latency > 3000 ? "degraded" : "online");
          } catch {
            // Network request failed but we're "online" - degraded
            setStatus("degraded");
          }
        } else {
          setStatus("offline");
        }
      }
      setInitialized(true);
    };

    if (!initialized) {
      void initializeConnection();
    }

    // Check for degraded connection every 30 seconds
    const checkConnectionQuality = async () => {
      if (!navigator.onLine) return;
      
      try {
        const start = Date.now();
        const controller = new AbortController();
        const timeout = setTimeout(() => controller.abort(), 5000);
        
        await fetch("/api/v1/health", {
          method: "HEAD",
          signal: controller.signal,
        });
        
        clearTimeout(timeout);
        const latency = Date.now() - start;
        
        // If latency > 3s, consider degraded
        if (latency > 3000) {
          setStatus("degraded");
        } else {
          setStatus("online");
        }
      } catch {
        // Network request failed but we're "online" - degraded
        if (navigator.onLine) {
          setStatus("degraded");
        }
      }
    };

    const interval = setInterval(checkConnectionQuality, 30000);

    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearInterval(interval);
    };
  }, [initialized]);

  return { status, lastOnline, pendingSyncCount, setPendingSyncCount };
}
