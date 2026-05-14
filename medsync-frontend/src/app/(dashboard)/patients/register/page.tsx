"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useForm } from "@/hooks/use-form";
import { useFacilities } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { DatePicker } from "@/components/ui/DatePicker";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { SuccessState } from "@/components/ui/SuccessState";
import { REGISTER_PATIENT_ROLES } from "@/lib/permissions";

// UX-05: step metadata
const STEPS = [
  { id: 1, label: "Identity" },
  { id: 2, label: "Medical" },
];

function formatGhanaId(v: string): string {
  const clean = v.toUpperCase().replace(/[^GH0-9-]/g, "");
  const parts = clean.split("-").filter(Boolean);
  if (parts[0] !== "GH" && !clean.startsWith("GH")) return v;
  let out = "GH";
  if (parts.length > 1) out += "-" + parts[1].slice(0, 4);
  if (parts.length > 2) out += "-" + parts[2].slice(0, 4);
  if (parts.length > 3) out += "-" + parts[3].slice(0, 6);
  return out;
}

export default function RegisterPatientPage() {
  const router = useRouter();
  const { user, viewAsHospitalId } = useAuth();
  const api = useApi();
  const { facilities, fetch: fetchFacilities } = useFacilities();
  const {
    values: form,
    errors,
    isSubmitting: loading,
    handleChange,
    handleSubmit: handleFinalSubmit,
  } = useForm({
    initialValues: {
      full_name: "",
      date_of_birth: "",
      gender: "male" as "male" | "female" | "other" | "unknown",
      ghana_health_id: "",
      phone: "",
      national_id: "",
      blood_group: "",
      allergies: [] as { allergen: string; reaction_type: string; severity: string }[],
    },
    validate: (v) => {
      const errs: Record<string, string> = {};
      if (!v.full_name) errs.full_name = "Full name is required";
      if (!v.date_of_birth) errs.date_of_birth = "Date of birth is required";
      if (!v.ghana_health_id) errs.ghana_health_id = "Ghana Health ID is required";
      return errs;
    },
    onSubmit: async (values) => {
      const payload = {
        ...values,
        hospital_id: effectiveHospitalId,
      };
      const res = await api.post<{ id: string }>("/patients", payload);
      setRegisteredPatientId(res.id);
    },
  });

  const [step, setStep] = useState(1);
  const [hospitalId, setHospitalId] = useState("");
  const [duplicateResult, setDuplicateResult] = useState<{
    duplicate: boolean;
    existing?: { full_name?: string; ghana_health_id?: string };
  } | null>(null);
  const [checkingDuplicate, setCheckingDuplicate] = useState(false);
  const [registeredPatientId, setRegisteredPatientId] = useState<string | null>(null);

  const canAccess = user?.role && REGISTER_PATIENT_ROLES.includes(user.role);
  const isSuperAdminNoHospital = user?.role === "super_admin" && !user.hospital_id;

  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  useEffect(() => {
    if (isSuperAdminNoHospital) fetchFacilities();
  }, [isSuperAdminNoHospital, fetchFacilities]);

  useEffect(() => {
    if (isSuperAdminNoHospital && viewAsHospitalId && facilities.some((f) => f.facility_id === viewAsHospitalId) && !hospitalId) {
      setHospitalId(viewAsHospitalId);
    }
  }, [isSuperAdminNoHospital, viewAsHospitalId, facilities, hospitalId]);

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[var(--gray-500)]">Redirecting…</div>;

  const handleGhanaIdChange = (v: string) => {
    handleChange("ghana_health_id", formatGhanaId(v));
    // Clear stale duplicate result when ID changes
    setDuplicateResult(null);
  };

  const effectiveHospitalId = user?.role === "super_admin" && !user.hospital_id ? hospitalId : (user?.hospital_id ?? "");
  const canSubmit = !isSuperAdminNoHospital || !!hospitalId;

  // UX-06: check duplicate on blur of Ghana ID field
  const checkDuplicate = async () => {
    if (!form.ghana_health_id.trim()) return null;
    setCheckingDuplicate(true);
    try {
      const res = await api.get<{ duplicate: boolean; existing?: { full_name?: string; ghana_health_id?: string } }>(
        `/patients/duplicate-check?ghana_health_id=${encodeURIComponent(form.ghana_health_id.trim())}`
      );
      setDuplicateResult(res);
      return res;
    } catch {
      setDuplicateResult(null);
      return null;
    } finally {
      setCheckingDuplicate(false);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    if (!canSubmit) return;
    handleFinalSubmit(e);
  };

  if (registeredPatientId) {
    return (
      <SuccessState
        title="Patient Registered"
        description={`Successfully registered ${form.full_name}. You can now view their profile or register another patient.`}
        actions={[
          {
            label: "View Patient Profile",
            href: `/patients/${registeredPatientId}`,
          },
          {
            label: "Register Another Patient",
            href: "/patients/register",
            variant: "secondary",
          },
        ]}
      />
    );
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="font-sora text-2xl font-bold text-[var(--gray-900)]">Register New Patient</h1>

      {/* UX-05: Step progress indicator */}
      <div className="flex items-center gap-0">
        {STEPS.map((s, idx) => (
          <React.Fragment key={s.id}>
            <div className="flex items-center gap-2">
              <span className={`flex h-7 w-7 items-center justify-center rounded-full text-sm font-bold transition-colors ${
                step === s.id
                  ? "bg-[var(--teal-500)] text-white"
                  : step > s.id
                    ? "bg-[var(--green-600)] text-white"
                    : "bg-[var(--gray-100)] text-[var(--gray-500)]"
              }`}>
                {step > s.id ? "✓" : s.id}
              </span>
              <span className={`text-sm font-medium ${step === s.id ? "text-[var(--gray-900)]" : "text-[var(--gray-500)]"}`}>
                {s.label}
              </span>
            </div>
            {idx < STEPS.length - 1 && (
              <div className={`mx-3 h-px flex-1 ${step > s.id ? "bg-[var(--green-600)]" : "bg-[var(--gray-300)]"}`} />
            )}
          </React.Fragment>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        {step === 1 && (
          <Card>
            <CardHeader><CardTitle>Identity</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              {isSuperAdminNoHospital && (
                  <Select
                    label="Register patient at facility (required)"
                    value={hospitalId}
                    onChange={(e) => setHospitalId(e.target.value)}
                    required
                  >
                    <option value="">Select facility</option>
                    {facilities.map((f) => (
                      <option key={f.facility_id} value={f.facility_id}>{f.name} ({f.nhis_code})</option>
                    ))}
                  </Select>
              )}

              <Input label="Full Name" value={form.full_name}
                error={errors.full_name}
                onChange={(e) => handleChange("full_name", e.target.value)} required />

              <DatePicker
                label="Date of Birth"
                error={errors.date_of_birth}
                value={form.date_of_birth ? new Date(form.date_of_birth + "T12:00:00") : null}
                onChange={(date) => {
                  if (date) {
                    const y = date.getFullYear();
                    const m = String(date.getMonth() + 1).padStart(2, '0');
                    const d = String(date.getDate()).padStart(2, '0');
                    handleChange("date_of_birth", `${y}-${m}-${d}`);
                  } else {
                    handleChange("date_of_birth", "");
                  }
                }}
                format="YYYY-MM-DD"
              />

              <Select
                label="Gender"
                value={form.gender}
                onChange={(e) => handleChange("gender", e.target.value)}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
                <option value="unknown">Unknown</option>
              </Select>

              {/* UX-06: onBlur triggers duplicate check */}
              <div>
                <Input label="Ghana Health ID" value={form.ghana_health_id}
                  error={errors.ghana_health_id}
                  onChange={(e) => handleGhanaIdChange(e.target.value)}
                  onBlur={() => { if (form.ghana_health_id.trim()) void checkDuplicate(); }}
                  placeholder="GH-ACC-2025-003847" required />
                {checkingDuplicate && <p className="mt-1 text-xs text-[var(--gray-500)]">Checking for duplicates…</p>}
                {duplicateResult?.duplicate && (
                  <p className="mt-1 text-sm text-[var(--red-600)]" role="alert">
                    ⚠ Duplicate found: {duplicateResult.existing?.full_name} ({duplicateResult.existing?.ghana_health_id}). Registration blocked.
                  </p>
                )}
                {duplicateResult && !duplicateResult.duplicate && form.ghana_health_id && (
                  <p className="mt-1 text-xs text-[var(--green-600)]">✓ ID is available</p>
                )}
              </div>

              <Input label="Phone (optional)" type="tel" value={form.phone} onChange={(e) => handleChange("phone", e.target.value)} />
              <Input label="National ID (optional)" value={form.national_id} onChange={(e) => handleChange("national_id", e.target.value)} />

              {/* UX-08: "Continue" not "Next: Medical" */}
              <Button type="button"
                onClick={async () => {
                  const result = await checkDuplicate();
                  if (!result?.duplicate) setStep(2);
                }}
                disabled={(isSuperAdminNoHospital && !hospitalId) || duplicateResult?.duplicate === true}
              >
                Continue →
              </Button>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardHeader><CardTitle>Medical Information</CardTitle></CardHeader>
            <CardContent className="space-y-4">
              <Select
                label="Blood Group"
                value={form.blood_group}
                onChange={(e) => handleChange("blood_group", e.target.value)}
              >
                <option value="">Select</option>
                {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"].map((bg) => (
                  <option key={bg} value={bg}>{bg}</option>
                ))}
              </Select>

              <div className="flex gap-2">
                <Button type="button" variant="secondary" onClick={() => setStep(1)}>← Back</Button>
                <Button type="submit" loading={loading} disabled={!canSubmit}>
                  Register patient
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {errors.form && <p className="mt-4 text-sm text-[var(--red-600)]" role="alert">{errors.form}</p>}
      </form>
    </div>
  );
}
