"use client";

import { useSync } from "@/hooks/use-sync";
import { useConnectionStatus } from "@/hooks/use-connection-status";
import { Cloud, CloudOff, RefreshCw, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";

export function SyncStatusIndicator() {
  const { isOnline } = useConnectionStatus();
  const { status, pendingCount, conflictCount, sync } = useSync();

  const isSyncing = status === "syncing";
  const hasPending = pendingCount > 0;
  const hasConflicts = conflictCount > 0;

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 rounded-full bg-slate-100 dark:bg-slate-800 text-xs font-medium border border-slate-200 dark:border-slate-700">
      <div className="flex items-center gap-1.5">
        {isOnline ? (
          <Cloud className="w-3.5 h-3.5 text-emerald-500" />
        ) : (
          <CloudOff className="w-3.5 h-3.5 text-amber-500" />
        )}
        <span className={cn(isOnline ? "text-emerald-600" : "text-amber-600")}>
          {isOnline ? "Online" : "Offline Mode"}
        </span>
      </div>

      <div className="w-px h-3 bg-slate-300 dark:bg-slate-600" />

      <button
        onClick={() => sync()}
        disabled={isSyncing || !isOnline}
        className="flex items-center gap-1.5 hover:text-blue-600 disabled:opacity-50 transition-colors"
      >
        <RefreshCw className={cn("w-3.5 h-3.5", isSyncing && "animate-spin text-blue-500")} />
        <span>
          {isSyncing ? "Syncing..." : hasPending ? `${pendingCount} Pending` : "Synced"}
        </span>
      </button>

      {hasConflicts && (
        <>
          <div className="w-px h-3 bg-slate-300 dark:bg-slate-600" />
          <div className="flex items-center gap-1.5 text-rose-500">
            <AlertCircle className="w-3.5 h-3.5" />
            <span>{conflictCount} Conflicts</span>
          </div>
        </>
      )}
    </div>
  );
}
