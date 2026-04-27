"use client";

import React from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/ui/stat-card";
import { EmptyState } from "@/components/ui/empty-state";
import { CardSkeleton } from "@/components/ui/skeleton";
import { useApi } from "@/hooks/use-api";
import { useNurseDashboard } from "@/hooks/use-nurse";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";

export function NurseWardDashboard() {
  const api = useApi();
  const { data, loading, fetch } = useNurseDashboard();
  usePollWhenVisible(fetch, 60_000, true);

  if (loading || !data) {
    return (
      <div className="space-y-6">
        <CardSkeleton lines={2} />
        <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => <CardSkeleton key={i} lines={2} />)}
        </div>
        <CardSkeleton lines={5} />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-[var(--gray-900)]">{data.ward_name}</h2>
          <p className="text-sm text-[var(--gray-500)]">Current shift: {data.current_shift}</p>
        </div>
        <Button onClick={fetch} variant="outline">Refresh</Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-4">
        <StatCard label="Admitted patients" value={data.admitted_count} accent="teal" />
        <StatCard label="Vitals overdue" value={data.vitals_overdue_count} accent="amber" valueClassName="text-[var(--red-600)]" />
        <StatCard label="Meds pending dispense" value={data.pending_dispense_count} accent="amber" valueClassName="text-[var(--amber-600)]" />
        <StatCard label="Current shift" value={data.current_shift} accent="navy" />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Priority worklist</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.priority_worklist.length === 0 ? (
              <EmptyState title="No urgent tasks" description="All tasks are up to date." />
            ) : data.priority_worklist.map((row, idx) => (
              <div key={`${row.patient_id}-${idx}`} className="flex items-center justify-between rounded border border-[var(--gray-300)] dark:border-[#334155] p-3 text-sm">
                <div>
                  <p className="font-medium text-[var(--gray-900)]">
                    [{row.type === "VITALS_DUE" ? "VITALS DUE" : "DISPENSE"}] {row.bed_code ?? "Bed —"} · {row.patient_name}
                  </p>
                  {row.type === "DISPENSE" ? (
                    <p className="text-[var(--gray-500)]">{row.drug_name}</p>
                  ) : (
                    <p className="text-[var(--gray-500)]">Last recorded: {row.last_recorded ? new Date(row.last_recorded).toLocaleString() : "Never"}</p>
                  )}
                </div>
                <div>
                  {row.type === "VITALS_DUE" ? (
                    <Link href={`/patients/${row.patient_id}/vitals/new`}>
                      <Button size="sm">Record</Button>
                    </Link>
                  ) : (
                    <Link href="/worklist"><Button size="sm" variant="secondary">Dispense</Button></Link>
                  )}
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-sm font-semibold text-[var(--gray-900)]">Shift tracking</p>
              <p className="text-xs text-[var(--gray-500)]">Status: {data.shift.status}</p>
            </div>
            <div className="flex gap-2">
              {data.shift.status === "not_started" ? (
                <Button size="sm" onClick={() => void api.post("/nurse/shift/start", {}).then(() => fetch())}>
                  Start shift
                </Button>
              ) : null}
              <Button size="sm" variant="secondary" onClick={() => void api.post("/nurse/shift/break-toggle", {}).then(() => fetch())}>
                {data.shift.status === "on_break" ? "Resume" : "Log break"}
              </Button>
              <Button size="sm" variant="secondary" onClick={() => void api.post("/nurse/shift/end", {}).then(() => fetch())}>End shift</Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
