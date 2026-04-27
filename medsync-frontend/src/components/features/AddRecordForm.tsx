"use client";

import React, { useMemo, useState, useEffect } from "react";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useLabTestTypes } from "@/hooks/use-admin";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { AllergyConflictModal } from "@/components/features/AllergyConflictModal";
import { useToast } from "@/lib/toast-context";
import { ROLES } from "@/lib/permissions";

// UX-09: Context-aware save button labels
const SAVE_LABELS: Record<string, string> = {
  diagnosis: "Add diagnosis",
  prescription: "Write prescription",
  lab_order: "Order lab test",
  vitals: "Record vitals",
  allergy: "Add allergy",
  nursing_note: "Save note",
};

const ALL_RECORD_TYPES = [
  { id: "diagnosis", label: "Diagnosis" },
  { id: "prescription", label: "Prescription" },
  { id: "lab_order", label: "Lab Order" },
  { id: "vitals", label: "Vitals" },
  { id: "allergy", label: "Allergy" },
  { id: "nursing_note", label: "Nursing Note" },
];

interface AddRecordFormProps {
  patientId: string;
  onSuccess?: () => void;
  onClose?: () => void;
  /** When set (e.g. for nurse quick-add), preselect this type and hide type selector. */
  initialType?: "vital_signs" | "nursing_note" | "allergy" | "diagnosis" | "prescription" | "lab_order";
}

const TYPE_TO_ID: Record<string, string> = {
  vital_signs: "vitals",
  nursing_note: "nursing_note",
  allergy: "allergy",
  diagnosis: "diagnosis",
  prescription: "prescription",
  lab_order: "lab_order",
};

export function AddRecordForm({ patientId, onSuccess, onClose, initialType }: AddRecordFormProps) {
  const { user } = useAuth();
  const { success: toastSuccess } = useToast();
  const api = useApi();
  const { labTestTypes, fetch: fetchLabTestTypes } = useLabTestTypes();
  useEffect(() => {
    if (user?.role === ROLES.DOCTOR || user?.role === ROLES.SUPER_ADMIN) fetchLabTestTypes();
  }, [user?.role, fetchLabTestTypes]);

  // RBAC-07: only expose record types the user's role can actually create
  const recordTypes = useMemo(() => {
    const role = user?.role;
    if (role === ROLES.NURSE) {
      return ALL_RECORD_TYPES.filter((t) =>
        ["vitals", "allergy", "nursing_note"].includes(t.id)
      );
    }
    if (role === ROLES.DOCTOR || role === ROLES.SUPER_ADMIN) {
      return ALL_RECORD_TYPES; // full access
    }
    // All other roles (receptionist, hospital_admin, etc.) cannot write records
    return [];
  }, [user?.role]);
  const [selectedType, setSelectedType] = useState<string | null>(
    initialType ? TYPE_TO_ID[initialType] ?? initialType : null
  );
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [allergyConflict, setAllergyConflict] = useState<{
    allergen: string;
    reaction: string;
    severity: string;
  } | null>(null);
  const [overrideReason, setOverrideReason] = useState("");
  const [icdSuggestions, setIcdSuggestions] = useState<Array<{ code: string; description: string }>>([]);
  const [drugSuggestions, setDrugSuggestions] = useState<Array<{ name: string; allergy_flag?: boolean }>>([]);

  const [form, setForm] = useState({
    icd10_code: "",
    icd10_description: "",
    severity: "moderate",
    onset_date: "",
    notes: "",
    is_chronic: false,
    drug_name: "",
    dosage: "",
    frequency: "",
    duration_days: "",
    route: "oral",
    test_name: "",
    urgency: "routine",
    temperature_c: "",
    pulse_bpm: "",
    resp_rate: "",
    bp_systolic: "",
    bp_diastolic: "",
    spo2_percent: "",
    weight_kg: "",
    height_cm: "",
    allergen: "",
    reaction_type: "",
    content: "",
  });

  useEffect(() => {
    if (selectedType !== "diagnosis" || form.icd10_code.trim().length < 2) {
      setIcdSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await api.get<{ data: Array<{ code: string; description: string }> }>(
          `/records/icd10-autocomplete?q=${encodeURIComponent(form.icd10_code.trim())}`
        );
        setIcdSuggestions(res.data || []);
      } catch {
        setIcdSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [api, selectedType, form.icd10_code]);

  useEffect(() => {
    if (selectedType !== "prescription" || form.drug_name.trim().length < 2) {
      setDrugSuggestions([]);
      return;
    }
    const t = setTimeout(async () => {
      try {
        const res = await api.get<{ data: Array<{ name: string; allergy_flag?: boolean }> }>(
          `/records/drug-autocomplete?q=${encodeURIComponent(form.drug_name.trim())}&patient_id=${encodeURIComponent(patientId)}`
        );
        setDrugSuggestions(res.data || []);
      } catch {
        setDrugSuggestions([]);
      }
    }, 250);
    return () => clearTimeout(t);
  }, [api, selectedType, form.drug_name, patientId]);

  const submit = async () => {
    setError("");
    // Basic client-side validation
    if (selectedType === "vitals") {
      const t = parseFloat(form.temperature_c);
      if (form.temperature_c && (t < 25 || t > 45)) {
        setError("Please enter a valid temperature between 25°C and 45°C");
        return;
      }
      const p = parseInt(form.pulse_bpm, 10);
      if (form.pulse_bpm && (p < 0 || p > 300)) {
        setError("Please enter a valid pulse rate");
        return;
      }
    }

    setLoading(true);
    try {
      if (selectedType === "diagnosis") {
        await api.post("/records/diagnosis", {
          patient_id: patientId,
          icd10_code: form.icd10_code,
          icd10_description: form.icd10_description,
          severity: form.severity,
          onset_date: form.onset_date || undefined,
          notes: form.notes || undefined,
          is_chronic: form.is_chronic,
        });
      } else if (selectedType === "prescription") {
        const body: Record<string, unknown> = {
          patient_id: patientId,
          drug_name: form.drug_name,
          dosage: form.dosage,
          frequency: form.frequency,
          duration_days: form.duration_days ? parseInt(form.duration_days, 10) : undefined,
          route: form.route,
          notes: form.notes || undefined,
        };
        if (allergyConflict) body.override_reason = overrideReason;
        await api.post("/records/prescription", body);
      } else if (selectedType === "lab_order") {
        await api.post("/records/lab-order", {
          patient_id: patientId,
          test_name: form.test_name,
          test_type: form.test_name,
          urgency: form.urgency,
          notes: form.notes || undefined,
        });
      } else if (selectedType === "vitals") {
        await api.post("/records/vitals", {
          patient_id: patientId,
          temperature_c: form.temperature_c ? parseFloat(form.temperature_c) : undefined,
          pulse_bpm: form.pulse_bpm ? parseInt(form.pulse_bpm, 10) : undefined,
          resp_rate: form.resp_rate ? parseInt(form.resp_rate, 10) : undefined,
          bp_systolic: form.bp_systolic ? parseInt(form.bp_systolic, 10) : undefined,
          bp_diastolic: form.bp_diastolic ? parseInt(form.bp_diastolic, 10) : undefined,
          spo2_percent: form.spo2_percent ? parseFloat(form.spo2_percent) : undefined,
          weight_kg: form.weight_kg ? parseFloat(form.weight_kg) : undefined,
          height_cm: form.height_cm ? parseFloat(form.height_cm) : undefined,
        });
      } else if (selectedType === "allergy") {
        await api.post("/records/allergy", {
          patient_id: patientId,
          allergen: form.allergen,
          reaction_type: form.reaction_type,
          severity: form.severity,
          notes: form.notes || undefined,
        });
      } else if (selectedType === "nursing_note") {
        await api.post("/records/nursing-note", {
          patient_id: patientId,
          content: form.content,
        });
      }
      // UX-10: success toast
      toastSuccess(SAVE_LABELS[selectedType ?? ""] ? `${SAVE_LABELS[selectedType!]} saved` : "Record saved");
      onSuccess?.();
      onClose?.();
      setSelectedType(null);
      setForm({
        icd10_code: "",
        icd10_description: "",
        severity: "moderate",
        onset_date: "",
        notes: "",
        is_chronic: false,
        drug_name: "",
        dosage: "",
        frequency: "",
        duration_days: "",
        route: "oral",
        test_name: "",
        urgency: "routine",
        temperature_c: "",
        pulse_bpm: "",
        resp_rate: "",
        bp_systolic: "",
        bp_diastolic: "",
        spo2_percent: "",
        weight_kg: "",
        height_cm: "",
        allergen: "",
        reaction_type: "",
        content: "",
      });
      setAllergyConflict(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to save";
      const statusCode = (err as Error & { statusCode?: number }).statusCode;
      const detail = (err as Error & { detail?: { conflict?: boolean; allergen?: string; reaction?: string; severity?: string } })?.detail;
      const is409 = statusCode === 409 || detail?.conflict;
      if (is409 && detail) {
        setAllergyConflict({
          allergen: String(detail.allergen ?? ""),
          reaction: String(detail.reaction ?? ""),
          severity: String(detail.severity ?? ""),
        });
        setError("");
        return;
      }
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  if (!selectedType) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-[#64748B]">Select record type</p>
        <div className="grid grid-cols-2 gap-2">
          {recordTypes.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setSelectedType(t.id)}
              className="rounded-lg border-2 border-[#CBD5E1] p-4 text-left text-sm font-medium transition-colors hover:border-[#0B8A96] hover:bg-[#F0FDFA]"
            >
              {t.label}
            </button>
          ))}
        </div>
      </div>
    );
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="space-y-4"
    >
      <AllergyConflictModal
        open={!!allergyConflict}
        onOpenChange={() => {}}
        conflict={allergyConflict}
        drugName={selectedType === "prescription" ? form.drug_name : undefined}
        dosage={selectedType === "prescription" ? form.dosage : undefined}
        overrideReason={overrideReason}
        onOverrideReasonChange={setOverrideReason}
        onConfirm={() => submit()}
        onCancel={() => {
          setAllergyConflict(null);
          setOverrideReason("");
        }}
        loading={loading}
      />

      {selectedType === "diagnosis" && (
        <>
          <Input
            label="ICD-10 Code"
            value={form.icd10_code}
            onChange={(e) => setForm((f) => ({ ...f, icd10_code: e.target.value }))}
            placeholder="e.g. J18.9"
            required
          />
          {icdSuggestions.length > 0 && (
            <div className="rounded-lg border border-[#E2E8F0] bg-white p-2 text-sm">
              {icdSuggestions.slice(0, 6).map((s) => (
                <button
                  key={`${s.code}-${s.description}`}
                  type="button"
                  className="block w-full rounded px-2 py-1 text-left hover:bg-[#F8FAFC]"
                  onClick={() => setForm((f) => ({ ...f, icd10_code: s.code, icd10_description: s.description }))}
                >
                  <span className="font-mono">{s.code}</span> - {s.description}
                </button>
              ))}
            </div>
          )}
          <Input
            label="Description"
            value={form.icd10_description}
            onChange={(e) => setForm((f) => ({ ...f, icd10_description: e.target.value }))}
            required
          />
          <Select
            label="Severity"
            value={form.severity}
            onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
          >
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
            <option value="critical">Critical</option>
          </Select>
          <Input
            label="Onset date"
            type="date"
            value={form.onset_date}
            onChange={(e) => setForm((f) => ({ ...f, onset_date: e.target.value }))}
          />
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="chronic"
              checked={form.is_chronic}
              onChange={(e) => setForm((f) => ({ ...f, is_chronic: e.target.checked }))}
            />
            <label htmlFor="chronic">Chronic</label>
          </div>
          <Input
            label="Notes"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          />
        </>
      )}

      {selectedType === "prescription" && (
        <>
          <Input
            label="Drug name"
            value={form.drug_name}
            onChange={(e) => setForm((f) => ({ ...f, drug_name: e.target.value }))}
            required
          />
          {drugSuggestions.length > 0 && (
            <div className="rounded-lg border border-[#E2E8F0] bg-white p-2 text-sm">
              {drugSuggestions.slice(0, 6).map((s) => (
                <button
                  key={s.name}
                  type="button"
                  className="flex w-full items-center justify-between rounded px-2 py-1 text-left hover:bg-[#F8FAFC]"
                  onClick={() => setForm((f) => ({ ...f, drug_name: s.name }))}
                >
                  <span>{s.name}</span>
                  {s.allergy_flag ? (
                    <span className="rounded bg-rose-100 px-2 py-0.5 text-xs font-semibold text-rose-700">Allergy risk</span>
                  ) : null}
                </button>
              ))}
            </div>
          )}
          <Input
            label="Dosage"
            value={form.dosage}
            onChange={(e) => setForm((f) => ({ ...f, dosage: e.target.value }))}
            placeholder="e.g. 500mg"
            required
          />
          <Input
            label="Frequency"
            value={form.frequency}
            onChange={(e) => setForm((f) => ({ ...f, frequency: e.target.value }))}
            placeholder="e.g. Three times daily"
            required
          />
          <Input
            label="Duration (days)"
            type="number"
            value={form.duration_days}
            onChange={(e) => setForm((f) => ({ ...f, duration_days: e.target.value }))}
          />
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
          <Input
            label="Notes"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          />
        </>
      )}

      {selectedType === "lab_order" && (
        <>
          <div>
            {labTestTypes.length > 0 ? (
              <Select
                label="Test type"
                value={form.test_name}
                onChange={(e) => setForm((f) => ({ ...f, test_name: e.target.value }))}
                required
              >
                <option value="">Select test</option>
                {labTestTypes.map((t) => (
                  <option key={`${t.lab_unit_id}-${t.test_name}`} value={t.test_name}>
                    {t.test_name} ({t.lab_unit_name})
                  </option>
                ))}
              </Select>
            ) : (
              <Input
                label="Test name"
                value={form.test_name}
                onChange={(e) => setForm((f) => ({ ...f, test_name: e.target.value }))}
                placeholder="e.g. Full Blood Count"
                required
              />
            )}
            <p className="mt-1 text-xs text-[#64748B]">Order is routed to the correct lab unit.</p>
          </div>
          <Select
            label="Urgency"
            value={form.urgency}
            onChange={(e) => setForm((f) => ({ ...f, urgency: e.target.value }))}
          >
            <option value="routine">Routine</option>
            <option value="urgent">Urgent</option>
            <option value="stat">STAT</option>
          </Select>
          <Input
            label="Notes for lab"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          />
        </>
      )}

      {selectedType === "vitals" && (
        <>
          <Input
            label="Temperature (C)"
            type="number"
            step="0.1"
            value={form.temperature_c}
            onChange={(e) => setForm((f) => ({ ...f, temperature_c: e.target.value }))}
          />
          <Input
            label="Pulse (bpm)"
            type="number"
            value={form.pulse_bpm}
            onChange={(e) => setForm((f) => ({ ...f, pulse_bpm: e.target.value }))}
          />
          <Input
            label="Respiratory rate"
            type="number"
            value={form.resp_rate}
            onChange={(e) => setForm((f) => ({ ...f, resp_rate: e.target.value }))}
          />
          {/* UX-12: BP fields side-by-side */}
          <div>
            <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[var(--gray-500)]">Blood Pressure (mmHg)</label>
            <div className="flex items-center gap-2">
              <Input
                type="number"
                value={form.bp_systolic}
                onChange={(e) => setForm((f) => ({ ...f, bp_systolic: e.target.value }))}
                placeholder="Systolic"
                className="flex-1"
              />
              <span className="font-bold text-[var(--gray-500)]">/</span>
              <Input
                type="number"
                value={form.bp_diastolic}
                onChange={(e) => setForm((f) => ({ ...f, bp_diastolic: e.target.value }))}
                placeholder="Diastolic"
                className="flex-1"
              />
            </div>
          </div>
          <Input
            label="SpO2 (%)"
            type="number"
            value={form.spo2_percent}
            onChange={(e) => setForm((f) => ({ ...f, spo2_percent: e.target.value }))}
          />
          <Input
            label="Weight (kg)"
            type="number"
            step="0.1"
            value={form.weight_kg}
            onChange={(e) => setForm((f) => ({ ...f, weight_kg: e.target.value }))}
          />
          <Input
            label="Height (cm)"
            type="number"
            step="0.1"
            value={form.height_cm}
            onChange={(e) => setForm((f) => ({ ...f, height_cm: e.target.value }))}
          />
        </>
      )}

      {selectedType === "allergy" && (
        <>
          <Input
            label="Allergen"
            value={form.allergen}
            onChange={(e) => setForm((f) => ({ ...f, allergen: e.target.value }))}
            required
          />
          <Input
            label="Reaction type"
            value={form.reaction_type}
            onChange={(e) => setForm((f) => ({ ...f, reaction_type: e.target.value }))}
            placeholder="e.g. Anaphylaxis, Rash"
          />
          <Select
            label="Severity"
            value={form.severity}
            onChange={(e) => setForm((f) => ({ ...f, severity: e.target.value }))}
          >
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
            <option value="life_threatening">Life Threatening</option>
          </Select>
          <Input
            label="Notes"
            value={form.notes}
            onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))}
          />
        </>
      )}

      {selectedType === "nursing_note" && (
        <Textarea
          label="Note content"
          value={form.content}
          onChange={(e) => setForm((f) => ({ ...f, content: e.target.value }))}
          placeholder="Enter clinical note..."
          required
          maxLength={1000}
          showCount
        />
      )}

      {error && <p className="text-sm text-[var(--red-600)]" role="alert">{error}</p>}
      <div className="flex gap-2">
        {!initialType && (
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              // UX-11: unsaved changes guard
              const dirty = Object.values(form).some((v) => (typeof v === "string" ? v.trim() !== "" : false));
              if (dirty && !window.confirm("You have unsaved changes. Discard them?")) return;
              setSelectedType(null);
              setAllergyConflict(null);
            }}
          >
            ← Back
          </Button>
        )}
        <Button type="submit" loading={loading}>
          {SAVE_LABELS[selectedType ?? ""] ?? "Save"}
        </Button>
      </div>
    </form>
  );
}
