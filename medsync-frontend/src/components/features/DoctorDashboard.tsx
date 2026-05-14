"use client";

import React from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorBanner } from "@/components/ui/error-banner";
import { CardSkeleton } from "@/components/ui/skeleton";
import { triageSortRank, TriageBadge } from "@/components/ui/badge";
import { useWorklistEncounters, type WorklistEncounter } from "@/hooks/use-encounters";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { useAlerts, useResolveAlert } from "@/hooks/use-alerts";
import { useDashboardStats } from "@/hooks/use-dashboard-stats";
import { useAuth } from "@/lib/auth-context";

const REFRESH_INTERVAL_MS = 60_000;

function AllergyIndicator({ hasAllergy }: { hasAllergy?: boolean }) {
  if (!hasAllergy) return <span className="text-xs text-[var(--gray-500)]">No known active allergy</span>;
  return (
    <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800 dark:bg-rose-900/30 dark:border-rose-800 dark:text-rose-300">
      Allergy risk
    </span>
  );
}

export function DoctorDashboard() {
  const { user } = useAuth();
  const { encounters, summary, fetch: fetchWorklist } = useWorklistEncounters();
  const { alerts, fetch: fetchAlerts } = useAlerts("active", undefined, user?.hospital_id || null);
  const { resolve: resolveAlert, loading: resolvingAlert } = useResolveAlert();
  const { stats: metrics, loading: dashboardLoading, error: dashboardError, refresh: fetchDashboard } = useDashboardStats();

  const [dismissedAlertIds, setDismissedAlertIds] = React.useState<Set<string>>(new Set());
  const [lastRefreshedAt, setLastRefreshedAt] = React.useState<Date | null>(null);
  const [referenceNowMs, setReferenceNowMs] = React.useState<number>(0);

  const refreshAll = React.useCallback(async () => {
    const refreshedAt = new Date();
    await Promise.all([fetchDashboard(), fetchWorklist(true), fetchAlerts()]);
    setLastRefreshedAt(refreshedAt);
    setReferenceNowMs(refreshedAt.getTime());
  }, [fetchAlerts, fetchDashboard, fetchWorklist]);

  const loading = dashboardLoading && encounters.length === 0;
  const error = dashboardError;

  React.useEffect(() => {
    void refreshAll();
  }, [refreshAll]);

  usePollWhenVisible(() => {
    void refreshAll();
  }, REFRESH_INTERVAL_MS, true);

  const queueRows = React.useMemo(() => {
    return [...encounters]
      .sort((a, b) => {
        const triage = triageSortRank(a.triage_badge) - triageSortRank(b.triage_badge);
        if (triage !== 0) return triage;
        return new Date(a.encounter_date).getTime() - new Date(b.encounter_date).getTime();
      })
      .slice(0, 8);
  }, [encounters]);

  const labRows = React.useMemo(() => {
    return [...encounters]
      .filter((row) => Number(row.pending_labs ?? 0) > 0)
      .sort((a, b) => Number(b.pending_labs ?? 0) - Number(a.pending_labs ?? 0))
      .slice(0, 6);
  }, [encounters]);

  const pendingDispenseRows = React.useMemo(() => {
    return [...encounters]
      .filter((row) => Number(row.pending_prescriptions ?? 0) > 0)
      .sort((a, b) => Number(b.pending_prescriptions ?? 0) - Number(a.pending_prescriptions ?? 0))
      .slice(0, 6);
  }, [encounters]);

  const visibleAlerts = React.useMemo(
    () => alerts.filter((a) => !dismissedAlertIds.has(a.id)).slice(0, 6),
    [alerts, dismissedAlertIds]
  );

  const dismissAlert = (alertId: string) => {
    setDismissedAlertIds((prev) => new Set([...prev, alertId]));
  };

  const resolveAndDismiss = async (alertId: string) => {
    const ok = await resolveAlert(alertId);
    if (ok) dismissAlert(alertId);
  };

  // Skeleton loading state
  if (loading && encounters.length === 0) {
    return (
      <div className="space-y-6">
        <div className="h-8 w-48 animate-pulse rounded bg-slate-200 dark:bg-slate-800 dark:bg-[#334155]" />
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
          {Array.from({ length: 5 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <CardSkeleton lines={6} />
          <CardSkeleton lines={6} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-end">
        <p className="text-xs text-[var(--gray-500)]">
          Last refreshed {lastRefreshedAt ? lastRefreshedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "—"}
        </p>
      </div>

      {error && (
        <ErrorBanner message={error} onRetry={() => { void refreshAll(); }} />
      )}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <StatCard label="Patients in queue" value={metrics.queue_count} accent="teal" />
        <StatCard label="Critical alerts" value={metrics.critical_alerts} accent="navy" />
        <StatCard label="New lab results" value={metrics.new_lab_results} accent="green" />
        <StatCard label="Pending dispense" value={metrics.pending_prescriptions} accent="amber" />
        <StatCard label="Referrals awaiting" value={metrics.referrals_awaiting} accent="teal" />
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle className="text-lg">Today&apos;s queue</CardTitle>
            <Link href="/worklist">
              <Button size="sm" variant="secondary">Open worklist</Button>
            </Link>
          </CardHeader>
          <CardContent className="space-y-3">
            {queueRows.length === 0 ? (
              <EmptyState title="No patients in your worklist" description="Your queue is clear." />
            ) : (
              queueRows.map((row) => {
                const waitMinutes = Math.max(
                  0,
                  Math.floor(((referenceNowMs || new Date(row.encounter_date).getTime()) - new Date(row.encounter_date).getTime()) / 60_000)
                );
                return (
                  <div key={row.id} className="rounded-lg border border-[var(--gray-300)] dark:border-[#334155] p-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold text-[var(--gray-900)]">{row.patient_name}</p>
                      <TriageBadge triage={row.triage_badge} />
                    </div>
                    <p className="mt-1 text-xs text-[var(--gray-500)]">
                      Wait time: {waitMinutes} min · {row.assigned_department_name || "Unassigned"}
                    </p>
                    <div className="mt-2">
                      <AllergyIndicator hasAllergy={row.has_active_allergy} />
                    </div>
                  </div>
                );
              })
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">New lab results (unreviewed)</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {labRows.length === 0 ? (
              <EmptyState title="No unreviewed lab results" />
            ) : (
              labRows.map((row: WorklistEncounter) => (
                <div key={`lab-${row.id}`} className="rounded-lg border border-[var(--gray-300)] dark:border-[#334155] p-3">
                  <div className="flex items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-[var(--gray-900)]">{row.patient_name}</p>
                    {(row.active_alerts ?? 0) > 0 ? (
                      <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-semibold text-red-800 dark:bg-red-900/30 dark:text-red-300">Critical value</span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-[var(--gray-500)]">
                    Unreviewed results: {row.pending_labs ?? 0}
                  </p>
                </div>
              ))
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Active alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {visibleAlerts.length === 0 ? (
            <EmptyState title="No active alerts" description="All clear." />
          ) : (
            <div className="flex flex-wrap gap-3">
              {visibleAlerts.map((alert) => (
                <div
                  key={alert.id}
                  className="min-w-[260px] flex-1 rounded-lg border border-[var(--gray-300)] dark:border-[#334155] bg-slate-50 dark:bg-slate-900 dark:bg-slate-900 dark:bg-slate-100 p-3"
                >
                  <p className="text-sm font-semibold text-[var(--gray-900)]">{alert.patient_name}</p>
                  <p className="mt-1 text-xs text-[var(--gray-500)]">{alert.message}</p>
                  <div className="mt-3 flex gap-2">
                    <Button size="sm" variant="secondary" onClick={() => dismissAlert(alert.id)}>
                      Dismiss
                    </Button>
                    <Button size="sm" onClick={() => void resolveAndDismiss(alert.id)} disabled={resolvingAlert}>
                      Resolve
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Pending dispense</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {pendingDispenseRows.length === 0 ? (
            <EmptyState title="No pending dispense items" />
          ) : (
            pendingDispenseRows.map((row) => (
              <div key={`rx-${row.id}`} className="rounded-lg border border-[var(--gray-300)] dark:border-[#334155] p-3">
                <p className="text-sm font-semibold text-[var(--gray-900)]">{row.patient_name}</p>
                <p className="mt-1 text-xs text-[var(--gray-500)]">
                  Pending prescriptions: {row.pending_prescriptions ?? 0}
                </p>
              </div>
            ))
          )}
          <p className="text-xs text-[var(--gray-500)]">Current queue summary pending dispense count: {summary.pending_prescriptions}</p>
        </CardContent>
      </Card>
    </div>
  );
}
