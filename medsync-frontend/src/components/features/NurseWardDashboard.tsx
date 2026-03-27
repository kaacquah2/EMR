"use client";

import React from "react";
import Link from "next/link";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useApi } from "@/hooks/use-api";
import { useNurseDashboard } from "@/hooks/use-nurse";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";

export function NurseWardDashboard() {
  const api = useApi();
  const { data, loading, fetch } = useNurseDashboard();
  usePollWhenVisible(fetch, 60_000, true);
  if (loading || !data) {
    return <div className="text-center py-8">Loading ward dashboard...</div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">{data.ward_name}</h2>
          <p className="text-sm text-slate-500">Current shift: {data.current_shift}</p>
        </div>
        <Button onClick={fetch} variant="outline">Refresh</Button>
      </div>

      <div className="grid gap-4 md:grid-cols-3 lg:grid-cols-4">
        <Card accent="teal">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Admitted patients</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">{data.admitted_count}</p>
          </CardContent>
        </Card>
        <Card accent="red">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Vitals overdue</p>
            <p className="mt-2 text-3xl font-bold text-red-600">{data.vitals_overdue_count}</p>
          </CardContent>
        </Card>
        <Card accent="amber">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Meds pending dispense</p>
            <p className="mt-2 text-3xl font-bold text-amber-600">{data.pending_dispense_count}</p>
          </CardContent>
        </Card>
        <Card accent="blue">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Current shift</p>
            <p className="mt-2 text-xl font-bold text-slate-900">{data.current_shift}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Priority worklist</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {data.priority_worklist.length === 0 ? (
              <p className="text-sm text-slate-500">No urgent tasks.</p>
            ) : data.priority_worklist.map((row, idx) => (
              <div key={`${row.patient_id}-${idx}`} className="flex items-center justify-between rounded border border-slate-200 p-3 text-sm">
                <div>
                  <p className="font-medium text-slate-900">
                    [{row.type === "VITALS_DUE" ? "VITALS DUE" : "DISPENSE"}] {row.bed_code ?? "Bed —"} · {row.patient_name}
                  </p>
                  {row.type === "DISPENSE" ? (
                    <p className="text-slate-500">{row.drug_name}</p>
                  ) : (
                    <p className="text-slate-500">Last recorded: {row.last_recorded ? new Date(row.last_recorded).toLocaleString() : "Never"}</p>
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
              <p className="text-sm font-semibold">Shift tracking</p>
              <p className="text-xs text-slate-500">Status: {data.shift.status}</p>
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
