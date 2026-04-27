"use client";

import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useToast } from "@/lib/toast-context";
import { useApi } from "@/hooks/use-api";
import { ActiveAlert } from "@/hooks/use-nurse-dashboard-enhanced";

interface ActiveAlertsPanelProps {
  alerts: ActiveAlert[];
  onRefresh: () => void;
}

/**
 * Active Clinical Alerts Panel - inline Resolve action with severity dots
 */
export function ActiveAlertsPanel({
  alerts,
  onRefresh,
}: ActiveAlertsPanelProps) {
  const api = useApi();
  const toast = useToast();
  const [resolving, setResolving] = useState<Set<string>>(new Set());

  const handleResolve = async (alertId: string) => {
    setResolving((prev) => new Set([...prev, alertId]));
    try {
      await api.patch(`/alerts/${alertId}`, { status: "resolved" });
      toast.success("Alert resolved");
      onRefresh();
    } catch {
      toast.error("Failed to resolve alert");
    } finally {
      setResolving((prev) => {
        const next = new Set(prev);
        next.delete(alertId);
        return next;
      });
    }
  };

  // Get severity dot
  const getDot = (severity: string) => {
    const filled = severity === "critical" || severity === "high";
    return filled ? "●" : "○";
  };

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case "critical":
        return "text-red-600";
      case "high":
        return "text-amber-600";
      case "medium":
        return "text-amber-500";
      case "low":
        return "text-slate-400";
      default:
        return "text-slate-400";
    }
  };

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Active clinical alerts</CardTitle>
        <Button
          size="sm"
          variant="ghost"
          className="text-xs text-blue-600 hover:text-blue-700"
          onClick={() => window.location.href = "/alerts"}
        >
          View all →
        </Button>
      </CardHeader>
      <CardContent>
        {alerts.length === 0 ? (
          <p className="text-sm text-slate-500">No active alerts</p>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => (
              <div
                key={alert.alert_id}
                className="flex items-start justify-between gap-3 border-b border-slate-100 pb-3 last:border-b-0 last:pb-0"
              >
                <div className="flex gap-2">
                  <span className={`text-lg ${getSeverityColor(alert.severity)}`}>
                    {getDot(alert.severity)}
                  </span>
                  <div>
                    <p className="text-sm font-medium text-slate-900">
                      {alert.message}
                    </p>
                    <p className="mt-1 text-xs text-slate-600">
                      {alert.patient_name}
                      {alert.bed_code && ` · ${alert.bed_code}`}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatTimeAgo(new Date(alert.created_at))}
                    </p>
                  </div>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="text-xs"
                  onClick={() => handleResolve(alert.alert_id)}
                  disabled={resolving.has(alert.alert_id)}
                >
                  {resolving.has(alert.alert_id) ? "…" : "Resolve"}
                </Button>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function formatTimeAgo(date: Date): string {
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMins / 60);

  if (diffMins < 1) return "just now";
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${Math.floor(diffHours / 24)}d ago`;
}
