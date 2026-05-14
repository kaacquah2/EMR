"use client";

import React, { useState, useEffect } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { usePatient } from "@/hooks/use-patients";
import { useCreateEncounter } from "@/hooks/use-encounters";
import { useDepartments, useDoctors } from "@/hooks/use-admin";
import { useEncounterAutoSave } from "@/hooks/use-encounter-auto-save";
import { AutoSaveIndicator } from "@/components/features/encounter/auto-save-indicator";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";

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
        <CardHeader>
          <CardTitle>Encounter details</CardTitle>
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
            <div className="flex gap-2">
              <Button type="submit" disabled={submitting}>
                Save encounter
              </Button>
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
    </div>
  );
}
