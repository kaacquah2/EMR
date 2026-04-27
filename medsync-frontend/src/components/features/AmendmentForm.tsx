"use client";

import React, { useState } from "react";
import { useApi } from "@/hooks/use-api";
import type { MedicalRecord } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

interface AmendmentFormProps {
  record: MedicalRecord;
  onSuccess?: () => void;
  onClose?: () => void;
}

export function AmendmentForm({ record, onSuccess, onClose }: AmendmentFormProps) {
  const api = useApi();
  const [reason, setReason] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  // UX-26: confirmation step
  const [confirmOpen, setConfirmOpen] = useState(false);

  const [form, setForm] = useState({
    icd10_code: record.diagnosis?.icd10_code ?? "",
    icd10_description: record.diagnosis?.icd10_description ?? "",
    severity: record.diagnosis?.severity ?? "moderate",
    onset_date: record.diagnosis?.onset_date ?? "",
    notes: record.diagnosis?.notes ?? "",
    is_chronic: record.diagnosis?.is_chronic ?? false,
    drug_name: record.prescription?.drug_name ?? "",
    dosage: record.prescription?.dosage ?? "",
    frequency: record.prescription?.frequency ?? "",
    duration_days: record.prescription?.duration_days != null ? String(record.prescription.duration_days) : "",
    route: record.prescription?.route ?? "oral",
    content: "",
    temperature_c: record.vital?.temperature_c != null ? String(record.vital.temperature_c) : "",
    pulse_bpm: record.vital?.pulse_bpm != null ? String(record.vital.pulse_bpm) : "",
    resp_rate: record.vital?.resp_rate != null ? String(record.vital.resp_rate) : "",
    bp_systolic: record.vital?.bp_systolic != null ? String(record.vital.bp_systolic) : "",
    bp_diastolic: record.vital?.bp_diastolic != null ? String(record.vital.bp_diastolic) : "",
    spo2_percent: record.vital?.spo2_percent != null ? String(record.vital.spo2_percent) : "",
    weight_kg: record.vital?.weight_kg != null ? String(record.vital.weight_kg) : "",
    height_cm: record.vital?.height_cm != null ? String(record.vital.height_cm) : "",
    test_name: record.lab_result?.test_name ?? "",
    result_value: record.lab_result?.result_value ?? "",
  });

  const MIN_REASON_CHARS = 20;

  const submit = async () => {
    setError("");
    if (!reason.trim()) {
      setError("Amendment reason is required.");
      return;
    }
    if (reason.trim().length < MIN_REASON_CHARS) {
      setError(`Amendment reason must be at least ${MIN_REASON_CHARS} characters.`);
      return;
    }
    setLoading(true);
    try {
      const body: Record<string, unknown> = { amendment_reason: reason.trim() };
      const t = record.record_type;
      if (t === "diagnosis" && record.diagnosis) {
        body.icd10_code = form.icd10_code || record.diagnosis.icd10_code;
        body.icd10_description = form.icd10_description || record.diagnosis.icd10_description;
        body.severity = form.severity || record.diagnosis.severity;
        body.onset_date = form.onset_date || record.diagnosis.onset_date;
        body.notes = form.notes;
        body.is_chronic = form.is_chronic;
      } else if (t === "prescription" && record.prescription) {
        body.drug_name = form.drug_name || record.prescription.drug_name;
        body.dosage = form.dosage || record.prescription.dosage;
        body.frequency = form.frequency || record.prescription.frequency;
        body.duration_days = form.duration_days ? parseInt(form.duration_days, 10) : record.prescription.duration_days;
        body.route = form.route || record.prescription.route;
        body.notes = form.notes;
      } else if (t === "vital_signs" && record.vital) {
        if (form.temperature_c !== "") body.temperature_c = parseFloat(form.temperature_c);
        if (form.pulse_bpm !== "") body.pulse_bpm = parseInt(form.pulse_bpm, 10);
        if (form.resp_rate !== "") body.resp_rate = parseInt(form.resp_rate, 10);
        if (form.bp_systolic !== "") body.bp_systolic = parseInt(form.bp_systolic, 10);
        if (form.bp_diastolic !== "") body.bp_diastolic = parseInt(form.bp_diastolic, 10);
        if (form.spo2_percent !== "") body.spo2_percent = parseFloat(form.spo2_percent);
        if (form.weight_kg !== "") body.weight_kg = parseFloat(form.weight_kg);
        if (form.height_cm !== "") body.height_cm = parseFloat(form.height_cm);
      } else if (t === "nursing_note") {
        body.content = form.content;
      } else if (t === "lab_result" && record.lab_result) {
        body.test_name = form.test_name || record.lab_result.test_name;
        body.result_value = form.result_value;
      }
      await api.post(`/records/${record.record_id}/amend`, body);
      onSuccess?.();
      onClose?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Amendment failed");
    } finally {
      setLoading(false);
    }
  };

  const t = record.record_type;
  return (
    <div className="space-y-4">
      <p className="text-sm text-[#64748B]">
        Create an amendment for this {t.replace("_", " ")} record. The original will be marked as amended and a new record will be created.
      </p>
      <Textarea
        label="Amendment reason (required, min 20 characters)"
        value={reason}
        onChange={(e) => setReason(e.target.value)}
        placeholder="Describe why this record needs correction (min 20 characters)"
        maxLength={500}
        showCount
        error={reason.trim().length > 0 && reason.trim().length < MIN_REASON_CHARS ? `${MIN_REASON_CHARS - reason.trim().length} more characters required.` : undefined}
      />

      {t === "diagnosis" && record.diagnosis && (
        <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
          <p className="text-xs font-semibold text-[#64748B]">Corrected data (optional)</p>
          <Input label="ICD-10 Code" value={form.icd10_code} onChange={(e) => setForm((f) => ({ ...f, icd10_code: e.target.value }))} />
          <Input label="Description" value={form.icd10_description} onChange={(e) => setForm((f) => ({ ...f, icd10_description: e.target.value }))} />
          <Select
            label="Severity"
            value={form.severity}
            onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value as typeof form.severity }))}
          >
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
            <option value="critical">Critical</option>
          </Select>
          <Input label="Onset date" type="date" value={form.onset_date} onChange={(e) => setForm((f) => ({ ...f, onset_date: e.target.value }))} />
          <div className="flex items-center gap-2">
            <input type="checkbox" checked={form.is_chronic} onChange={(e) => setForm((f) => ({ ...f, is_chronic: e.target.checked }))} />
            <label className="text-sm">Chronic</label>
          </div>
          <Input label="Notes" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
        </div>
      )}

      {t === "prescription" && record.prescription && (
        <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
          <p className="text-xs font-semibold text-[#64748B]">Corrected data (optional)</p>
          <Input label="Drug name" value={form.drug_name} onChange={(e) => setForm((f) => ({ ...f, drug_name: e.target.value }))} />
          <Input label="Dosage" value={form.dosage} onChange={(e) => setForm((f) => ({ ...f, dosage: e.target.value }))} />
          <Input label="Frequency" value={form.frequency} onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value }))} />
          <Input label="Duration (days)" type="number" value={form.duration_days} onChange={(e) => setForm((f) => ({ ...f, duration_days: e.target.value }))} />
          <Select
            label="Route"
            value={form.route}
            onChange={(e) => setForm((f) => ({ ...f, route: e.target.value }))}
          >
            <option value="oral">Oral</option>
            <option value="iv">IV</option>
            <option value="im">IM</option>
            <option value="topical">Topical</option>
            <option value="inhalation">Inhalation</option>
            <option value="other">Other</option>
          </Select>
          <Input label="Notes" value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} />
        </div>
      )}

      {t === "vital_signs" && record.vital && (
        <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
          <p className="text-xs font-semibold text-[#64748B]">Corrected data (optional)</p>
          <Input label="Temperature (C)" type="number" step="0.1" value={form.temperature_c} onChange={(e) => setForm((f) => ({ ...f, temperature_c: e.target.value }))} />
          <Input label="Pulse (bpm)" type="number" value={form.pulse_bpm} onChange={(e) => setForm((f) => ({ ...f, pulse_bpm: e.target.value }))} />
          <Input label="Respiratory rate" type="number" value={form.resp_rate} onChange={(e) => setForm((f) => ({ ...f, resp_rate: e.target.value }))} />
          <Input label="BP Systolic" type="number" value={form.bp_systolic} onChange={(e) => setForm((f) => ({ ...f, bp_systolic: e.target.value }))} />
          <Input label="BP Diastolic" type="number" value={form.bp_diastolic} onChange={(e) => setForm((f) => ({ ...f, bp_diastolic: e.target.value }))} />
          <Input label="SpO2 (%)" type="number" value={form.spo2_percent} onChange={(e) => setForm((f) => ({ ...f, spo2_percent: e.target.value }))} />
          <Input label="Weight (kg)" type="number" step="0.1" value={form.weight_kg} onChange={(e) => setForm((f) => ({ ...f, weight_kg: e.target.value }))} />
          <Input label="Height (cm)" type="number" step="0.1" value={form.height_cm} onChange={(e) => setForm((f) => ({ ...f, height_cm: e.target.value }))} />
        </div>
      )}

      {t === "nursing_note" && (
        <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
          <Textarea
            label="Corrected content"
            value={form.content}
            onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
            placeholder="Revised note content"
            maxLength={1000}
            showCount
          />
        </div>
      )}

      {t === "lab_result" && record.lab_result && (
        <div className="space-y-3 border-t border-[#E2E8F0] pt-4">
          <p className="text-xs font-semibold text-[#64748B]">Corrected data (optional)</p>
          <Input label="Test name" value={form.test_name} onChange={(e) => setForm((f) => ({ ...f, test_name: e.target.value }))} />
          <Input label="Result value" value={form.result_value} onChange={(e) => setForm((f) => ({ ...f, result_value: e.target.value }))} />
        </div>
      )}

      {error && <p className="text-sm text-[var(--red-600)]" role="alert">{error}</p>}

      {/* UX-26: ConfirmDialog before amending */}
      {confirmOpen && (
        <div className="rounded-lg border border-[var(--amber-600)]/40 bg-[#FFFBEB] p-4">
          <p className="text-sm font-semibold text-[var(--amber-600)]">⚠ Confirm amendment</p>
          <p className="mt-1 text-sm text-[var(--gray-700)]">
            You are about to permanently amend this <strong>{t.replace("_", " ")}</strong> record.
            This action is <strong>audit-logged and cannot be undone</strong>.
          </p>
          <div className="mt-3 flex gap-2">
            <Button type="button" variant="secondary" onClick={() => setConfirmOpen(false)} disabled={loading}>Cancel</Button>
            <Button type="button" variant="danger" loading={loading} onClick={submit}>
              Yes, create amendment
            </Button>
          </div>
        </div>
      )}

      {!confirmOpen && (
        <div className="flex gap-2 justify-end pt-2">
          <Button type="button" variant="secondary" onClick={onClose} disabled={loading}>Cancel</Button>
          <Button type="button" disabled={!reason.trim() || loading}
            onClick={() => setConfirmOpen(true)}>
            Review &amp; confirm →
          </Button>
        </div>
      )}
    </div>
  );
}
