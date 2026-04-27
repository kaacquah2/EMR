"use client";

import { useMemo } from "react";
import { useAuth } from "@/lib/auth-context";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { useNurseDashboardEnhanced } from "@/hooks/use-nurse-dashboard-enhanced";
import { StatCard } from "@/components/ui/stat-card";
import { CardSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useRouter } from "next/navigation";

import { BedGrid } from "./BedGrid";
import { PriorityTasksPanel } from "./PriorityTasksPanel";
import { PendingDispensePanel } from "./PendingDispensePanel";
import { ActiveAlertsPanel } from "./ActiveAlertsPanel";
import { ShiftBreakTracker } from "./ShiftBreakTracker";

/**
 * Enhanced Nurse Ward Dashboard with bed grid, priority tasks, dispense, and alerts panels
 */
export function NurseWardDashboardEnhanced() {
  const { user } = useAuth();
  const router = useRouter();
  const wardId = user?.ward_id ?? undefined;

  // Fetch all dashboard data
  const { data, loading, fetch } = useNurseDashboardEnhanced(wardId);

  // Auto-refresh every 60 seconds
  usePollWhenVisible(fetch, 60_000, true);

  // Compute last refresh time - use data.last_refreshed directly to match React Compiler inference
  const lastRefreshed = useMemo(() => {
    const timestamp = data?.last_refreshed;
    if (!timestamp) return "";
    return new Date(timestamp).toLocaleTimeString("en-GB", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }, [data?.last_refreshed]);

  // Page heading with greeting
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";

  if (loading && !data) {
    return (
      <div className="space-y-8">
        <div className="h-8 w-64 animate-pulse rounded bg-[#E2E8F0] dark:bg-[#334155]" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
        <CardSkeleton lines={8} />
      </div>
    );
  }

  if (!data) {
    return (
      <div className="flex h-64 items-center justify-center">
        <EmptyState title="Unable to load dashboard" description="Please refresh the page or contact support." />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Page Heading */}
      <div className="space-y-2">
        <h1 className="text-3xl font-bold text-[var(--gray-900)]">
          {greeting}, {user?.full_name}
        </h1>
        <p className="text-sm text-[var(--gray-500)]">
          Ward {user?.ward_name} · Nurse shift · Last refreshed {lastRefreshed}
        </p>
      </div>

      {/* Shift Break Tracker */}
      <ShiftBreakTracker
        onEndShift={() => {
          router.push('/worklist/handover');
        }}
      />

      {/* Stat Cards (4-column grid) */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Admitted patients"
          value={data.stats.admitted_count}
          subtitle={`Ward ${user?.ward_name}`}
          accent="teal"
        />
        <StatCard
          label="Vitals overdue"
          value={data.stats.vitals_overdue_count}
          subtitle=">4h since last reading"
          accent="amber"
          valueClassName="text-[var(--red-600)]"
        />
        <StatCard
          label="Meds pending dispense"
          value={data.stats.pending_dispense_count}
          subtitle="Across ward patients"
          accent="amber"
        />
        <StatCard
          label="Active clinical alerts"
          value={data.stats.active_alerts_count}
          subtitle="Needs attention"
          accent="navy"
        />
      </div>

      {/* Row 1: Bed Grid + Priority Tasks */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Bed Grid - 2/3 width */}
        <div className="lg:col-span-2">
          <BedGrid beds={data.beds} />
        </div>

        {/* Priority Tasks - 1/3 width */}
        <div>
          <PriorityTasksPanel
            beds={data.beds}
            prescriptions={data.pending_prescriptions}
          />
        </div>
      </div>

      {/* Row 2: Pending Dispense + Active Alerts */}
      <div className="grid gap-6 lg:grid-cols-2">
        <PendingDispensePanel
          prescriptions={data.pending_prescriptions}
          onRefresh={fetch}
        />
        <ActiveAlertsPanel
          alerts={data.active_alerts}
          onRefresh={fetch}
        />
      </div>
    </div>
  );
}
