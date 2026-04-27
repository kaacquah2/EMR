"use client";

import { useConnectionStatus, ConnectionStatus } from "@/hooks/use-connection-status";
import { Wifi, WifiOff, CloudOff, RefreshCw } from "lucide-react";

interface ConnectionStatusIndicatorProps {
  showSyncButton?: boolean;
  onSyncNow?: () => void;
  syncing?: boolean;
}

export function ConnectionStatusIndicator({
  showSyncButton = true,
  onSyncNow,
  syncing = false,
}: ConnectionStatusIndicatorProps) {
  const { status, lastOnline, pendingSyncCount } = useConnectionStatus();

  const statusConfig: Record<ConnectionStatus, { color: string; icon: React.ReactNode; label: string }> = {
    online: {
      color: "bg-green-500",
      icon: <Wifi className="h-3 w-3" />,
      label: "Online",
    },
    degraded: {
      color: "bg-amber-500",
      icon: <CloudOff className="h-3 w-3" />,
      label: "Slow connection",
    },
    offline: {
      color: "bg-red-500",
      icon: <WifiOff className="h-3 w-3" />,
      label: "Offline",
    },
  };

  const config = statusConfig[status];

  const formatLastOnline = () => {
    if (!lastOnline) return "";
    const now = new Date();
    const diff = Math.floor((now.getTime() - lastOnline.getTime()) / 1000);
    
    if (diff < 60) return "just now";
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return lastOnline.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  return (
    <div className="flex items-center gap-2 text-xs">
      {/* Status dot and label */}
      <div className="flex items-center gap-1.5">
        <div className={`h-2 w-2 rounded-full ${config.color}`} />
        <span className="text-muted-foreground">{config.label}</span>
      </div>

      {/* Pending sync count */}
      {pendingSyncCount > 0 && (
        <div className="flex items-center gap-1 text-amber-600">
          <span className="font-medium">{pendingSyncCount} pending</span>
        </div>
      )}

      {/* Sync button */}
      {showSyncButton && status === "online" && pendingSyncCount > 0 && (
        <button
          onClick={onSyncNow}
          disabled={syncing}
          className="flex items-center gap-1 px-2 py-0.5 text-xs bg-primary/10 hover:bg-primary/20 text-primary rounded transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`h-3 w-3 ${syncing ? "animate-spin" : ""}`} />
          {syncing ? "Syncing..." : "Sync now"}
        </button>
      )}

      {/* Last synced time */}
      {status !== "online" && lastOnline && (
        <span className="text-muted-foreground">
          Last online: {formatLastOnline()}
        </span>
      )}
    </div>
  );
}
