"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { usePatient } from "@/hooks/use-patients";
import { usePatientRecords } from "@/hooks/use-patient-records";
import { useEncounters } from "@/hooks/use-encounters";
import { useApi } from "@/hooks/use-api";
import { useConsents, useBreakGlassList, useFacilities, useReferrals } from "@/hooks/use-interop";
import dynamic from 'next/dynamic';
const DischargeSummaryForm = dynamic(() => import("@/components/features/DischargeSummaryForm").then(mod => mod.DischargeSummaryForm), { ssr: false });
const AllergyBanner = dynamic(() => import("@/components/features/AllergyBanner").then(mod => mod.AllergyBanner), { ssr: false });
import { Button } from "@/components/ui/button";
import { SlideOver } from "@/components/features/SlideOver";
const RecordTimelineCard = dynamic(() => import("@/components/features/RecordTimelineCard").then(mod => mod.RecordTimelineCard), { ssr: false });
const AddRecordForm = dynamic(() => import("@/components/features/AddRecordForm").then(mod => mod.AddRecordForm), { ssr: false });
const AmendmentForm = dynamic(() => import("@/components/features/AmendmentForm").then(mod => mod.AmendmentForm), { ssr: false });
import type { MedicalRecord } from "@/lib/types";
import { ROLES, Role, RECORD_CREATE_ROLES, RECORD_AMEND_ROLES, ENCOUNTER_CREATE_ROLES, hasRole } from "@/lib/permissions";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useAppointments } from "@/hooks/use-appointments";
import { usePollWhenVisible } from "@/hooks/use-poll-when-visible";
import type { Patient, Consent } from "@/lib/types";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useAsyncAIAnalysis } from "@/hooks/use-async-ai-analysis";
import { AIAnalysisProgress } from "@/components/features/ai/ai-analysis-progress";

const PATIENT_LABS_POLL_MS = 45_000;

type Tab = "overview" | "encounters" | "diagnoses" | "prescriptions" | "labs" | "vitals" | "amendments" | "ai_history" | "ai_analysis";

/** Roles that see only demographics + appointments (no clinical records). */
const RESTRICTED_PATIENT_VIEW_ROLES: Role[] = [
  ROLES.RECEPTIONIST,
  ROLES.RADIOLOGY_TECHNICIAN,
  ROLES.BILLING_STAFF,
  ROLES.WARD_CLERK,
  ROLES.PHARMACY_TECHNICIAN,
  ROLES.HOSPITAL_ADMIN,
];

function ReceptionistPatientView({ patient, patientId }: { patient: Patient; patientId: string }) {
  const { appointments, loading } = useAppointments(undefined, patientId);
  const upcoming = appointments.filter(
    (a) => new Date(a.scheduled_at) >= new Date() && !["cancelled", "no_show"].includes(a.status)
  );
  return (
    <div className="space-y-8">
      <Breadcrumbs
        items={[
          { label: "Patients", href: "/patients/search" },
          { label: patient.full_name ?? "Patient" },
        ]}
      />
      <div className="rounded-lg border border-[#E2E8F0] bg-white p-6">
        <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Demographics</h2>
        <p className="mt-2 text-[#64748B]">
          {patient.full_name} · {patient.ghana_health_id}
        </p>
        <p className="text-sm text-[#64748B]">DOB: {patient.date_of_birth}</p>
        {patient.phone && <p className="text-sm text-[#64748B]">Phone: {patient.phone}</p>}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Upcoming Appointments</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-[#64748B]">Loading...</p>
          ) : upcoming.length === 0 ? (
            <p className="text-[#64748B]">No upcoming appointments</p>
          ) : (
            <ul className="space-y-2">
              {upcoming.slice(0, 20).map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-2 rounded border border-[#E2E8F0] p-2 text-sm">
                  <span>{new Date(a.scheduled_at).toLocaleString()}</span>
                  <span className="text-[#64748B]">{a.appointment_type}</span>
                  <span className="text-[#64748B]">{a.status}</span>
                  {a.provider_name && <span className="text-[#64748B]">— {a.provider_name}</span>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function HospitalAdminPatientView({ patient, patientId }: { patient: Patient; patientId: string }) {
  const { appointments, loading } = useAppointments(undefined, patientId);
  const upcoming = appointments.filter(
    (a) => new Date(a.scheduled_at) >= new Date() && !["cancelled", "no_show"].includes(a.status)
  );
  return (
    <div className="space-y-8">
      <Breadcrumbs
        items={[
          { label: "Patients", href: "/patients/search" },
          { label: patient.full_name ?? "Patient" },
        ]}
      />
      <div className="rounded-lg border border-[#E2E8F0] bg-[#F0F9FF] p-4">
        <p className="text-sm font-medium text-[#0F172A]">
          Clinical records are not available to your role. You can manage staff and view audit logs from the Admin section.
        </p>
      </div>
      <div className="rounded-lg border border-[#E2E8F0] bg-white p-6">
        <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Demographics</h2>
        <p className="mt-2 text-[#64748B]">
          {patient.full_name} · {patient.ghana_health_id}
        </p>
        <p className="text-sm text-[#64748B]">DOB: {patient.date_of_birth}</p>
        {patient.phone && <p className="text-sm text-[#64748B]">Phone: {patient.phone}</p>}
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Upcoming Appointments</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-[#64748B]">Loading...</p>
          ) : upcoming.length === 0 ? (
            <p className="text-[#64748B]">No upcoming appointments</p>
          ) : (
            <ul className="space-y-2">
              {upcoming.slice(0, 20).map((a) => (
                <li key={a.id} className="flex flex-wrap items-center gap-2 rounded border border-[#E2E8F0] p-2 text-sm">
                  <span>{new Date(a.scheduled_at).toLocaleString()}</span>
                  <span className="text-[#64748B]">{a.appointment_type}</span>
                  <span className="text-[#64748B]">{a.status}</span>
                  {a.provider_name && <span className="text-[#64748B]">— {a.provider_name}</span>}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function PatientPage() {
  const params = useParams();
  const id = params.id as string;
  const { user } = useAuth();
  const router = useRouter();
  const { patient, loading, error, fetch } = usePatient(id);
  const {
    records,
    diagnoses,
    prescriptions,
    labs,
    vitals,
    fetchAll,
  } = usePatientRecords(id);
  const api = useApi();
  const { encounters, loading: encountersLoading, fetch: fetchEncounters } = useEncounters(id);
  const { facilities, fetch: fetchFacilities } = useFacilities();
  const { list: consents, fetchList: fetchConsents, grant: grantConsent, revoke: revokeConsent } = useConsents();
  const { list: breakGlassList, fetchList: fetchBreakGlass } = useBreakGlassList();
  const { create: createReferral } = useReferrals();
  const aiAnalysis = useAsyncAIAnalysis(id);

  const [tab, setTab] = useState<Tab>("overview");
  const [addOpen, setAddOpen] = useState(false);
  const [dischargeSummaryOpen, setDischargeSummaryOpen] = useState(false);
  const [consentModalOpen, setConsentModalOpen] = useState(false);
  const [referralModalOpen, setReferralModalOpen] = useState(false);
  const [consentFacilityId, setConsentFacilityId] = useState("");
  const [consentScope, setConsentScope] = useState<"SUMMARY" | "FULL_RECORD">("SUMMARY");
  const [consentExpiresAt, setConsentExpiresAt] = useState("");
  const [referralFacilityId, setReferralFacilityId] = useState("");
  const [referralReason, setReferralReason] = useState("");
  const [consentSuccess, setConsentSuccess] = useState<string | null>(null);
  const [referralSuccess, setReferralSuccess] = useState(false);
  const [amendRecord, setAmendRecord] = useState<MedicalRecord | null>(null);
  const [exportPdfLoading, setExportPdfLoading] = useState(false);
  const [addRecordInitialType, setAddRecordInitialType] = useState<"vital_signs" | "nursing_note" | null>(null);
  const [consentToRevoke, setConsentToRevoke] = useState<Consent | null>(null);
  const [revokeConsentLoading, setRevokeConsentLoading] = useState(false);
  const [aiHistory, setAiHistory] = useState<Array<{ timestamp?: string; analysis_type?: string; confidence_score?: number }>>([]);
  const [closeEncounterConfirmOpen, setCloseEncounterConfirmOpen] = useState(false);
  const [closeEncounterLoading, setCloseEncounterLoading] = useState(false);

  const handleExportPdf = async () => {
    if (!id) return;
    setExportPdfLoading(true);
    try {
      const blob = await api.getBlob(`/patients/${id}/export-pdf`);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `patient_${patient?.ghana_health_id ?? id}_record.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      // Error is logged; could show toast
      if (process.env.NODE_ENV === "development") {
        console.error("PDF export failed:", error);
      }
    } finally {
      setExportPdfLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, [fetch]);

  useEffect(() => {
    if (user?.role !== "nurse" || !id) return;
    let cancelled = false;
    (async () => {
      try {
        const resp = await api.get<{ beds?: Array<{ patient_id?: string }> }>("/nurse/worklist");
        const patientIds = new Set((resp.beds || []).map((b) => b.patient_id).filter(Boolean) as string[]);
        if (!cancelled && !patientIds.has(id)) {
          router.replace("/worklist");
        }
      } catch {
        if (!cancelled) router.replace("/worklist");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user?.role, id, api, router]);

  const isRestrictedView = user?.role && RESTRICTED_PATIENT_VIEW_ROLES.includes(user.role);
  useEffect(() => {
    if (patient && !isRestrictedView) fetchAll();
  }, [patient, fetchAll, isRestrictedView]);
  useEffect(() => {
    if (id && !isRestrictedView) fetchEncounters();
  }, [id, fetchEncounters, isRestrictedView]);
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ data?: Array<{ timestamp?: string; analysis_type?: string; confidence_score?: number }> }>(`/ai/analysis-history/${id}`);
        if (!cancelled) setAiHistory(res.data || []);
      } catch {
        if (!cancelled) setAiHistory([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, id]);

  const globalPatientId = patient?.global_patient_id ?? null;

  useEffect(() => {
    if (globalPatientId) {
      fetchConsents(globalPatientId);
      fetchBreakGlass(globalPatientId);
    }
  }, [globalPatientId, fetchConsents, fetchBreakGlass]);

  useEffect(() => {
    if (consentModalOpen || referralModalOpen) fetchFacilities();
  }, [consentModalOpen, referralModalOpen, fetchFacilities]);

  usePollWhenVisible(
    () => fetchAll(true),
    PATIENT_LABS_POLL_MS,
    !isRestrictedView && tab === "labs"
  );

  const canInterop =
    (user?.role === "doctor" || user?.role === "hospital_admin" || user?.role === "super_admin") &&
    !!globalPatientId;

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-[#64748B]">Loading patient...</p>
      </div>
    );
  }

  if (error || !patient) {
    return (
      <div className="rounded-lg bg-[#FEE2E2] p-4 text-[#B91C1C]">
        {error || "Patient not found"}
      </div>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: "overview", label: "Overview" },
    { id: "encounters", label: "Encounters" },
    { id: "prescriptions", label: "Prescriptions" },
    { id: "labs", label: "Labs" },
    { id: "vitals", label: "Vitals" },
    { id: "amendments", label: "Amendments" },
    { id: "ai_analysis", label: "AI Analysis" },
    { id: "ai_history", label: "AI History" },
  ];
  if (user?.role !== "nurse") {
    tabs.splice(2, 0, { id: "diagnoses", label: "Diagnoses" });
  }

  const isDoctor = user?.role === ROLES.DOCTOR;
  const isNurse = user?.role === ROLES.NURSE;
  const canAddRecord = hasRole(user?.role, RECORD_CREATE_ROLES);
  const showFullAddRecordFAB = isDoctor || (user?.role === ROLES.SUPER_ADMIN);
  const canAddEncounter = hasRole(user?.role, ENCOUNTER_CREATE_ROLES);
  const canExportPdf = user?.role === ROLES.DOCTOR || user?.role === ROLES.SUPER_ADMIN;
  // RBAC-06: only doctors and super_admin can amend records
  const canAmendRecords = hasRole(user?.role, RECORD_AMEND_ROLES);

  if (user?.role === "receptionist") {
    return <ReceptionistPatientView patient={patient} patientId={id} />;
  }
  if (user?.role === "hospital_admin") {
    return <HospitalAdminPatientView patient={patient} patientId={id} />;
  }

  return (
    <div className="space-y-8">
      <Breadcrumbs
        items={[
          { label: "Patients", href: "/patients/search" },
          { label: patient.full_name ?? "Patient" },
        ]}
      />
      <div className="sticky top-0 z-10 -mx-8 -mt-8 bg-[#F5F3EE] px-8 pb-4 pt-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="h-16 w-16 rounded-full bg-[#0EAFBE] flex items-center justify-center text-2xl font-bold text-white">
              {patient.full_name?.charAt(0) || "?"}
            </div>
            <div>
              <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
                {patient.full_name}
              </h1>
              <p className="font-mono text-sm text-[#64748B]">
                {patient.ghana_health_id}
              </p>
              <p className="mt-1 text-sm text-[#64748B]">
                DOB: {patient.date_of_birth} | {patient.gender} | Blood: {patient.blood_group}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            {canExportPdf && (
              <Button variant="secondary" onClick={handleExportPdf} disabled={exportPdfLoading}>
                {exportPdfLoading ? "Exporting..." : "Export PDF"}
              </Button>
            )}
            {canAddEncounter && (
              <Link href={`/patients/${id}/encounters/new`}>
                <Button variant="secondary">Add Encounter</Button>
              </Link>
            )}
            {showFullAddRecordFAB && (
              <Button onClick={() => { setAddRecordInitialType(null); setAddOpen(true); }}>Add Record</Button>
            )}
            {isNurse && (
              <>
                <Button onClick={() => { setAddRecordInitialType("vital_signs"); setAddOpen(true); }}>Add Vitals</Button>
                <Button variant="secondary" onClick={() => { setAddRecordInitialType("nursing_note"); setAddOpen(true); }}>Add Nursing Note</Button>
              </>
            )}
            {canInterop && (
              <>
                <Button variant="secondary" onClick={() => { setConsentSuccess(null); setConsentModalOpen(true); }}>
                  Manage sharing
                </Button>
                <Button variant="secondary" onClick={() => { setReferralSuccess(false); setReferralModalOpen(true); }}>
                  Create referral
                </Button>
              </>
            )}
          </div>
        </div>

        <AllergyBanner allergies={patient.allergies || []} />
      </div>

      <div className="flex gap-2 border-b border-[#CBD5E1]">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`border-b-2 px-4 py-2 text-sm font-medium ${
              tab === t.id
                ? "border-[#0B8A96] text-[#0B8A96]"
                : "border-transparent text-[#64748B] hover:text-[#0F172A]"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="min-h-[200px]">
        {tab === "encounters" && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {canAddEncounter && (
                <>
                  <Link href={`/patients/${id}/encounters/new`}>
                    <Button size="sm">Add Encounter</Button>
                  </Link>
                  {encounters.length > 0 && (
                    <Button size="sm" variant="secondary" onClick={() => setDischargeSummaryOpen(true)}>
                      Discharge summary
                    </Button>
                  )}
                  {encounters.some((e) => e.status !== "completed") && (
                    <Button size="sm" variant="secondary" onClick={() => setCloseEncounterConfirmOpen(true)}>
                      Close encounter
                    </Button>
                  )}
                </>
              )}
            </div>
            {encountersLoading ? (
              <p className="text-[#64748B]">Loading encounters...</p>
            ) : encounters.length === 0 ? (
              <p className="text-[#64748B]">No encounters yet.</p>
            ) : (
              <ul className="space-y-2">
                {encounters.map((e) => (
                  <li key={e.id} className="rounded-lg border border-[#E2E8F0] p-3">
                    <span className="font-medium capitalize">{e.encounter_type?.replace("_", " ")}</span>
                    <span className="ml-2 text-sm text-[#64748B]">
                      {e.encounter_date ? new Date(e.encounter_date).toLocaleString() : ""}
                    </span>
                    {e.created_by && <span className="ml-2 text-xs text-[#94A3B8]">by {e.created_by}</span>}
                    {e.notes && <p className="mt-1 text-sm text-[#64748B]">{e.notes}</p>}
                    {e.discharge_summary && (
                      <p className="mt-2 text-sm text-[#475569] border-t border-[#E2E8F0] pt-2 whitespace-pre-wrap">
                        {e.discharge_summary}
                      </p>
                    )}
                  </li>
                ))}
              </ul>
            )}
            <DischargeSummaryForm
              open={dischargeSummaryOpen}
              onOpenChange={setDischargeSummaryOpen}
              encounters={encounters}
              patientId={id}
              onSave={async (encounterId, text) => {
                await api.patch(`/patients/${id}/encounters/${encounterId}`, { discharge_summary: text });
              }}
              onSuccess={fetchEncounters}
            />
          </div>
        )}
        {tab === "overview" && (
          <div className="space-y-4">
            {records.length ? (
              records.map((r) => (
                <RecordTimelineCard
                  key={r.record_id}
                  record={r}
                  hospitalName={r.hospital_id ? undefined : undefined}
                  canAmend={canAmendRecords}  // RBAC-06: server-aligned
                  onAmend={(rec) => setAmendRecord(rec)}
                />
              ))
            ) : (
              <p className="text-[#64748B]">No records yet.</p>
            )}
          </div>
        )}
        {tab === "diagnoses" && (
          <div className="space-y-2">
            {isNurse ? (
              <p className="rounded-lg border border-[#E2E8F0] bg-[#F8FAFC] p-4 text-[#64748B]">Clinical records are restricted to the care team.</p>
            ) : diagnoses.length ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="py-2 text-left font-medium">ICD-10</th>
                    <th className="py-2 text-left font-medium">Description</th>
                    <th className="py-2 text-left font-medium">Severity</th>
                    <th className="py-2 text-left font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {diagnoses.map((d) => (
                    <tr key={d.diagnosis_id} className="border-b border-[#F1F5F9]">
                      <td className="py-2 font-mono">{d.icd10_code}</td>
                      <td className="py-2">{d.icd10_description}</td>
                      <td className="py-2">{d.severity}</td>
                      <td className="py-2 text-[#64748B]">{d.created_at?.slice(0, 10)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-[#64748B]">No diagnoses.</p>
            )}
          </div>
        )}
        {tab === "prescriptions" && (
          <div className="space-y-2">
            {prescriptions.length ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="py-2 text-left font-medium">Drug</th>
                    <th className="py-2 text-left font-medium">Dosage</th>
                    <th className="py-2 text-left font-medium">Frequency</th>
                    <th className="py-2 text-left font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {prescriptions.map((p) => (
                    <tr key={p.prescription_id} className="border-b border-[#F1F5F9]">
                      <td className="py-2">{p.drug_name}</td>
                      <td className="py-2">{p.dosage}</td>
                      <td className="py-2">{p.frequency}</td>
                      <td className="py-2">
                        <span
                          className={`rounded-full px-2 py-0.5 text-xs ${
                            p.dispense_status === "dispensed"
                              ? "bg-green-100 text-green-700"
                              : p.dispense_status === "cancelled"
                                ? "bg-gray-100 text-gray-600"
                                : "bg-amber-100 text-amber-700"
                          }`}
                        >
                          {p.dispense_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-[#64748B]">No prescriptions.</p>
            )}
          </div>
        )}
        {tab === "labs" && (
          <div className="space-y-2">
            {labs.length ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="py-2 text-left font-medium">Test</th>
                    <th className="py-2 text-left font-medium">Result</th>
                    <th className="py-2 text-left font-medium">Range</th>
                    <th className="py-2 text-left font-medium">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {labs.map((l) => (
                    <tr key={l.lab_result_id} className="border-b border-[#F1F5F9]">
                      <td className="py-2">{l.test_name}</td>
                      <td className="py-2">{l.result_value || "—"}</td>
                      <td className="py-2 text-[#64748B]">{l.reference_range || "—"}</td>
                      <td className="py-2">{l.status}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-[#64748B]">No lab results.</p>
            )}
          </div>
        )}
        {tab === "vitals" && (
          <div className="space-y-2">
            {vitals.length ? (
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-[#E2E8F0]">
                    <th className="py-2 text-left font-medium">Date</th>
                    <th className="py-2 text-left font-medium">Temp</th>
                    <th className="py-2 text-left font-medium">Pulse</th>
                    <th className="py-2 text-left font-medium">BP</th>
                    <th className="py-2 text-left font-medium">SpO2</th>
                  </tr>
                </thead>
                <tbody>
                  {vitals.map((v) => (
                    <tr key={v.vital_id} className="border-b border-[#F1F5F9]">
                      <td className="py-2 text-[#64748B]">{v.created_at?.slice(0, 16)}</td>
                      <td className="py-2">{v.temperature_c ?? "—"}</td>
                      <td className="py-2">{v.pulse_bpm ?? "—"}</td>
                      <td className="py-2">
                        {v.bp_systolic != null && v.bp_diastolic != null
                          ? `${v.bp_systolic}/${v.bp_diastolic}`
                          : "—"}
                      </td>
                      <td className="py-2">{v.spo2_percent ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="text-[#64748B]">No vitals recorded.</p>
            )}
          </div>
        )}
        {tab === "amendments" && (
          <div className="space-y-2">
            {records.filter((r) => r.is_amended || r.amendment_reason).length ? (
              records
                .filter((r) => r.is_amended || r.amendment_reason)
                .map((r) => (
                  <div key={r.record_id} className="rounded-lg border border-[#E2E8F0] bg-white p-4">
                    <p className="font-medium">{r.record_type.replace("_", " ")}</p>
                    <p className="text-sm text-[#64748B]">{r.amendment_reason || "Amended record"}</p>
                  </div>
                ))
            ) : (
              <p className="text-[#64748B]">No amendments.</p>
            )}
          </div>
        )}
        {tab === "ai_history" && (
          <div className="space-y-2">
            {aiHistory.length ? (
              aiHistory.map((h, idx) => (
                <div key={`${h.timestamp || "t"}-${idx}`} className="rounded-lg border border-[#E2E8F0] bg-white p-4 text-sm">
                  <p className="font-medium">{h.analysis_type || "Analysis"}</p>
                  <p className="text-[#64748B]">
                    {h.timestamp ? new Date(h.timestamp).toLocaleString() : "Unknown time"}
                    {typeof h.confidence_score === "number" ? ` · Confidence ${Math.round(h.confidence_score * 100)}%` : ""}
                  </p>
                </div>
              ))
            ) : (
              <p className="text-[#64748B]">No AI history.</p>
            )}
          </div>
        )}
        {tab === "ai_analysis" && (
          <div className="space-y-4">
            <AIAnalysisProgress
              jobId={aiAnalysis.jobId}
              status={aiAnalysis.status}
              progressPercent={aiAnalysis.progressPercent}
              currentStep={aiAnalysis.currentStep}
              analysis={aiAnalysis.analysis}
              error={aiAnalysis.error}
              onStart={async () => {
                await aiAnalysis.startAnalysis();
              }}
              onCancel={aiAnalysis.cancelJob}
              onRetry={async () => {
                await aiAnalysis.startAnalysis();
              }}
              onClose={() => setTab("overview")}
              onStartNew={() => {
                aiAnalysis.cancelJob();
                setTimeout(() => {
                  aiAnalysis.startAnalysis();
                }, 500);
              }}
            />
          </div>
        )}
        {tab === "ai_history" && canInterop && globalPatientId && false && (
          <div className="space-y-6">
            <section>
              <h3 className="text-sm font-semibold text-[#0F172A] mb-2">Active consents</h3>
              {consents.filter((c) => c.is_active && (!c.expires_at || new Date(c.expires_at) > new Date())).length ? (
                <ul className="space-y-2">
                  {consents
                    .filter((c) => c.is_active && (!c.expires_at || new Date(c.expires_at) > new Date()))
                    .map((c) => (
                      <li key={c.consent_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-[#E2E8F0] bg-white p-3 text-sm">
                        <span>
                          {c.granted_to_facility_name} — {c.scope}
                          {c.expires_at ? ` until ${c.expires_at.slice(0, 10)}` : " (no expiry)"}
                        </span>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => setConsentToRevoke(c)}
                        >
                          Revoke
                        </Button>
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-[#64748B]">No active consents.</p>
              )}
            </section>
            <section>
              <h3 className="text-sm font-semibold text-[#0F172A] mb-2">Expired / revoked consents</h3>
              {consents.filter((c) => !c.is_active || (c.expires_at && new Date(c.expires_at) <= new Date())).length ? (
                <ul className="space-y-2">
                  {consents
                    .filter((c) => !c.is_active || (c.expires_at && new Date(c.expires_at) <= new Date()))
                    .map((c) => (
                      <li key={c.consent_id} className="rounded-lg border border-[#F1F5F9] bg-[#F8FAFC] p-3 text-sm text-[#64748B]">
                        {c.granted_to_facility_name} — {c.scope} — {c.is_active ? "expired" : "revoked"}
                      </li>
                    ))}
                </ul>
              ) : (
                <p className="text-[#64748B]">None.</p>
              )}
            </section>
            <section>
              <h3 className="text-sm font-semibold text-[#0F172A] mb-2">Break-glass history</h3>
              {breakGlassList.length ? (
                <ul className="space-y-2">
                  {breakGlassList.map((b) => (
                    <li key={b.break_glass_id} className="rounded-lg border border-[#FEE2E2] bg-[#FEF2F2] p-3 text-sm">
                      {b.created_at} — {b.reason}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-[#64748B]">No break-glass access recorded.</p>
              )}
            </section>
          </div>
        )}
      </div>

      {/* Consent modal */}
      <Dialog open={consentModalOpen} onOpenChange={setConsentModalOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Grant consent</DialogTitle>
            </DialogHeader>
            {globalPatientId && (
              <div className="space-y-4">
                <label className="block text-sm font-medium text-[#0F172A]">Facility</label>
                <select
                  className="w-full rounded-lg border border-[#CBD5E1] px-3 py-2 text-sm"
                  value={consentFacilityId}
                  onChange={(e) => setConsentFacilityId(e.target.value)}
                >
                  <option value="">Select facility</option>
                  {facilities.map((f) => (
                    <option key={f.facility_id} value={f.facility_id}>{f.name}</option>
                  ))}
                </select>
                <label className="block text-sm font-medium text-[#0F172A]">Scope</label>
                <select
                  className="w-full rounded-lg border border-[#CBD5E1] px-3 py-2 text-sm"
                  value={consentScope}
                  onChange={(e) => setConsentScope(e.target.value as "SUMMARY" | "FULL_RECORD")}
                >
                  <option value="SUMMARY">Summary only</option>
                  <option value="FULL_RECORD">Full record</option>
                </select>
                <Input
                  label="Expiration date (optional)"
                  type="date"
                  value={consentExpiresAt}
                  onChange={(e) => setConsentExpiresAt(e.target.value)}
                />
                {consentSuccess && <p className="text-sm text-[#0B8A96]">{consentSuccess}</p>}
                <div className="mt-4 flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setConsentModalOpen(false)}>Cancel</Button>
                  <Button
                    disabled={!consentFacilityId}
                    onClick={async () => {
                      try {
                        await grantConsent({
                          global_patient_id: globalPatientId,
                          granted_to_facility_id: consentFacilityId,
                          scope: consentScope,
                          expires_at: consentExpiresAt || null,
                        });
                        const facilityName = facilities.find((f) => f.facility_id === consentFacilityId)?.name ?? "Facility";
                        setConsentSuccess(`${facilityName} now has access${consentExpiresAt ? ` until ${consentExpiresAt}` : " (no expiry)"}.`);
                        fetchConsents(globalPatientId);
                      } catch {
                        setConsentSuccess(null);
                      }
                    }}
                  >
                    Grant
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </DialogPortal>
      </Dialog>

      <ConfirmDialog
        open={closeEncounterConfirmOpen}
        onOpenChange={setCloseEncounterConfirmOpen}
        title="Close encounter"
        message={`Close active encounter and mark visit discharged?\nAdded items: Diagnoses ${diagnoses.length}, Prescriptions ${prescriptions.length}, Labs ${labs.length}, Vitals ${vitals.length}.`}
        confirmLabel="Close encounter"
        loading={closeEncounterLoading}
        onConfirm={async () => {
          const openEncounter = encounters.find((e) => e.status !== "completed");
          if (!openEncounter) return;
          setCloseEncounterLoading(true);
          try {
            await api.post(`/patients/${id}/encounters/${openEncounter.id}/close`, {
              confirmation_items: [
                `diagnoses:${diagnoses.length}`,
                `prescriptions:${prescriptions.length}`,
                `labs:${labs.length}`,
                `vitals:${vitals.length}`,
              ],
            });
            fetchEncounters();
            setCloseEncounterConfirmOpen(false);
          } finally {
            setCloseEncounterLoading(false);
          }
        }}
      />

      <ConfirmDialog
        open={consentToRevoke !== null}
        onOpenChange={(open) => { if (!open) setConsentToRevoke(null); }}
        title="Revoke consent"
        message={
          consentToRevoke
            ? `Revoke access for ${consentToRevoke.granted_to_facility_name} (${consentToRevoke.scope})? This cannot be undone.`
            : ""
        }
        confirmLabel="Revoke"
        variant="danger"
        loading={revokeConsentLoading}
        onConfirm={async () => {
          if (!consentToRevoke || !globalPatientId) return;
          setRevokeConsentLoading(true);
          try {
            await revokeConsent(consentToRevoke.consent_id);
            fetchConsents(globalPatientId);
            setConsentToRevoke(null);
          } finally {
            setRevokeConsentLoading(false);
          }
        }}
      />

      {/* Referral modal - simplified: use api directly */}
      <Dialog open={referralModalOpen} onOpenChange={setReferralModalOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create referral</DialogTitle>
            </DialogHeader>
            {globalPatientId && (
              <div className="space-y-4">
                <label className="block text-sm font-medium text-[#0F172A]">To facility</label>
                <select
                  className="w-full rounded-lg border border-[#CBD5E1] px-3 py-2 text-sm"
                  value={referralFacilityId}
                  onChange={(e) => setReferralFacilityId(e.target.value)}
                >
                  <option value="">Select facility</option>
                  {facilities.filter((f) => f.facility_id !== user?.hospital_id).map((f) => (
                    <option key={f.facility_id} value={f.facility_id}>{f.name}</option>
                  ))}
                </select>
                <Input
                  label="Reason"
                  value={referralReason}
                  onChange={(e) => setReferralReason(e.target.value)}
                  placeholder="Reason for referral"
                />
                {referralSuccess && <p className="text-sm text-[#0B8A96]">Referral created.</p>}
                <div className="mt-4 flex justify-end gap-2">
                  <Button variant="secondary" onClick={() => setReferralModalOpen(false)}>Cancel</Button>
                  <Button
                    disabled={!referralFacilityId || !referralReason.trim()}
                    onClick={async () => {
                      try {
                        await createReferral({
                          global_patient_id: globalPatientId,
                          to_facility_id: referralFacilityId,
                          reason: referralReason.trim(),
                        });
                        setReferralSuccess(true);
                        setTimeout(() => { setReferralModalOpen(false); setReferralSuccess(false); }, 1500);
                      } catch {
                        setReferralSuccess(false);
                      }
                    }}
                  >
                    Create referral
                  </Button>
                </div>
              </div>
            )}
          </DialogContent>
        </DialogPortal>
      </Dialog>

      {/* Amend record slide-over */}
      {amendRecord && (
        <SlideOver
          open={!!amendRecord}
          onOpenChange={(open) => !open && setAmendRecord(null)}
          title="Add amendment"
        >
          <AmendmentForm
            record={amendRecord}
            onSuccess={fetchAll}
            onClose={() => setAmendRecord(null)}
          />
        </SlideOver>
      )}

      {canAddRecord && (
        <>
          {showFullAddRecordFAB && (
            <button
              type="button"
              onClick={() => { setAddRecordInitialType(null); setAddOpen(true); }}
              className="fixed bottom-8 right-8 flex h-14 w-14 items-center justify-center rounded-full bg-[#0B8A96] text-white shadow-lg hover:bg-[#0A7A85]"
              aria-label="Add record"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 5v14M5 12h14" />
              </svg>
            </button>
          )}
          <SlideOver open={addOpen} onOpenChange={(open) => { setAddOpen(open); if (!open) setAddRecordInitialType(null); }} title={addRecordInitialType ? (addRecordInitialType === "vital_signs" ? "Add Vitals" : "Add Nursing Note") : "Add Record"}>
            <AddRecordForm
              patientId={id}
              onSuccess={fetchAll}
              onClose={() => setAddOpen(false)}
              initialType={addRecordInitialType ?? undefined}
            />
          </SlideOver>
        </>
      )}
    </div>
  );
}
