"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { isBenignApiNetworkFailure } from "@/lib/api-client";
import { useToast } from "@/lib/toast-context";

interface LabMetrics {
  avg_tat_by_urgency: {
    stat_min: number | null;
    urgent_min: number | null;
    routine_min: number | null;
  };
  breach_count: number;
  breached_orders: Array<{ test_name: string; overdue_minutes: number }>;
  pending_by_age: Record<"0-1h" | "1-4h" | "4-24h" | "24h+", number>;
  throughput: { today: number; yesterday: number; seven_day_avg: number };
}

export function LabDashboard() {
  const api = useApi();
  const toast = useToast();
  const [metrics, setMetrics] = useState<LabMetrics | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchLabMetrics = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get<LabMetrics>("/lab/analytics/trends");
      setMetrics(response);
    } catch (error) {
      if (!isBenignApiNetworkFailure(error)) console.error("Failed to fetch lab metrics:", error);
      toast.error(
        isBenignApiNetworkFailure(error)
          ? "Could not reach the API. Check that the backend is running."
          : "Failed to load lab dashboard. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }, [api, toast]);

  useEffect(() => {
    fetchLabMetrics();
  }, [fetchLabMetrics]);
  usePollWhenVisible(fetchLabMetrics, 60_000, true);

  if (loading || !metrics) {
    return <div className="text-center py-8">Loading lab dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Laboratory Dashboard</h2>
        <p className="text-sm text-slate-500 mt-1">Turnaround performance and breach monitoring</p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card accent="red">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">STAT TAT (today)</p>
            <p className="mt-2 text-3xl font-bold text-red-700">{metrics.avg_tat_by_urgency.stat_min ?? "—"} min</p>
          </CardContent>
        </Card>
        <Card accent="amber">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Urgent TAT (today)</p>
            <p className="mt-2 text-3xl font-bold text-amber-700">{metrics.avg_tat_by_urgency.urgent_min ?? "—"} min</p>
          </CardContent>
        </Card>
        <Card accent="blue">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Routine TAT (today)</p>
            <p className="mt-2 text-3xl font-bold text-blue-700">{metrics.avg_tat_by_urgency.routine_min ?? "—"} min</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>TAT Breaches Today</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-3 text-xl font-bold text-[#DC2626]">{metrics.breach_count}</div>
          <div className="space-y-2">
            {metrics.breached_orders.length === 0 ? (
              <p className="text-sm text-[#64748B]">No breaches recorded today.</p>
            ) : (
              metrics.breached_orders.map((b, idx) => (
                <div key={`${b.test_name}-${idx}`} className="rounded border border-[#FECACA] bg-[#FEF2F2] p-2 text-sm">
                  {b.test_name} - {b.overdue_minutes} min over
                </div>
              ))
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="bg-slate-50">
        <CardContent className="pt-6">
          <p className="text-sm font-semibold text-slate-700 mb-3">Pending by Age</p>
          <div className="grid gap-2 text-sm">
            <div>0-1h: <strong>{metrics.pending_by_age["0-1h"]}</strong></div>
            <div>1-4h: <strong>{metrics.pending_by_age["1-4h"]}</strong></div>
            <div>4-24h: <strong>{metrics.pending_by_age["4-24h"]}</strong></div>
            <div className="text-red-700">24h+: <strong>{metrics.pending_by_age["24h+"]}</strong></div>
          </div>
          <p className="mt-4 text-sm font-semibold text-slate-700">Throughput</p>
          <div className="grid gap-2 text-sm">
            <div>Today: <strong>{metrics.throughput.today}</strong></div>
            <div>Yesterday: <strong>{metrics.throughput.yesterday}</strong></div>
            <div>7-day avg: <strong>{metrics.throughput.seven_day_avg}</strong></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
