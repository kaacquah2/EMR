"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { usePatient } from "@/hooks/use-patients";
import { useCreateEncounter } from "@/hooks/use-encounters";
import { useDepartments, useDoctors } from "@/hooks/use-admin";
import { useEncounterAutoSave } from "@/hooks/use-encounter-auto-save";
import { AutoSaveIndicator } from "@/components/features/encounter/auto-save-indicator";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Loader2, LayoutTemplate, X } from "lucide-react";

const ENCOUNTER_TYPES = [
  { value: "outpatient", label: "Outpatient" },
  { value: "inpatient", label: "Inpatient" },
  { value: "emergency", label: "Emergency" },
  { value: "follow_up", label: "Follow-up" },
  { value: "consultation", label: "Consultation" },
  { value: "other", label: "Other" },
];

const ENCOUNTER_STATUS = [
  { value: "waiting", label: "Waiting" },
  { value: "in_consultation", label: "In consultation" },
  { value: "completed", label: "Completed" },
];

interface EncounterTemplate {
  id: string;
  name: string;
  description: string;
  template_type: string;
  specialty: string;
  encounter_type: string;
  usage_count: number;
  created_by: string;
  chief_complaint_template?: string;
  hpi_template?: string;
  examination_template?: string;
  assessment_template?: string;
}

function TemplatePickerModal({
  onClose,
  onApply,
}: {
  onClose: () => void;
  onApply: (t: EncounterTemplate) => void;
}) {
  const api = useApi();
  const toast = useToast();
  const [templates, setTemplates] = useState<EncounterTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<EncounterTemplate | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  useEffect(() => {
    api
      .get<{ data: EncounterTemplate[] }>("/encounter-templates")
      .then((r) => setTemplates(r.data ?? []))
      .catch(() => toast.error("Failed to load templates"))
      .finally(() => setLoading(false));
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSelect = async (t: EncounterTemplate) => {
    setLoadingDetail(true);
    try {
      const detail = await api.get<EncounterTemplate>(`/encounter-templates/${t.id}`);
      setSelected(detail);
    } catch {
      toast.error("Failed to load template details");
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-2xl bg-white dark:bg-slate-900 rounded-xl shadow-2xl border border-slate-200 dark:border-slate-800 flex flex-col max-h-[85vh]">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-100 dark:border-slate-800">
          <div className="flex items-center gap-2">
            <LayoutTemplate className="h-5 w-5 text-[#6366F1]" />
            <h3 className="text-lg font-bold text-slate-900 dark:text-slate-100">Select Encounter Template</h3>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-300">
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="flex flex-1 overflow-hidden">
          {/* Template list */}
          <div className="w-1/2 border-r border-slate-100 dark:border-slate-800 overflow-y-auto">
            {loading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              </div>
            ) : templates.length === 0 ? (
              <div className="p-6 text-sm text-slate-400 text-center">
                No templates found. Create one after saving an encounter.
              </div>
            ) : (
              <ul className="divide-y divide-slate-100 dark:divide-slate-800">
                {templates.map((t) => (
                  <li key={t.id}>
                    <button
                      onClick={() => void handleSelect(t)}
                      className={`w-full px-4 py-3 text-left hover:bg-slate-50 dark:hover:bg-slate-800/50 transition-colors ${
                        selected?.id === t.id ? "bg-[#6366F1]/5 border-l-2 border-[#6366F1]" : ""
                      }`}
                    >
                      <p className="font-medium text-sm text-slate-900 dark:text-slate-100">{t.name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">
                        {t.template_type} · {t.encounter_type || "any type"} · used {t.usage_count}×
                      </p>
                      {t.description && (
                        <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{t.description}</p>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Template preview */}
          <div className="w-1/2 overflow-y-auto p-4">
            {loadingDetail ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-slate-400" />
              </div>
            ) : selected ? (
              <div className="space-y-3 text-sm">
                <h4 className="font-semibold text-slate-900 dark:text-slate-100">{selected.name}</h4>
                {selected.chief_complaint_template && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Chief Complaint</p>
                    <p className="text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{selected.chief_complaint_template}</p>
                  </div>
                )}
                {selected.hpi_template && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">HPI</p>
                    <p className="text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{selected.hpi_template}</p>
                  </div>
                )}
                {selected.examination_template && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Examination</p>
                    <p className="text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{selected.examination_template}</p>
                  </div>
                )}
                {selected.assessment_template && (
                  <div>
                    <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1">Assessment & Plan</p>
                    <p className="text-slate-700 dark:text-slate-300 whitespace-pre-wrap">{selected.assessment_template}</p>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-slate-400 text-center py-8">Select a template to preview</p>
            )}
          </div>
        </div>

        <div className="flex justify-end gap-2 px-6 py-4 border-t border-slate-100 dark:border-slate-800">
          <Button variant="secondary" size="sm" onClick={onClose}>Cancel</Button>
          <Button
            size="sm"
            className="bg-[#6366F1] hover:bg-[#4F46E5] text-white"
            disabled={!selected}
            onClick={() => selected && onApply(selected)}
          >
            Apply Template
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function NewEncounterPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { user } = useAuth();
  const { patient, loading: patientLoading, error: patientError } = usePatient(id);
  const { create, loading: submitting } = useCreateEncounter(id);
  
  // Auto-save hook
  const { updateDraft, isSaving, getFormattedLastSavedTime, error: autoSaveError } =
    useEncounterAutoSave(id);

  const [encounterType, setEncounterType] = useState("outpatient");
  const [notes, setNotes] = useState("");
  const [chiefComplaint, setChiefComplaint] = useState("");
  const [hpi, setHpi] = useState("");
  const [examFindings, setExamFindings] = useState("");
  const [assessmentPlan, setAssessmentPlan] = useState("");
  const [assignedDepartmentId, setAssignedDepartmentId] = useState("");
  const [assignedDoctorId, setAssignedDoctorId] = useState("");
  const [status, setStatus] = useState<"waiting" | "in_consultation" | "completed">("waiting");
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [showTemplatePicker, setShowTemplatePicker] = useState(false);
  const [savingTemplate, setSavingTemplate] = useState(false);
  const api = useApi();
  const toast = useToast();

  const saveAsTemplate = useCallback(async () => {
    const name = window.prompt("Template name (e.g. 'Hypertension Follow-up'):");
    if (!name?.trim()) return;
    setSavingTemplate(true);
    try {
      await api.post("/encounter-templates", {
        name: name.trim(),
        template_type: "personal",
        encounter_type: encounterType,
        chief_complaint_template: chiefComplaint,
        hpi_template: hpi,
        examination_template: examFindings,
        assessment_template: assessmentPlan,
      });
      toast.success("Template saved");
    } catch {
      toast.error("Failed to save template");
    } finally {
      setSavingTemplate(false);
    }
  }, [api, encounterType, chiefComplaint, hpi, examFindings, assessmentPlan, toast]);

  const applyTemplate = useCallback((t: EncounterTemplate) => {
    if (t.chief_complaint_template) setChiefComplaint(t.chief_complaint_template);
    if (t.hpi_template) setHpi(t.hpi_template);
    if (t.examination_template) setExamFindings(t.examination_template);
    if (t.assessment_template) setAssessmentPlan(t.assessment_template);
    if (t.encounter_type) setEncounterType(t.encounter_type);
    setHasUnsavedChanges(true);
    setShowTemplatePicker(false);
  }, []);

  const { departments, fetch: fetchDepartments } = useDepartments();
  const { doctors, fetch: fetchDoctors } = useDoctors(assignedDepartmentId || undefined);

  const canAdd = user?.role === "doctor" || user?.role === "nurse" || user?.role === "hospital_admin" || user?.role === "super_admin";

  useEffect(() => {
    if (!canAdd && user) {
      router.replace("/unauthorized");
    }
  }, [canAdd, user, router]);

  useEffect(() => {
    if (canAdd) {
      fetchDepartments();
    }
  }, [canAdd, fetchDepartments]);

  useEffect(() => {
    if (canAdd) fetchDoctors();
  }, [canAdd, fetchDoctors, assignedDepartmentId]);

  // Trigger auto-save on SOAP field changes
  useEffect(() => {
    const timer = setTimeout(() => {
      updateDraft({
        patient_id: id,
        soap: {
          subjective: chiefComplaint || hpi ? `Chief complaint: ${chiefComplaint}\nHPI: ${hpi}` : "",
          objective: examFindings,
          assessment: assessmentPlan,
          plan: notes,
        },
      });
      setHasUnsavedChanges(false);
    }, 500);

    return () => clearTimeout(timer);
  }, [chiefComplaint, hpi, examFindings, assessmentPlan, notes, updateDraft, id]);

  // Track form changes
  const handleFieldChange = () => {
    setHasUnsavedChanges(true);
  };

  // Warn before leaving with unsaved changes
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsavedChanges) {
        e.preventDefault();
        e.returnValue = "";
      }
    };

    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => window.removeEventListener("beforeunload", handleBeforeUnload);
  }, [hasUnsavedChanges]);

  if (patientLoading || !patient) {
    return (
      <div className="flex items-center justify-center py-12">
        <p className="text-slate-500 dark:text-slate-500">{patientError || "Loading..."}</p>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await create({
        encounter_type: encounterType,
        notes: notes.trim() || undefined,
        chief_complaint: chiefComplaint.trim() || undefined,
        hpi: hpi.trim() || undefined,
        examination_findings: examFindings.trim() || undefined,
        assessment_plan: assessmentPlan.trim() || undefined,
        assigned_department_id: assignedDepartmentId || undefined,
        assigned_doctor_id: assignedDoctorId || undefined,
        status,
      });
      setHasUnsavedChanges(false);
      router.push(`/patients/${id}`);
    } catch {
      //
    }
  };

  const lastSavedTime = getFormattedLastSavedTime();

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <Breadcrumbs
        items={[
          { label: "Patients", href: "/patients/search" },
          { label: patient.full_name ?? "Patient", href: `/patients/${id}` },
          { label: "New encounter" },
        ]}
      />
      <div>
        <Link href={`/patients/${id}`} className="text-sm text-[#0EAFBE] hover:underline">
          Back to patient
        </Link>
        <h1 className="mt-2 font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Add Encounter</h1>
        <p className="text-slate-500 dark:text-slate-500">
          Patient: {patient.full_name} ({patient.ghana_health_id})
        </p>
        {lastSavedTime && (
          <p className="mt-1 text-xs text-green-600">✓ Auto-saved at {lastSavedTime}</p>
        )}
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>Encounter details</CardTitle>
          {user?.role === "doctor" && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setShowTemplatePicker(true)}
              className="flex items-center gap-1.5 shrink-0"
            >
              <LayoutTemplate className="h-4 w-4" />
              Use Template
            </Button>
          )}
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Encounter type</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                value={encounterType}
                onChange={(e) => {
                  setEncounterType(e.target.value);
                  handleFieldChange();
                }}
              >
                {ENCOUNTER_TYPES.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Department (routing)</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                value={assignedDepartmentId}
                onChange={(e) => {
                  setAssignedDepartmentId(e.target.value);
                  setAssignedDoctorId("");
                  handleFieldChange();
                }}
              >
                <option value="">Select department</option>
                {departments.map((d) => (
                  <option key={d.department_id} value={d.department_id}>{d.name}</option>
                ))}
              </select>
              <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">Route patient to this department for consultation.</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Assigned doctor (optional)</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                value={assignedDoctorId}
                onChange={(e) => {
                  setAssignedDoctorId(e.target.value);
                  handleFieldChange();
                }}
              >
                <option value="">Any doctor in department</option>
                {doctors.map((d) => (
                  <option key={d.user_id} value={d.user_id}>{d.full_name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Status</label>
              <select
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value as "waiting" | "in_consultation" | "completed");
                  handleFieldChange();
                }}
              >
                {ENCOUNTER_STATUS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Subjective: Chief complaint</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                rows={2}
                value={chiefComplaint}
                onChange={(e) => {
                   setChiefComplaint(e.target.value);
                   handleFieldChange();
                 }}
                data-testid="encounter-chief-complaint"
                placeholder="Main complaint in patient words"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Subjective: History of present illness (HPI)</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                rows={3}
                value={hpi}
                onChange={(e) => {
                   setHpi(e.target.value);
                   handleFieldChange();
                 }}
                data-testid="encounter-hpi"
                placeholder="Duration, progression, associated symptoms"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Objective: Examination findings</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                rows={3}
                value={examFindings}
                onChange={(e) => {
                   setExamFindings(e.target.value);
                   handleFieldChange();
                 }}
                data-testid="encounter-examination"
                placeholder="Physical exam and objective findings"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Assessment and plan</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                rows={3}
                value={assessmentPlan}
                onChange={(e) => {
                   setAssessmentPlan(e.target.value);
                   handleFieldChange();
                 }}
                data-testid="encounter-assessment"
                placeholder="Differential, treatment plan, follow-up"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-900 dark:text-slate-100">Additional notes</label>
              <textarea
                className="mt-1 w-full rounded-lg border border-slate-200 dark:border-slate-800 bg-white px-3 py-2 text-slate-900 dark:text-slate-100"
                rows={4}
                value={notes}
                onChange={(e) => {
                   setNotes(e.target.value);
                   handleFieldChange();
                 }}
                placeholder="Reason for visit, complaint, etc."
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={submitting}>
                Save encounter
              </Button>
              {user?.role === "doctor" && (
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => void saveAsTemplate()}
                  disabled={savingTemplate}
                  title="Save current SOAP fields as a reusable template"
                >
                  {savingTemplate ? (
                    <><Loader2 className="h-3 w-3 animate-spin mr-1" /> Saving…</>
                  ) : (
                    "Save as Template"
                  )}
                </Button>
              )}
              <Link href={`/patients/${id}`}>
                <Button type="button" variant="secondary">
                  Cancel
                </Button>
              </Link>
            </div>
          </form>
        </CardContent>
      </Card>

      <AutoSaveIndicator
        isSaving={isSaving}
        error={autoSaveError}
        lastSavedAt={lastSavedTime}
      />

      {showTemplatePicker && (
        <TemplatePickerModal
          onClose={() => setShowTemplatePicker(false)}
          onApply={applyTemplate}
        />
      )}
    </div>
  );
}
