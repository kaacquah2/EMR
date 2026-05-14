"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useApi } from "@/hooks/use-api";
import { usePatient } from "@/hooks/use-patients";
import { useAIAnalysis } from "@/hooks/use-ai-analysis";
import { usePatientRecords } from "@/hooks/use-patient-records";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AllergyBanner } from "@/components/features/AllergyBanner";
import { AllergyConflictModal } from "@/components/features/AllergyConflictModal";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

type EncounterData = {
  id: string;
  status?: string;
  visit_status?: string;
  chief_complaint?: string | null;
  hpi?: string | null;
  examination_findings?: string | null;
  assessment_plan?: string | null;
  notes?: string | null;
};

type Point = number | null;

function Sparkline({ data }: { data: Point[] }) {
  const width = 120;
  const height = 30;
  const valid = data.filter((d): d is number => typeof d === "number");
  if (valid.length < 2) return <span className="text-xs text-slate-500 dark:text-slate-500">No trend</span>;
  const min = Math.min(...valid);
  const max = Math.max(...valid);
  const span = Math.max(max - min, 1);
  const points = data
    .map((v, i) => {
      if (v == null) return null;
      const x = (i / Math.max(data.length - 1, 1)) * width;
      const y = height - ((v - min) / span) * height;
      return `${x},${y}`;
    })
    .filter(Boolean)
    .join(" ");
  return (
    <svg width={width} height={height} className="overflow-visible">
      <polyline fill="none" stroke="#0B8A96" strokeWidth="2" points={points} />
    </svg>
  );
}

export default function EncounterDetailPage() {
  const params = useParams();
  const router = useRouter();
  const api = useApi();
  const { analyzePatient, loading: aiLoading } = useAIAnalysis();
  const patientId = params.id as string;
  const encounterId = params.encounterId as string;
  const { patient } = usePatient(patientId);
  const { vitals, diagnoses, prescriptions, labs, fetchAll } = usePatientRecords(patientId);

  const [encounter, setEncounter] = useState<EncounterData | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedAt, setSavedAt] = useState<string>("");
  const [dirty, setDirty] = useState(false);
  const [aiOpen, setAiOpen] = useState(false);
  const [aiResult, setAiResult] = useState<{
    risk_scores?: Record<string, { risk_score?: number }>;
    diagnosis_suggestions?: { suggestions?: Array<{ diagnosis: string; icd10_code?: string; probability?: number }> };
    triage_assessment?: { triage_level?: string };
  } | null>(null);

  const [icdQuery, setIcdQuery] = useState("");
  const [icdSuggestions, setIcdSuggestions] = useState<Array<{ code: string; description: string }>>([]);
  const [diagnosisCode, setDiagnosisCode] = useState("");
  const [diagnosisDesc, setDiagnosisDesc] = useState("");
  const [diagnosisSeverity, setDiagnosisSeverity] = useState("moderate");

  const [drugName, setDrugName] = useState("");
  const [drugSuggestions, setDrugSuggestions] = useState<Array<{ name: string; allergy_flag?: boolean }>>([]);
  const [dosage, setDosage] = useState("");
  const [frequency, setFrequency] = useState("");
  const [durationDays, setDurationDays] = useState("");
  const [route, setRoute] = useState("oral");
  const [overrideReason, setOverrideReason] = useState("");
  const [allergyConflict, setAllergyConflict] = useState<{ allergen: string; reaction: string; severity: string } | null>(null);
  const [closeOpen, setCloseOpen] = useState(false);

  useEffect(() => {
    (async () => {
      const data = await api.get<EncounterData>(`/patients/${patientId}/encounters/${encounterId}`);
      setEncounter(data);
      setDirty(false);
    })();
  }, [api, patientId, encounterId]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  useEffect(() => {
    if (!dirty || !encounter) return;
    const interval = setInterval(async () => {
      setSaving(true);
      try {
        await api.patch(`/patients/${patientId}/encounters/${encounterId}`, {
          chief_complaint: encounter.chief_complaint || "",
          hpi: encounter.hpi || "",
          examination_findings: encounter.examination_findings || "",
          assessment_plan: encounter.assessment_plan || "",
          notes: encounter.notes || "",
          status: encounter.status === "completed" ? "completed" : "in_consultation",
        });
        setSavedAt(new Date().toLocaleTimeString());
        setDirty(false);
      } finally {
        setSaving(false);
      }
    }, 30000);
    return () => clearInterval(interval);
  }, [api, dirty, encounter, patientId, encounterId]);

  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (!dirty) return;
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);

  useEffect(() => {
    if (icdQuery.trim().length < 2) {
      setIcdSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      const res = await api.get<{ data: Array<{ code: string; description: string }> }>(`/icd10/search?q=${encodeURIComponent(icdQuery.trim())}`);
      setIcdSuggestions(res.data || []);
    }, 200);
    return () => clearTimeout(t);
  }, [api, icdQuery]);

  useEffect(() => {
    if (drugName.trim().length < 2) {
      setDrugSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      const res = await api.get<{ data: Array<{ name: string; allergy_flag?: boolean }> }>(
        `/records/drug-autocomplete?q=${encodeURIComponent(drugName.trim())}&patient_id=${encodeURIComponent(patientId)}`
      );
      setDrugSuggestions(res.data || []);
    }, 200);
    return () => clearTimeout(t);
  }, [api, drugName, patientId]);

  const last5Vitals = useMemo(() => {
    const recent = [...vitals].slice(0, 5).reverse();
    return {
      bp: recent.map((v) => (v.bp_systolic != null ? Number(v.bp_systolic) : null)),
      pulse: recent.map((v) => (v.pulse_bpm != null ? Number(v.pulse_bpm) : null)),
      temp: recent.map((v) => (v.temperature_c != null ? Number(v.temperature_c) : null)),
    };
  }, [vitals]);

  if (!patient || !encounter) return <div className="py-8 text-center text-slate-500 dark:text-slate-500">Loading encounter...</div>;

  const setEncounterField = (field: keyof EncounterData, value: string) => {
    setEncounter((prev) => (prev ? { ...prev, [field]: value } : prev));
    setDirty(true);
  };

  const runAI = async () => {
    const res = await analyzePatient(patientId, { include_similarity: true, include_referral: true });
    setAiResult({
      risk_scores: res.risk_analysis?.predictions,
      diagnosis_suggestions: res.diagnosis_suggestions,
      triage_assessment: res.triage_assessment,
    });
    setAiOpen(true);
  };

  const addDiagnosis = async () => {
    await api.post("/records/diagnosis", {
      patient_id: patientId,
      icd10_code: diagnosisCode,
      icd10_description: diagnosisDesc,
      severity: diagnosisSeverity,
      is_chronic: false,
    });
    setDiagnosisCode("");
    setDiagnosisDesc("");
    fetchAll(true);
  };

  const savePrescription = async (withOverride = false) => {
    try {
      await api.post("/records/prescription", {
        patient_id: patientId,
        drug_name: drugName,
        dosage,
        frequency,
        duration_days: durationDays ? Number(durationDays) : undefined,
        route,
        override_reason: withOverride ? overrideReason : undefined,
      });
      setDrugName("");
      setDosage("");
      setFrequency("");
      setDurationDays("");
      setAllergyConflict(null);
      setOverrideReason("");
      fetchAll(true);
    } catch (err) {
      const e = err as Error & { statusCode?: number; detail?: { conflict?: boolean; allergen?: string; reaction?: string; severity?: string } };
      if (e.statusCode === 409 || e.detail?.conflict) {
        setAllergyConflict({
          allergen: String(e.detail?.allergen || ""),
          reaction: String(e.detail?.reaction || ""),
          severity: String(e.detail?.severity || ""),
        });
      }
    }
  };

  return (
    <div className="space-y-6">
      <div className="sticky top-0 z-20 rounded-lg border border-slate-200 dark:border-slate-800 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="font-semibold text-slate-900 dark:text-slate-100">
              {patient.full_name} · {patient.gender} · {patient.blood_group} · NHIS: {patient.nhis_number || "N/A"}
            </p>
            <p className="text-xs text-slate-500 dark:text-slate-500">
              {saving ? "Saving draft..." : savedAt ? `Saved draft at ${savedAt}` : "Autosave every 30s"}
            </p>
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" onClick={runAI} disabled={aiLoading}>
              {aiLoading ? "Running AI..." : "Run AI Analysis"}
            </Button>
            <Button onClick={() => setCloseOpen(true)} disabled={encounter.status === "completed"}>
              Mark as Complete
            </Button>
            <Link href={`/patients/${patientId}`}>
              <Button variant="secondary">Back</Button>
            </Link>
          </div>
        </div>
      </div>

      <AllergyBanner allergies={patient.allergies || []} />

      <Card>
        <CardHeader><CardTitle>Subjective</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <input className="w-full rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="Chief complaint" value={encounter.chief_complaint || ""} onChange={(e) => setEncounterField("chief_complaint", e.target.value)} />
          <textarea className="w-full rounded border border-slate-300 dark:border-slate-700 px-3 py-2" rows={4} placeholder="HPI (OLDCARTS)" value={encounter.hpi || ""} onChange={(e) => setEncounterField("hpi", e.target.value)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Objective</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-3 text-sm">
            <div><p>BP</p><Sparkline data={last5Vitals.bp} /></div>
            <div><p>Pulse</p><Sparkline data={last5Vitals.pulse} /></div>
            <div><p>Temp</p><Sparkline data={last5Vitals.temp} /></div>
          </div>
          <textarea className="w-full rounded border border-slate-300 dark:border-slate-700 px-3 py-2" rows={4} placeholder="Examination findings" value={encounter.examination_findings || ""} onChange={(e) => setEncounterField("examination_findings", e.target.value)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Assessment</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <input className="w-full rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="Search ICD-10 (2+ chars)" value={icdQuery} onChange={(e) => setIcdQuery(e.target.value)} />
          {icdSuggestions.length > 0 && (
            <div className="rounded border border-slate-200 dark:border-slate-800 p-2">
              {icdSuggestions.slice(0, 8).map((s) => (
                <button key={`${s.code}-${s.description}`} type="button" className="block w-full rounded px-2 py-1 text-left hover:bg-slate-50 dark:bg-slate-900" onClick={() => { setDiagnosisCode(s.code); setDiagnosisDesc(s.description); }}>
                  <span className="font-mono">{s.code}</span> - {s.description}
                </button>
              ))}
            </div>
          )}
          <div className="grid gap-2 md:grid-cols-3">
            <input className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="ICD-10 code" value={diagnosisCode} onChange={(e) => setDiagnosisCode(e.target.value)} />
            <input className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="Description" value={diagnosisDesc} onChange={(e) => setDiagnosisDesc(e.target.value)} />
            <select className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" value={diagnosisSeverity} onChange={(e) => setDiagnosisSeverity(e.target.value)}>
              <option value="mild">mild</option><option value="moderate">moderate</option><option value="severe">severe</option><option value="critical">critical</option>
            </select>
          </div>
          <Button onClick={addDiagnosis}>Add diagnosis</Button>
          <textarea className="w-full rounded border border-slate-300 dark:border-slate-700 px-3 py-2" rows={3} placeholder="Assessment plan" value={encounter.assessment_plan || ""} onChange={(e) => setEncounterField("assessment_plan", e.target.value)} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle>Plan — Prescription</CardTitle></CardHeader>
        <CardContent className="space-y-3">
          <input className={`w-full rounded border px-3 py-2 ${drugSuggestions.some((d) => d.name === drugName && d.allergy_flag) ? "border-[#DC2626]" : "border-slate-300 dark:border-slate-700"}`} placeholder="Drug name" value={drugName} onChange={(e) => setDrugName(e.target.value)} />
          {drugSuggestions.length > 0 && (
            <div className="rounded border border-slate-200 dark:border-slate-800 p-2">
              {drugSuggestions.slice(0, 8).map((d) => (
                <button key={d.name} type="button" className="flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-slate-50 dark:bg-slate-900" onClick={() => setDrugName(d.name)}>
                  <span>{d.name}</span>
                  {d.allergy_flag ? <span className="rounded bg-[#FEE2E2] px-2 py-0.5 text-xs text-[#B91C1C]">Allergy</span> : null}
                </button>
              ))}
            </div>
          )}
          <div className="grid gap-2 md:grid-cols-4">
            <input className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="Dosage" value={dosage} onChange={(e) => setDosage(e.target.value)} />
            <input className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="Frequency" value={frequency} onChange={(e) => setFrequency(e.target.value)} />
            <input className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" placeholder="Duration days" value={durationDays} onChange={(e) => setDurationDays(e.target.value)} />
            <select className="rounded border border-slate-300 dark:border-slate-700 px-3 py-2" value={route} onChange={(e) => setRoute(e.target.value)}>
              <option value="oral">oral</option><option value="iv">iv</option><option value="im">im</option><option value="topical">topical</option><option value="inhalation">inhalation</option>
            </select>
          </div>
          <Button onClick={() => savePrescription(false)}>Save prescription</Button>
        </CardContent>
      </Card>

      <AllergyConflictModal
        open={!!allergyConflict}
        onOpenChange={() => {}}
        conflict={allergyConflict}
        drugName={drugName}
        dosage={dosage}
        overrideReason={overrideReason}
        onOverrideReasonChange={setOverrideReason}
        onConfirm={() => savePrescription(true)}
        onCancel={() => {
          setAllergyConflict(null);
          setOverrideReason("");
        }}
        loading={false}
      />

      <ConfirmDialog
        open={closeOpen}
        onOpenChange={setCloseOpen}
        title="Close encounter"
        message={`You have added:\n· ${diagnoses.length} diagnoses\n· ${prescriptions.length} prescriptions\n· ${labs.length} lab orders\nMark encounter as complete?`}
        confirmLabel="Confirm"
        onConfirm={async () => {
          await api.post(`/patients/${patientId}/encounters/${encounterId}/close`, {
            confirmation_items: [
              `diagnoses:${diagnoses.length}`,
              `prescriptions:${prescriptions.length}`,
              `labs:${labs.length}`,
            ],
          });
          router.push(`/patients/${patientId}`);
        }}
      />

      {aiOpen && (
        <div className="fixed inset-y-0 right-0 z-50 w-full max-w-md overflow-y-auto border-l border-slate-200 dark:border-slate-800 bg-white p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="font-semibold">AI Analysis</h3>
            <Button variant="secondary" size="sm" onClick={() => setAiOpen(false)}>Close</Button>
          </div>
          <p className="mb-2 text-sm">Triage: <strong>{aiResult?.triage_assessment?.triage_level || "N/A"}</strong></p>
          <div className="space-y-2">
            {(aiResult?.diagnosis_suggestions?.suggestions || []).slice(0, 10).map((s, idx) => (
              <div key={`${s.icd10_code || s.diagnosis}-${idx}`} className="rounded border border-slate-200 dark:border-slate-800 p-2 text-sm">
                <p className="font-medium">{idx + 1}. {s.diagnosis}</p>
                <p className="text-xs text-slate-500 dark:text-slate-500">{s.icd10_code || "No code"} · {Math.round((s.probability || 0) * 100)}%</p>
                <Button
                  size="sm"
                  variant="secondary"
                  className="mt-2"
                  onClick={() => {
                    setDiagnosisCode(s.icd10_code || "");
                    setDiagnosisDesc(s.diagnosis || "");
                  }}
                >
                  Apply to form
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

