"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { useFacilities } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";

const REGISTER_PATIENT_ROLES = ["hospital_admin", "super_admin"];

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
  const [duplicateResult, setDuplicateResult] = useState<{ duplicate: boolean; existing?: { full_name?: string; ghana_health_id?: string } } | null>(null);

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
  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

  const handleGhanaIdChange = (v: string) => {
    setForm((f) => ({ ...f, ghana_health_id: formatGhanaId(v) }));
  };

  const effectiveHospitalId = user?.role === "super_admin" && !user.hospital_id ? hospitalId : (user?.hospital_id ?? "");
  const canSubmit = !isSuperAdminNoHospital || !!hospitalId;
  const checkDuplicate = async () => {
    if (!form.ghana_health_id.trim()) return;
    try {
      const res = await api.get<{ duplicate: boolean; existing?: { full_name?: string; ghana_health_id?: string } }>(
        `/patients/duplicate-check?ghana_health_id=${encodeURIComponent(form.ghana_health_id.trim())}`
      );
      setDuplicateResult(res);
      return res;
    } catch {
      setDuplicateResult(null);
      return null;
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
      await api.post("/patients", body);
      router.push("/patients/search");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
        Register New Patient
      </h1>

      <form onSubmit={handleSubmit}>
        {step === 1 && (
          <Card>
            <CardHeader>
              <CardTitle>Identity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {isSuperAdminNoHospital && (
                <div>
                  <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                    Register patient at facility (required)
                  </label>
                  <select
                    value={hospitalId}
                    onChange={(e) => setHospitalId(e.target.value)}
                    required
                    className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                  >
                    <option value="">Select facility</option>
                    {facilities.map((f) => (
                      <option key={f.facility_id} value={f.facility_id}>
                        {f.name} ({f.nhis_code})
                      </option>
                    ))}
                  </select>
                  <p className="mt-1 text-xs text-[#64748B]">
                    Super Admin must select the facility where this patient is being registered.
                  </p>
                </div>
              )}
              <Input
                label="Full Name"
                value={form.full_name}
                onChange={(e) => setForm((f) => ({ ...f, full_name: e.target.value }))}
                required
              />
              <Input
                label="Date of Birth"
                type="date"
                value={form.date_of_birth}
                onChange={(e) => setForm((f) => ({ ...f, date_of_birth: e.target.value }))}
                required
              />
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                  Gender
                </label>
                <select
                  value={form.gender}
                  onChange={(e) => setForm((f) => ({ ...f, gender: e.target.value as typeof form.gender }))}
                  className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                >
                  <option value="male">Male</option>
                  <option value="female">Female</option>
                  <option value="other">Other</option>
                  <option value="unknown">Unknown</option>
                </select>
              </div>
              <Input
                label="Ghana Health ID"
                value={form.ghana_health_id}
                onChange={(e) => handleGhanaIdChange(e.target.value)}
                placeholder="GH-ACC-2025-003847"
                required
              />
              {duplicateResult?.duplicate && (
                <p className="text-sm text-[#B91C1C]">
                  Duplicate found: {duplicateResult.existing?.full_name} ({duplicateResult.existing?.ghana_health_id}). Registration is blocked.
                </p>
              )}
              <Input
                label="Phone (optional)"
                value={form.phone}
                onChange={(e) => setForm((f) => ({ ...f, phone: e.target.value }))}
              />
              <Input
                label="National ID (optional)"
                value={form.national_id}
                onChange={(e) => setForm((f) => ({ ...f, national_id: e.target.value }))}
              />
              <Button
                type="button"
                onClick={async () => {
                  const result = await checkDuplicate();
                  if (!result?.duplicate) setStep(2);
                }}
                disabled={isSuperAdminNoHospital && !hospitalId}
              >
                Next: Medical
              </Button>
            </CardContent>
          </Card>
        )}

        {step === 2 && (
          <Card>
            <CardHeader>
              <CardTitle>Medical</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <label className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-[#64748B]">
                  Blood Group
                </label>
                <select
                  value={form.blood_group}
                  onChange={(e) => setForm((f) => ({ ...f, blood_group: e.target.value }))}
                  className="h-11 w-full rounded-lg border-[1.5px] border-[#CBD5E1] px-3"
                >
                  <option value="">Select</option>
                  {["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-", "unknown"].map((bg) => (
                    <option key={bg} value={bg}>{bg}</option>
                  ))}
                </select>
              </div>
              <Button type="button" variant="secondary" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button type="submit" disabled={loading || !canSubmit}>
                {loading ? "Registering..." : "Register Patient"}
              </Button>
            </CardContent>
          </Card>
        )}
        {error && <p className="mt-4 text-sm text-[#DC2626]">{error}</p>}
      </form>
    </div>
  );
}
