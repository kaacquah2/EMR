"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useWorklistEncounters } from "@/hooks/use-encounters";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { useApi } from "@/hooks/use-api";

export function DoctorWorklist() {
  const router = useRouter();
  const api = useApi();
  const [departmentFilter, setDepartmentFilter] = useState("");
  const [encounterTypeFilter, setEncounterTypeFilter] = useState("");
  const { encounters, summary, loading, fetch } = useWorklistEncounters();
  const [dashboardStats, setDashboardStats] = useState<{ new_lab_results: number; critical_alerts: number; pending_prescriptions: number; referrals_awaiting: number }>({
    new_lab_results: 0,
    critical_alerts: 0,
    pending_prescriptions: 0,
    referrals_awaiting: 0,
  });
  useEffect(() => {
    (async () => {
      try {
        const stats = await api.get<{
          new_lab_results?: number;
          critical_alerts?: number;
          pending_prescriptions?: number;
          referrals_awaiting?: number;
        }>("/dashboard");
        setDashboardStats({
          new_lab_results: Number(stats.new_lab_results || 0),
          critical_alerts: Number(stats.critical_alerts || 0),
          pending_prescriptions: Number(stats.pending_prescriptions || 0),
          referrals_awaiting: Number(stats.referrals_awaiting || 0),
        });
      } catch {
        setDashboardStats({ new_lab_results: 0, critical_alerts: 0, pending_prescriptions: 0, referrals_awaiting: 0 });
      }
    })();
  }, [api]);
  usePollWhenVisible(() => fetch(true, { department_id: departmentFilter || undefined, encounter_type: encounterTypeFilter || undefined }), 60_000, true);

  const departments = useMemo(() => {
    const uniq = new Map<string, string>();
    for (const e of encounters) {
      if (e.assigned_department_id && e.assigned_department_name) uniq.set(e.assigned_department_id, e.assigned_department_name);
    }
    return [...uniq.entries()].map(([id, name]) => ({ id, name }));
  }, [encounters]);
  const encounterTypes = useMemo(() => [...new Set(encounters.map((e) => e.encounter_type))], [encounters]);

  if (loading) {
    return <div className="text-center py-8">Loading worklist...</div>;
  }

  const handleViewPatient = (patientId: string) => {
    router.push(`/patients/${patientId}`);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-slate-900">Patient Worklist</h2>
        <p className="text-sm text-slate-500 mt-1">
          Active encounters sorted by priority
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-5">
        <Card accent="blue">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Total Patients</p>
            <p className="mt-2 text-3xl font-bold text-slate-900">
              {summary.queue_count}
            </p>
            <p className="mt-1 text-xs text-slate-500">in your care</p>
          </CardContent>
        </Card>

        <Card accent="red">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Critical</p>
            <p className="mt-2 text-3xl font-bold text-red-600">
              {dashboardStats.critical_alerts}
            </p>
            <p className="mt-1 text-xs text-slate-500">active alerts</p>
          </CardContent>
        </Card>

        <Card accent="orange">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Pending Labs</p>
            <p className="mt-2 text-3xl font-bold text-orange-600">
              {dashboardStats.new_lab_results}
            </p>
            <p className="mt-1 text-xs text-slate-500">new lab results</p>
          </CardContent>
        </Card>

        <Card accent="amber">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Pending Rx</p>
            <p className="mt-2 text-3xl font-bold text-amber-600">
              {dashboardStats.pending_prescriptions}
            </p>
            <p className="mt-1 text-xs text-slate-500">not dispensed</p>
          </CardContent>
        </Card>
        <Card accent="purple">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-600">Referrals</p>
            <p className="mt-2 text-3xl font-bold text-violet-600">
              {dashboardStats.referrals_awaiting}
            </p>
            <p className="mt-1 text-xs text-slate-500">awaiting action</p>
          </CardContent>
        </Card>
      </div>

      {/* Sorting and Filtering */}
      <Card>
        <CardContent className="pt-6">
          <div className="grid gap-4 md:grid-cols-3">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Department
              </label>
              <select
                value={departmentFilter}
                onChange={(e) => setDepartmentFilter(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All departments</option>
                {departments.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">
                Encounter type
              </label>
              <select
                value={encounterTypeFilter}
                onChange={(e) => setEncounterTypeFilter(e.target.value)}
                className="w-full px-3 py-2 border border-slate-300 rounded-md text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">All encounter types</option>
                {encounterTypes.map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
              </select>
            </div>

            <div className="flex items-end">
              <Button
                onClick={() => fetch(false, { department_id: departmentFilter || undefined, encounter_type: encounterTypeFilter || undefined })}
                variant="outline"
                className="w-full"
              >
                Refresh
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Worklist */}
      <div className="space-y-3">
        {encounters.map((encounter) => (
          <Card
            key={encounter.id}
            className={`${encounter.active_alerts ? "border-red-300" : ""}`}
          >
            <CardContent className="pt-6">
              <div className="flex items-start justify-between gap-4">
                {/* Patient Info */}
                <div
                  className="flex-1 cursor-pointer"
                  onClick={() => handleViewPatient(encounter.patient_id)}
                >
                  <div className="flex items-center gap-3">
                    <div className={`w-3 h-3 rounded-full flex-shrink-0 ${encounter.status === "in_consultation" ? "bg-amber-600" : "bg-blue-600"}`} />
                    <div>
                      <h3 className="font-semibold text-slate-900 hover:text-blue-600">
                        {encounter.patient_name}
                      </h3>
                      <p className="text-xs text-slate-500">
                        {encounter.ghana_health_id} · {new Date(encounter.encounter_date).toLocaleDateString()}
                      </p>
                    </div>
                  </div>

                  {/* Diagnosis and Status */}
                  <div className="mt-3 space-y-2">
                    {/* Alerts and Pending */}
                    <div className="flex flex-wrap gap-2 pt-1">
                      {(encounter.active_alerts ?? 0) > 0 && (
                        <span className="inline-block px-2 py-1 bg-red-100 text-red-800 border border-red-300 rounded text-xs font-semibold">
                          ⚠️ {encounter.active_alerts ?? 0} Alert
                          {(encounter.active_alerts ?? 0) !== 1 ? "s" : ""}
                        </span>
                      )}

                      {(encounter.pending_labs ?? 0) > 0 && (
                        <span className="inline-block px-2 py-1 bg-blue-100 text-blue-800 border border-blue-300 rounded text-xs font-semibold">
                          🧪 {encounter.pending_labs ?? 0} Pending Lab
                          {(encounter.pending_labs ?? 0) !== 1 ? "s" : ""}
                        </span>
                      )}

                      {(encounter.pending_prescriptions ?? 0) > 0 && (
                        <span className="inline-block px-2 py-1 bg-amber-100 text-amber-800 border border-amber-300 rounded text-xs font-semibold">
                          💊 {encounter.pending_prescriptions ?? 0} Pending Rx
                        </span>
                      )}

                      <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-300">
                        {encounter.triage_badge === "consulting" ? "In consultation" : "Waiting"}
                      </span>
                      {encounter.has_active_allergy && (
                        <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-rose-100 text-rose-800 border border-rose-300">
                          Allergy
                        </span>
                      )}
                      <span className="inline-block px-2 py-1 rounded text-xs font-semibold bg-slate-100 text-slate-800 border border-slate-300">
                        {encounter.assigned_department_name || "Unassigned"}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="flex flex-col gap-2">
                  <Button
                    size="sm"
                    onClick={() =>
                      handleViewPatient(encounter.patient_id)
                    }
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    View Patient
                  </Button>

                  <Button size="sm" variant="outline" onClick={() => router.push(`/patients/${encounter.patient_id}?tab=encounters`)}>
                    Open Encounter
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {encounters.length === 0 && (
          <div className="text-center py-12 text-slate-500">
            No patients in your worklist
          </div>
        )}
      </div>
    </div>
  );
}
