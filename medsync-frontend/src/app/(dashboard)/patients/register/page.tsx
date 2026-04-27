"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useFacilities } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
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
  const [step, setStep] = useState(1);
  const [form, setForm] = useState({
    full_name: "",
    date_of_birth: "",
    gender: "male" as "male" | "female" | "other" | "unknown",
    ghana_health_id: "",
    phone: "",
    national_id: "",
    blood_group: "",
    allergies: [] as { allergen: string; reaction_type: string; severity: string }[],
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [hospitalId, setHospitalId] = useState("");
  const [duplicateResult, setDuplicateResult] = useState<{
    duplicate: boolean;
    existing?: { full_name?: string; ghana_health_id?: string };
  } | null>(null);
  const [checkingDuplicate, setCheckingDuplicate] = useState(false);

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
    setForm((f) => ({ ...f, ghana_health_id: formatGhanaId(v) }));
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit) return;
    setError("");
    setLoading(true);
    try {
      const body: Record<string, unknown> = {
        full_name: form.full_name,
        date_of_birth: form.date_of_birth,
        gender: form.gender,
        ghana_health_id: form.ghana_health_id,
        phone: form.phone || undefined,
        national_id: form.national_id || undefined,
        blood_group: form.blood_group || "unknown",
        allergies: form.allergies,
      };
      if (user?.role === "super_admin" && effectiveHospitalId) body.hospital_id = effectiveHospitalId;
      // UX-07: redirect to patient profile, not search page
      const patient = await api.post<{ patient_id: string }>("/patients", body);
      router.push(`/patients/${patient.patient_id}?registered=1`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

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
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))} required />

              <Input label="Date of Birth" type="date" value={form.date_of_birth}
                onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))} required />

              <Select
                label="Gender"
                value={form.gender}
                onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value as typeof form.gender }))}
              >
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other</option>
                <option value="unknown">Unknown</option>
              </Select>

              {/* UX-06: onBlur triggers duplicate check */}
              <div>
                <Input label="Ghana Health ID" value={form.ghana_health_id}
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

              <Input label="Phone (optional)" type="tel" value={form.phone} onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))} />
              <Input label="National ID (optional)" value={form.national_id} onChange={(e) => setForm((f) => ({ ...f, national_id: e.target.value }))} />

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
                onChange={(e) => setForm((f) => ({ ...f, blood_group: e.target.value }))}
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

        {error && <p className="mt-4 text-sm text-[var(--red-600)]" role="alert">{error}</p>}
      </form>
    </div>
  );
}
