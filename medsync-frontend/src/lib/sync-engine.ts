/**
 * Sync Engine for MedSync PWA
 * Handles FIFO processing of offline pending actions when connectivity restores.
 * Clinical data conflicts ALWAYS require manual review - never auto-resolved.
 */

import { pendingActionsStore, PendingAction } from "./offline-store";

type SyncStatus = "idle" | "syncing" | "error";
type ConflictResolution = "manual_required" | "resolved";

export interface SyncResult {
  action: PendingAction;
  success: boolean;
  error?: string;
  conflict?: {
    type: "version_mismatch" | "data_changed" | "permission_denied";
    serverData?: unknown;
    resolution: ConflictResolution;
  };
}

export interface SyncState {
  status: SyncStatus;
  lastSync: Date | null;
  pendingCount: number;
  conflictCount: number;
  results: SyncResult[];
}

let syncState: SyncState = {
  status: "idle",
  lastSync: null,
  pendingCount: 0,
  conflictCount: 0,
  results: [],
};

const listeners = new Set<(state: SyncState) => void>();

export function subscribeSyncState(callback: (state: SyncState) => void): () => void {
  listeners.add(callback);
  callback(syncState);
  return () => listeners.delete(callback);
}

function notifyListeners() {
  listeners.forEach((cb) => cb({ ...syncState }));
}

function updateSyncState(updates: Partial<SyncState>) {
  syncState = { ...syncState, ...updates };
  notifyListeners();
}

/**
 * Process all pending actions in FIFO order.
 * Each action is attempted once; failures are marked for retry or manual review.
 */
export async function syncPendingActions(
  apiClient: { fetch: (url: string, options?: RequestInit) => Promise<Response> }
): Promise<SyncResult[]> {
  if (syncState.status === "syncing") {
    console.log("Sync already in progress");
    return [];
  }

  const pending = await pendingActionsStore.getPending();
  if (pending.length === 0) {
    updateSyncState({ status: "idle", pendingCount: 0 });
    return [];
  }

  updateSyncState({ status: "syncing", pendingCount: pending.length, results: [] });
  const results: SyncResult[] = [];

  // Process in FIFO order (oldest first)
  const sorted = pending.sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
  );

  // Batch into groups of 20 to avoid overwhelming the server
  const BATCH_SIZE = 20;
  for (let i = 0; i < sorted.length; i += BATCH_SIZE) {
    const batch = sorted.slice(i, i + BATCH_SIZE);

    const batchResults = await Promise.all(
      batch.map((action) => processAction(action, apiClient))
    );

    results.push(...batchResults);

    // Update state after each batch
    updateSyncState({
      pendingCount: sorted.length - (i + batch.length),
      results: [...syncState.results, ...batchResults],
    });
  }

  const conflicts = results.filter((r) => r.conflict?.resolution === "manual_required");

  updateSyncState({
    status: conflicts.length > 0 ? "error" : "idle",
    lastSync: new Date(),
    pendingCount: await pendingActionsStore.count(),
    conflictCount: conflicts.length,
    results,
  });

  return results;
}

async function processAction(
  action: PendingAction,
  apiClient: { fetch: (url: string, options?: RequestInit) => Promise<Response> }
): Promise<SyncResult> {
  try {
    const response = await apiClient.fetch(action.endpoint, {
      method: action.method,
      headers: {
        "Content-Type": "application/json",
        "X-Offline-Action-Id": action.id,
      },
      body: action.body ? JSON.stringify(action.body) : undefined,
    });

    if (response.ok) {
      // Success - remove from pending queue
      await pendingActionsStore.remove(action.id);
      return { action, success: true };
    }

    if (response.status === 409) {
      // Version conflict - requires manual review for clinical data
      const serverData = await response.json().catch(() => null);

      // Mark as requiring manual resolution
      await pendingActionsStore.update(action.id, { status: "conflict" });

      return {
        action,
        success: false,
        error: "Version conflict - data was modified",
        conflict: {
          type: "version_mismatch",
          serverData,
          resolution: "manual_required", // NEVER auto-resolve clinical data
        },
      };
    }

    if (response.status === 401) {
      // Auth error - don't remove, user needs to re-login
      await pendingActionsStore.update(action.id, { status: "auth_error" });
      return {
        action,
        success: false,
        error: "Authentication expired - please log in again",
      };
    }

    if (response.status === 403) {
      // Permission denied - mark for review
      await pendingActionsStore.update(action.id, { status: "conflict" });
      return {
        action,
        success: false,
        error: "Permission denied",
        conflict: {
          type: "permission_denied",
          resolution: "manual_required",
        },
      };
    }

    // Other errors - increment retry count
    const newRetryCount = (action.retry_count || 0) + 1;
    if (newRetryCount >= 3) {
      await pendingActionsStore.update(action.id, { status: "failed" });
      return {
        action,
        success: false,
        error: `Failed after ${newRetryCount} attempts: HTTP ${response.status}`,
      };
    }

    await pendingActionsStore.update(action.id, { retry_count: newRetryCount });
    return {
      action,
      success: false,
      error: `HTTP ${response.status} - will retry`,
    };
  } catch (error) {
    // Network error - will retry on next sync
    const newRetryCount = (action.retry_count || 0) + 1;
    await pendingActionsStore.update(action.id, { retry_count: newRetryCount });

    return {
      action,
      success: false,
      error: error instanceof Error ? error.message : "Network error",
    };
  }
}

/**
 * Queue an action for offline sync
 */
export async function queueOfflineAction(
  actionType: string,
  endpoint: string,
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  body?: unknown
): Promise<string> {
  const id = await pendingActionsStore.add({
    action_type: actionType,
    endpoint,
    method,
    body,
  });

  updateSyncState({
    pendingCount: await pendingActionsStore.count(),
  });

  // Try to sync immediately if online
  if (typeof navigator !== "undefined" && navigator.onLine) {
    // Trigger background sync if available
    if ("serviceWorker" in navigator) {
      try {
        const registration = await navigator.serviceWorker.ready;
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        if ("sync" in registration && typeof (registration as any).sync?.register === "function") {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          await (registration as any).sync.register("sync-pending-actions").catch(() => {
            // Background Sync API not supported
          });
        }
      } catch {
        // Service worker not available
      }
    }
  }

  return id;
}

/**
 * Get conflicts that need manual review
 */
export async function getConflicts(): Promise<PendingAction[]> {
  const all = await pendingActionsStore.getAll();
  return all.filter((a) => a.status === "conflict");
}

/**
 * Resolve a conflict by discarding the offline action (keep server version)
 */
export async function discardConflict(actionId: string): Promise<void> {
  await pendingActionsStore.remove(actionId);
  updateSyncState({
    pendingCount: await pendingActionsStore.count(),
    conflictCount: Math.max(0, syncState.conflictCount - 1),
  });
}

/**
 * Resolve a conflict by retrying with the offline data (overwrite server)
 */
export async function retryWithForce(
  actionId: string,
  apiClient: { fetch: (url: string, options?: RequestInit) => Promise<Response> }
): Promise<SyncResult> {
  const all = await pendingActionsStore.getAll();
  const action = all.find((a) => a.id === actionId);
  
  if (!action) {
    throw new Error("Action not found");
  }

  // Add force flag to bypass version check
  const bodyWithForce = {
    ...(action.body as object || {}),
    _force_overwrite: true,
  };

  const result = await processAction(
    { ...action, body: bodyWithForce },
    apiClient
  );

  if (result.success) {
    updateSyncState({
      conflictCount: Math.max(0, syncState.conflictCount - 1),
    });
  }

  return result;
}

// Listen for online/offline events
if (typeof window !== "undefined") {
  window.addEventListener("online", () => {
    console.log("Connection restored - sync will be triggered");
    // The service worker will trigger sync via Background Sync API
  });

  // Listen for sync messages from service worker
  if ("BroadcastChannel" in window) {
    try {
      const channel = new BroadcastChannel("medsync-sync");
      channel.addEventListener("message", (event: MessageEvent) => {
        if (event.data?.type === "SYNC_TRIGGERED") {
          console.log("Background sync triggered by service worker");
          // The app should call syncPendingActions with its apiClient
        }
      });
    } catch {
      // BroadcastChannel not supported
    }
  }
}

export function getSyncState(): SyncState {
  return { ...syncState };
}
