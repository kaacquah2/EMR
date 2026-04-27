"use client";

import { useState, useEffect, useCallback } from "react";
import {
  subscribeSyncState,
  syncPendingActions,
  getSyncState,
  queueOfflineAction,
  getConflicts,
  discardConflict,
  retryWithForce,
  type SyncResult,
} from "@/lib/sync-engine";
import { PendingAction } from "@/lib/offline-store";
import { useAuth } from "@/lib/auth-context";

export function useSync() {
  const [state, setState] = useState(getSyncState());
  const [conflicts, setConflicts] = useState<PendingAction[]>([]);
  const { getAccessToken } = useAuth();

  useEffect(() => {
    const unsubscribe = subscribeSyncState(setState);

    // Load conflicts
    getConflicts().then(setConflicts);

    return unsubscribe;
  }, []);

  const createFetchFunction = useCallback(() => {
    return async (url: string, options?: RequestInit): Promise<Response> => {
      try {
        // Use the raw fetch to get a Response object
        const method = options?.method || "GET";
        const token = getAccessToken();
        const headers: HeadersInit = {
          "Content-Type": "application/json",
          ...(options?.headers as Record<string, string>),
        };
        if (token) {
          (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
        }

        const res = await fetch(url, {
          ...options,
          method,
          headers,
        });
        return res;
      } catch (error) {
        // Return a response-like error
        throw error;
      }
    };
  }, [getAccessToken]);

  const sync = useCallback(async () => {
    const results = await syncPendingActions({
      fetch: createFetchFunction(),
    });

    // Refresh conflicts
    const newConflicts = await getConflicts();
    setConflicts(newConflicts);

    return results;
  }, [createFetchFunction]);

  const queue = useCallback(
    (
      actionType: string,
      endpoint: string,
      method: "POST" | "PUT" | "PATCH" | "DELETE",
      body?: unknown
    ) => {
      return queueOfflineAction(actionType, endpoint, method, body);
    },
    []
  );

  const resolveDiscard = useCallback(async (actionId: string) => {
    await discardConflict(actionId);
    setConflicts((prev) => prev.filter((c) => c.id !== actionId));
  }, []);

  const resolveRetry = useCallback(async (actionId: string): Promise<SyncResult> => {
    const result = await retryWithForce(actionId, {
      fetch: createFetchFunction(),
    });

    if (result.success) {
      setConflicts((prev) => prev.filter((c) => c.id !== actionId));
    }

    return result;
  }, [createFetchFunction]);

  return {
    status: state.status,
    lastSync: state.lastSync,
    pendingCount: state.pendingCount,
    conflictCount: state.conflictCount,
    conflicts,
    sync,
    queue,
    resolveDiscard,
    resolveRetry,
  };
}
