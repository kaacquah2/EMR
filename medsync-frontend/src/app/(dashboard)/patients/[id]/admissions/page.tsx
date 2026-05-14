"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useWards, useBedsByWard } from "@/hooks/use-admin";
import { useAdmissions } from "@/hooks/use-admissions";
import { usePatient } from "@/hooks/use-patients";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export default function AdmissionsPage() {
  const params = useParams();
  useRouter();
  const { user } = useAuth();
  const api = useApi();
  const patientId = params.id as string;
  const [wardId, setWardId] = useState("");
  const [bedId, setBedId] = useState("");
  const [notes, setNotes] = useState("");
  const { patient } = usePatient(patientId);
  const { wards, fetch: fetchWards } = useWards();
  const { beds, fetch: fetchBeds } = useBedsByWard(wardId || null);
  const { admissions, fetch: fetchAdmissions } = useAdmissions();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [dischargeConfirmOpen, setDischargeConfirmOpen] = useState(false);

  const canManage = user?.role === "doctor" || user?.role === "hospital_admin" || user?.role === "super_admin";

  useEffect(() => {
    fetchWards();
    fetchAdmissions();
  }, [fetchWards, fetchAdmissions]);
  useEffect(() => {
    setBedId("");
    if (wardId) fetchBeds();
  }, [wardId, fetchBeds]);

  const patientAdmission = admissions.find((a) => a.patient_id === patientId);

  if (!canManage) {
    return (
      <div className="rounded-lg bg-[#FEF3C7] p-4 text-[#B45309]">
        You do not have permission to manage admissions.
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Breadcrumbs
        items={[
          { label: "Patients", href: "/patients/search" },
          { label: patient?.full_name ?? "Patient", href: `/patients/${patientId}` },
          { label: "Admissions" },
        ]}
      />
      <div className="flex items-center gap-4">
        <Link href={`/patients/${patientId}`}>
          <Button variant="ghost">Back</Button>
        </Link>
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">
          Ward Admission
        </h1>
      </div>

      {patientAdmission && (
        <Card className="p-6">
          <h3 className="font-medium">Current Admission</h3>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-500">
            Ward: {patientAdmission.ward_name}
            {patientAdmission.bed_code && ` | Bed: ${patientAdmission.bed_code}`}
            {" | Admitted: "}{patientAdmission.admitted_at?.slice(0, 16)} by {patientAdmission.admitted_by}
          </p>
          <Button
            variant="secondary"
            className="mt-4"
            onClick={() => setDischargeConfirmOpen(true)}
          >
            Discharge
          </Button>
        </Card>
      )}

      <ConfirmDialog
        open={dischargeConfirmOpen}
        onOpenChange={setDischargeConfirmOpen}
        title="Discharge patient"
        message="Are you sure you want to discharge this patient from the ward? This will end the current admission."
        confirmLabel="Discharge"
        variant="danger"
        loading={loading}
        onConfirm={async () => {
          if (!patientAdmission) return;
          try {
            await api.patch(`/admissions/${patientAdmission.admission_id}/discharge`, { discharge_reason: notes });
            fetchAdmissions();
          } catch (e) {
            setError(e instanceof Error ? e.message : "Failed");
          }
        }}
      />

      {!patientAdmission && (
        <Card className="p-6">
          <h3 className="font-medium">Admit Patient</h3>
          <form
            className="mt-4 space-y-4"
            onSubmit={async (e) => {
              e.preventDefault();
              setError("");
              setLoading(true);
              try {
                const body: { patient_id: string; ward_id: string; bed_id?: string } = { patient_id: patientId, ward_id: wardId };
                if (bedId) body.bed_id = bedId;
                await api.post("/admissions/create", body);
                fetchAdmissions();
                setWardId("");
                setBedId("");
                setNotes("");
              } catch (e) {
                setError(e instanceof Error ? e.message : "Failed to admit");
              } finally {
                setLoading(false);
              }
            }}
          >
            <div>
              <label className="mb-1.5 block text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Ward</label>
              <select
                value={wardId}
                onChange={(e) => setWardId(e.target.value)}
                className="h-11 w-full rounded-lg border-[1.5px] border-slate-300 dark:border-slate-700 px-3"
                required
              >
                <option value="">Select ward</option>
                {wards.map((w) => (
                  <option key={w.ward_id} value={w.ward_id}>{w.ward_name}</option>
                ))}
              </select>
            </div>
            {wardId && (
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase text-slate-500 dark:text-slate-500">Bed (optional)</label>
                <select
                  value={bedId}
                  onChange={(e) => setBedId(e.target.value)}
                  className="h-11 w-full rounded-lg border-[1.5px] border-slate-300 dark:border-slate-700 px-3"
                >
                  <option value="">No bed</option>
                  {beds.map((b) => (
                    <option key={b.id} value={b.id}>{b.bed_code} ({b.status})</option>
                  ))}
                </select>
              </div>
            )}
            {error && <p className="text-sm text-[#DC2626]">{error}</p>}
            <Button type="submit" disabled={loading}>{loading ? "Admitting..." : "Admit"}</Button>
          </form>
        </Card>
      )}
    </div>
  );
}
