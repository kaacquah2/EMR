"use client";

import React, { useCallback, useEffect, useState } from "react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { isBenignApiNetworkFailure } from "@/lib/api-client";

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
  const [metrics, setMetrics] = useState<LabMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLabMetrics = useCallback(async () => {
    try {
      setLoading(true);
      const response = await api.get<LabMetrics>("/lab/analytics/trends");
      setMetrics(response);
      setError(null);
    } catch (err) {
      setError(
        isBenignApiNetworkFailure(err)
          ? "Could not reach the API. Check that the backend is running."
          : "Failed to load lab dashboard. Please try again."
      );
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchLabMetrics();
  }, [fetchLabMetrics]);
  usePollWhenVisible(fetchLabMetrics, 60_000, true);

  if (loading && !metrics) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-56 animate-pulse rounded bg-[#E2E8F0] dark:bg-[#334155]" />
        <div className="grid gap-4 md:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
        <CardSkeleton lines={5} />
        <CardSkeleton lines={6} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold text-[var(--gray-900)]">Laboratory Dashboard</h2>
        <p className="text-sm text-[var(--gray-500)] mt-1">Turnaround performance and breach monitoring</p>
      </div>

      {error && (
        <ErrorBanner message={error} onRetry={() => { setError(null); void fetchLabMetrics(); }} />
      )}

      {metrics && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <StatCard label="STAT TAT (today)" value={metrics.avg_tat_by_urgency.stat_min != null ? `${metrics.avg_tat_by_urgency.stat_min} min` : "—"} accent="amber" valueClassName="text-[var(--red-600)]" />
            <StatCard label="Urgent TAT (today)" value={metrics.avg_tat_by_urgency.urgent_min != null ? `${metrics.avg_tat_by_urgency.urgent_min} min` : "—"} accent="amber" valueClassName="text-[var(--amber-600)]" />
            <StatCard label="Routine TAT (today)" value={metrics.avg_tat_by_urgency.routine_min != null ? `${metrics.avg_tat_by_urgency.routine_min} min` : "—"} accent="navy" />
          </div>

          <Card>
            <CardHeader>
              <CardTitle>TAT Breaches Today</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="mb-3 text-xl font-bold text-[var(--red-600)]">{metrics.breach_count}</div>
              <div className="space-y-2">
                {metrics.breached_orders.length === 0 ? (
                  <EmptyState title="No breaches recorded today" />
                ) : (
                  metrics.breached_orders.map((b, idx) => (
                    <div key={`${b.test_name}-${idx}`} className="rounded border border-[#FECACA] dark:border-[#B91C1C]/40 bg-[#FEF2F2] dark:bg-[#450A0A] p-2 text-sm text-[var(--red-600)]">
                      {b.test_name} - {b.overdue_minutes} min over
                    </div>
                  ))
                )}
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <p className="text-sm font-semibold text-[var(--gray-700)] mb-3">Pending by Age</p>
              <div className="grid gap-2 text-sm">
                <div className="text-[var(--gray-900)]">0-1h: <strong>{metrics.pending_by_age["0-1h"]}</strong></div>
                <div className="text-[var(--gray-900)]">1-4h: <strong>{metrics.pending_by_age["1-4h"]}</strong></div>
                <div className="text-[var(--gray-900)]">4-24h: <strong>{metrics.pending_by_age["4-24h"]}</strong></div>
                <div className="text-[var(--red-600)]">24h+: <strong>{metrics.pending_by_age["24h+"]}</strong></div>
              </div>
              <p className="mt-4 text-sm font-semibold text-[var(--gray-700)]">Throughput</p>
              <div className="grid gap-2 text-sm text-[var(--gray-900)]">
                <div>Today: <strong>{metrics.throughput.today}</strong></div>
                <div>Yesterday: <strong>{metrics.throughput.yesterday}</strong></div>
                <div>7-day avg: <strong>{metrics.throughput.seven_day_avg}</strong></div>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
