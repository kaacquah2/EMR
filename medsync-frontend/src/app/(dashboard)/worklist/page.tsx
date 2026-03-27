"use client";

import React, { useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useWorklistEncounters } from "@/hooks/use-encounters";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useNurseWorklist } from "@/hooks/use-nurse";

const WORKLIST_ROLES = ["doctor", "nurse", "hospital_admin", "super_admin"];
const WORKLIST_POLL_MS = 45_000;

function getTriageLabel(value?: string): "CRITICAL" | "URGENT" | "LESS URGENT" {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "critical") return "CRITICAL";
  if (normalized === "urgent") return "URGENT";
  return "LESS URGENT";
}

function TriageBadge({ triage }: { triage?: string }) {
  const label = getTriageLabel(triage);
  const cls =
    label === "CRITICAL"
      ? "bg-red-100 text-red-800 border-red-200"
      : label === "URGENT"
        ? "bg-amber-100 text-amber-800 border-amber-200"
        : "bg-blue-100 text-blue-800 border-blue-200";
  return <span className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${cls}`}>{label}</span>;
}

function AllergyIndicator({ hasAllergy }: { hasAllergy?: boolean }) {
  if (!hasAllergy) return <span className="text-xs text-[#64748B]">None</span>;
  return (
    <span className="inline-flex items-center rounded-full border border-rose-200 bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-800">
      Allergy risk
    </span>
  );
}

export default function WorklistPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const { encounters, summary, loading, fetch } = useWorklistEncounters();
  const [departmentFilter, setDepartmentFilter] = React.useState("");
  const [encounterTypeFilter, setEncounterTypeFilter] = React.useState("");
  const canAccess = user?.role && WORKLIST_ROLES.includes(user.role);
  const fetchWithFilters = React.useCallback(async (silent = false) => {
    await fetch(silent, { department_id: departmentFilter || undefined, encounter_type: encounterTypeFilter || undefined });
  }, [departmentFilter, encounterTypeFilter, fetch]);

  usePollWhenVisible(
    () => {
      void fetchWithFilters(true);
    },
    WORKLIST_POLL_MS,
    canAccess ?? false
  );
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);
  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;
  const startConsultation = async (patientId: string, complaint: string) => {
    const encounter = await api.post<{ id: string }>(`/patients/${patientId}/encounters`, {
      encounter_type: "outpatient",
      chief_complaint: complaint || "",
      status: "in_consultation",
      visit_status: "in_consultation",
    });
    router.push(`/patients/${patientId}/encounter/${encounter.id}`);
  };

  if (user?.role === "nurse") {
    return <NurseWardWorklist />;
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
          {user?.role === "doctor" ? "My patients waiting" : "Waiting for consultation"}
        </h1>
        <p className="mt-1 text-sm text-[#64748B]">
          Patients routed to your department or assigned to you. Open the patient to consult or update the encounter.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Queue</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-3">
            <div className="rounded border border-[#E2E8F0] p-3 text-sm">
              Queue: <strong>{summary.queue_count}</strong>
            </div>
            <div className="rounded border border-[#E2E8F0] p-3 text-sm">
              Alerts: <strong>{summary.alerts}</strong>
            </div>
            <div className="rounded border border-[#E2E8F0] p-3 text-sm">
              Pending labs/Rx: <strong>{summary.pending_labs}</strong> / <strong>{summary.pending_prescriptions}</strong>
            </div>
          </div>
          <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2">
            <select
              className="h-10 rounded-lg border border-[#CBD5E1] px-3 text-sm"
              value={departmentFilter}
              onChange={(e) => setDepartmentFilter(e.target.value)}
            >
              <option value="">All departments</option>
              {[...new Map(encounters.filter((e) => e.assigned_department_id && e.assigned_department_name).map((e) => [e.assigned_department_id!, e.assigned_department_name!])).entries()]
                .map(([id, name]) => <option key={id} value={id}>{name}</option>)}
            </select>
            <select
              className="h-10 rounded-lg border border-[#CBD5E1] px-3 text-sm"
              value={encounterTypeFilter}
              onChange={(e) => setEncounterTypeFilter(e.target.value)}
            >
              <option value="">All encounter types</option>
              {[...new Set(encounters.map((e) => e.encounter_type))].map((t) => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
            </select>
          </div>
          {loading ? (
            <p className="py-8 text-center text-[#64748B]">Loading…</p>
          ) : encounters.length === 0 ? (
            <p className="py-8 text-center text-[#64748B]">No patients waiting.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Patient</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Ghana Health ID</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Department</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Status</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Triage</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Allergy</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Date</th>
                    <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {encounters.map((e) => (
                    <tr key={e.id} className="border-b border-[#F1F5F9]">
                      <td className="px-4 py-2 font-medium text-[#0F172A]">{e.patient_name}</td>
                      <td className="px-4 py-2 text-sm text-[#475569]">{e.ghana_health_id}</td>
                      <td className="px-4 py-2 text-sm text-[#475569]">{e.assigned_department_name ?? "—"}</td>
                      <td className="px-4 py-2">
                        <span
                          className={
                            e.status === "in_consultation"
                              ? "rounded-full bg-[#FEF3C7] px-2 py-0.5 text-xs text-[#92400E]"
                              : "rounded-full bg-[#DBEAFE] px-2 py-0.5 text-xs text-[#1E40AF]"
                          }
                        >
                          {e.status === "in_consultation" ? "In consultation" : "Waiting"}
                        </span>
                      </td>
                      <td className="px-4 py-2 text-xs"><TriageBadge triage={e.triage_badge} /></td>
                      <td className="px-4 py-2 text-xs"><AllergyIndicator hasAllergy={e.has_active_allergy} /></td>
                      <td className="px-4 py-2 text-sm text-[#64748B]">
                        {new Date(e.encounter_date).toLocaleString()}
                      </td>
                      <td className="px-4 py-2">
                        <div className="flex gap-2">
                          <Link href={`/patients/${e.patient_id}`}>
                            <Button size="sm" variant="secondary">
                              Open
                            </Button>
                          </Link>
                          <Button
                            size="sm"
                            onClick={() => startConsultation(e.patient_id, e.notes ?? "")}
                          >
                            Start consultation
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function NurseWardWorklist() {
  const { data, loading, fetch, dispense, acknowledgeHandover } = useNurseWorklist();
  const [tab, setTab] = React.useState<"beds" | "dispense" | "handover">("beds");
  const [noteContent, setNoteContent] = React.useState("");
  const [noteType, setNoteType] = React.useState<"observation" | "handover" | "incident">("observation");
  const [selectedPatientId, setSelectedPatientId] = React.useState<string>("");
  const [incomingNurseId, setIncomingNurseId] = React.useState<string>("");
  const api = useApi();

  if (loading || !data) return <div className="py-8 text-center text-[#64748B]">Loading...</div>;

  const saveNote = async () => {
    if (!selectedPatientId || !noteContent.trim()) return;
    await api.post("/records/nursing-note", {
      patient_id: selectedPatientId,
      note_type: noteType,
      incoming_nurse_id: noteType === "handover" ? incomingNurseId : undefined,
      content: noteContent.trim(),
    });
    setNoteContent("");
    await fetch();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">{data.ward_name} Worklist</h1>
        <Button size="sm" variant="secondary" onClick={() => void fetch()}>Refresh</Button>
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant={tab === "beds" ? "primary" : "secondary"} onClick={() => setTab("beds")}>Beds</Button>
        <Button size="sm" variant={tab === "dispense" ? "primary" : "secondary"} onClick={() => setTab("dispense")}>Dispense</Button>
        <Button size="sm" variant={tab === "handover" ? "primary" : "secondary"} onClick={() => setTab("handover")}>Handover</Button>
      </div>

      {tab === "beds" && (
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.beds.map((bed) => (
            <Card key={bed.bed_id} accent={bed.status === "critical" ? "red" : bed.status === "watch" ? "amber" : bed.status === "stable" ? "green" : "blue"}>
              <CardContent className="pt-4">
                <p className="font-semibold">{bed.bed_code}</p>
                {bed.patient_id ? (
                  <>
                    <p className="text-sm">{bed.patient_name}</p>
                    <p className="text-xs text-[#64748B]">Admitted for: {bed.admitted_for}</p>
                    <p className="text-xs text-[#64748B]">Last vitals: {bed.last_vitals_at ? new Date(bed.last_vitals_at).toLocaleString() : "Never"}</p>
                    <p className="mt-1 text-xs uppercase">{bed.status}</p>
                    <div className="mt-3 flex flex-wrap gap-2">
                      <Link href={`/patients/${bed.patient_id}/vitals/new`}><Button size="sm">Vitals</Button></Link>
                      <Link href={`/patients/${bed.patient_id}`}><Button size="sm" variant="secondary">Chart</Button></Link>
                      <Button size="sm" variant="secondary" onClick={() => { setSelectedPatientId(bed.patient_id ?? ""); setTab("handover"); }}>Note</Button>
                      <Button size="sm" variant="secondary" onClick={() => setTab("dispense")}>Dispense</Button>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-[#64748B] mt-2">Available</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {tab === "dispense" && (
        <Card>
          <CardHeader><CardTitle>Pending prescriptions</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {data.dispense_items.length === 0 ? <p className="text-sm text-[#64748B]">No pending items.</p> : data.dispense_items.map((row) => (
              <div key={row.record_id} className="rounded border border-[#E2E8F0] p-3">
                <p className="text-sm font-medium">{row.patient_name} · {row.bed_code ?? "Bed —"} · {row.drug_name}</p>
                <p className="text-xs text-[#64748B]">{row.dosage} · {row.frequency} · {row.route} · by {row.written_by}</p>
                {row.allergy_conflict ? (
                  <p className="mt-1 text-xs text-amber-700">ALLERGY CONFLICT — Override authorised: {row.allergy_override_reason || "reason not provided"}</p>
                ) : null}
                <div className="mt-2">
                  <Button size="sm" onClick={() => void dispense(row.record_id)}>Mark Dispensed</Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {tab === "handover" && (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card>
            <CardHeader><CardTitle>SBAR / Nursing Note</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <select className="h-10 w-full rounded border border-[#CBD5E1] px-3 text-sm" value={selectedPatientId} onChange={(e) => setSelectedPatientId(e.target.value)}>
                <option value="">Select patient</option>
                {data.beds.filter((b) => !!b.patient_id).map((b) => <option key={b.patient_id} value={b.patient_id}>{b.patient_name}</option>)}
              </select>
              <select className="h-10 w-full rounded border border-[#CBD5E1] px-3 text-sm" value={noteType} onChange={(e) => setNoteType(e.target.value as "observation" | "handover" | "incident")}>
                <option value="observation">Observation</option>
                <option value="handover">Handover</option>
                <option value="incident">Incident</option>
              </select>
              {noteType === "handover" ? (
                <select className="h-10 w-full rounded border border-[#CBD5E1] px-3 text-sm" value={incomingNurseId} onChange={(e) => setIncomingNurseId(e.target.value)}>
                  <option value="">Incoming nurse</option>
                  {data.incoming_nurse_candidates.map((n) => <option key={n.user_id} value={n.user_id}>{n.full_name}</option>)}
                </select>
              ) : null}
              <textarea className="min-h-[160px] w-full rounded border border-[#CBD5E1] p-3 text-sm" value={noteContent} onChange={(e) => setNoteContent(e.target.value)} />
              <Button onClick={() => void saveNote()}>Save note</Button>
            </CardContent>
          </Card>
          <Card>
            <CardHeader><CardTitle>Pending acknowledgments</CardTitle></CardHeader>
            <CardContent className="space-y-2">
              {data.handover_pending_ack.length === 0 ? <p className="text-sm text-[#64748B]">No pending handovers.</p> : data.handover_pending_ack.map((h) => (
                <div key={h.note_id} className="rounded border border-[#E2E8F0] p-3">
                  <p className="text-sm font-medium">{h.patient_name}</p>
                  <p className="text-xs text-[#64748B]">From: {h.outgoing_nurse_name} · {h.signed_at ? new Date(h.signed_at).toLocaleString() : ""}</p>
                  <p className="mt-2 text-sm whitespace-pre-wrap">{h.content}</p>
                  <Button className="mt-2" size="sm" onClick={() => void acknowledgeHandover(h.note_id)}>Acknowledge & Accept</Button>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
