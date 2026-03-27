"use client";

import React from "react";
import { useParams, useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useApi } from "@/hooks/use-api";
import { useNurseWorklist } from "@/hooks/use-nurse";

type FormState = {
  temperature_c: string;
  pulse_bpm: string;
  resp_rate: string;
  bp_systolic: string;
  bp_diastolic: string;
  spo2_percent: string;
  weight_kg: string;
  height_cm: string;
};

const initialForm: FormState = {
  temperature_c: "",
  pulse_bpm: "",
  resp_rate: "",
  bp_systolic: "",
  bp_diastolic: "",
  spo2_percent: "",
  weight_kg: "",
  height_cm: "",
};

export default function NewVitalsPage() {
  const params = useParams();
  const patientId = params.id as string;
  const router = useRouter();
  const api = useApi();
  const { data } = useNurseWorklist();
  const [form, setForm] = React.useState<FormState>(initialForm);
  const [batchMode, setBatchMode] = React.useState(false);
  const [batchRows, setBatchRows] = React.useState<Record<string, FormState>>({});
  const [criticalModal, setCriticalModal] = React.useState<{ open: boolean; text: string }>({ open: false, text: "" });

  const inputRefs = React.useRef<Array<HTMLInputElement | null>>([]);
  const orderedKeys: Array<keyof FormState> = ["temperature_c", "pulse_bpm", "resp_rate", "bp_systolic", "bp_diastolic", "spo2_percent", "weight_kg", "height_cm"];
  const update = (k: keyof FormState, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const bmi = form.weight_kg && form.height_cm ? (Number(form.weight_kg) / ((Number(form.height_cm) / 100) ** 2)).toFixed(1) : "";

  const nextFocus = (idx: number) => {
    const next = inputRefs.current[idx + 1];
    if (next) next.focus();
  };

  const saveSingle = async () => {
    const spo2 = Number(form.spo2_percent || 0);
    const isCritical = (spo2 > 0 && spo2 < 88) || Number(form.bp_systolic || 0) > 180 || Number(form.bp_systolic || 0) < 90;
    await api.post("/records/vitals", {
      patient_id: patientId,
      ...Object.fromEntries(orderedKeys.map((k) => [k, form[k] ? Number(form[k]) : undefined])),
      critical_action_confirmed: !isCritical,
    });
    if (isCritical) {
      setCriticalModal({ open: true, text: `CRITICAL VALUE — SpO2 ${form.spo2_percent || "N/A"}%` });
      return;
    }
    router.push(`/patients/${patientId}`);
  };

  const confirmCritical = async () => {
    await api.post("/records/vitals", {
      patient_id: patientId,
      ...Object.fromEntries(orderedKeys.map((k) => [k, form[k] ? Number(form[k]) : undefined])),
      critical_action_confirmed: true,
    });
    setCriticalModal({ open: false, text: "" });
    router.push(`/patients/${patientId}`);
  };

  const saveBatch = async () => {
    const payload = Object.entries(batchRows).map(([pid, row]) => ({
      patient_id: pid,
      ...Object.fromEntries(orderedKeys.map((k) => [k, row[k] ? Number(row[k]) : undefined])),
    }));
    await api.post("/records/vitals/batch", payload);
    router.push("/worklist");
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">Record Vitals</h1>
        <Button variant="secondary" onClick={() => setBatchMode((v) => !v)}>
          {batchMode ? "Single patient mode" : "Record vitals for multiple patients"}
        </Button>
      </div>

      {!batchMode ? (
        <Card>
          <CardHeader><CardTitle>Vitals Entry</CardTitle></CardHeader>
          <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-2">
            {orderedKeys.map((key, idx) => (
              <input
                key={key}
                ref={(el) => { inputRefs.current[idx] = el; }}
                className="min-h-[44px] rounded border border-[#CBD5E1] px-3 text-sm"
                placeholder={key}
                value={form[key]}
                onChange={(e) => update(key, e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); nextFocus(idx); } }}
              />
            ))}
            <div className="text-sm text-[#64748B]">BMI: {bmi || "—"}</div>
            <div className="md:col-span-2">
              <Button onClick={() => void saveSingle()}>Save Vitals</Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader><CardTitle>Batch Vitals</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {(data?.beds ?? []).filter((b) => !!b.patient_id).map((bed) => {
              const pid = bed.patient_id as string;
              const row = batchRows[pid] || initialForm;
              return (
                <div key={pid} className="rounded border border-[#E2E8F0] p-2">
                  <p className="mb-2 text-sm font-medium">{bed.patient_name} · {bed.bed_code}</p>
                  <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
                    {orderedKeys.map((k) => (
                      <input
                        key={k}
                        className="min-h-[44px] rounded border border-[#CBD5E1] px-2 text-xs"
                        placeholder={k}
                        value={row[k]}
                        onChange={(e) => setBatchRows((prev) => ({ ...prev, [pid]: { ...(prev[pid] || initialForm), [k]: e.target.value } }))}
                      />
                    ))}
                  </div>
                </div>
              );
            })}
            <Button onClick={() => void saveBatch()}>Save all</Button>
          </CardContent>
        </Card>
      )}

      {criticalModal.open ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-6">
          <div className="w-full max-w-xl rounded bg-white p-6">
            <p className="text-xl font-bold text-red-700">{criticalModal.text}</p>
            <p className="mt-2 text-sm text-[#475569]">Notify doctor immediately.</p>
            <Button className="mt-4" onClick={() => void confirmCritical()}>
              I have notified the doctor — confirm action taken
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
