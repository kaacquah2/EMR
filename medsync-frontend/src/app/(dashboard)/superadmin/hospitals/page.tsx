"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

type HospitalRow = {
  hospital_id: string;
  name: string;
  region: string;
  nhis_code?: string | null;
  staff_count?: number | null;
  patient_count?: number | null;
  is_active?: boolean | null;
  created_at?: string | null;
};

export default function SuperAdminHospitalsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const [hospitals, setHospitals] = useState<HospitalRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  const [onboardOpen, setOnboardOpen] = useState(false);
  const [onboardLoading, setOnboardLoading] = useState(false);
  const [onboardError, setOnboardError] = useState("");
  const [onboardForm, setOnboardForm] = useState({
    name: "",
    region: "",
    nhis_code: "",
    address: "",
    phone: "",
    email: "",
    head_of_facility: "",
  });

  const canAccess = user?.role === "super_admin";
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  const loadHospitals = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get<{ data: HospitalRow[] }>("/superadmin/hospitals");
      const rows = Array.isArray(r?.data) ? r.data : [];
      setHospitals(rows);
    } catch {
      setHospitals([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    if (typeof window !== "undefined") {
      setHighlightId(new URLSearchParams(window.location.search).get("highlight"));
    }
  }, []);

  useEffect(() => {
    if (!canAccess) return;
    void loadHospitals();
  }, [canAccess, loadHospitals]);

  useEffect(() => {
    if (!highlightId || loading) return;
    const el = document.getElementById(`hospital-row-${highlightId}`);
    el?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [highlightId, loading, hospitals.length]);

  const submitOnboard = async () => {
    setOnboardError("");
    setOnboardLoading(true);
    try {
      await api.post("/superadmin/onboard-hospital", {
        name: onboardForm.name.trim(),
        region: onboardForm.region.trim(),
        nhis_code: onboardForm.nhis_code.trim(),
        address: onboardForm.address.trim(),
        phone: onboardForm.phone.trim(),
        email: onboardForm.email.trim(),
        head_of_facility: onboardForm.head_of_facility.trim(),
      });
      setOnboardOpen(false);
      setOnboardForm({
        name: "",
        region: "",
        nhis_code: "",
        address: "",
        phone: "",
        email: "",
        head_of_facility: "",
      });
      await loadHospitals();
    } catch (e) {
      setOnboardError(e instanceof Error ? e.message : "Failed to create hospital");
    } finally {
      setOnboardLoading(false);
    }
  };

  const totals = useMemo(() => {
    const total = hospitals.length;
    const active = hospitals.filter((h) => h.is_active !== false).length;
    return { total, active };
  }, [hospitals]);

  if (user && !canAccess) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">
        Redirecting...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Hospitals</h1>
          <p className="text-sm text-slate-500 dark:text-slate-500">
            Total: <strong>{totals.total}</strong> · Active:{" "}
            <strong>{totals.active}</strong>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => setOnboardOpen(true)}>
            Onboard hospital
          </Button>
          <Link href="/superadmin/cross-facility-activity-log">
            <Button variant="secondary">Cross-Facility Monitor</Button>
          </Link>
          <Link href="/admin/facilities">
            <Button variant="secondary">Facilities</Button>
          </Link>
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All hospitals</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-500">Loading…</p>
          ) : hospitals.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-500">No hospitals.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800">
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Name</th>
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Region</th>
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">NHIS</th>
                    <th className="py-2 text-right font-medium text-slate-500 dark:text-slate-500">Staff</th>
                    <th className="py-2 text-right font-medium text-slate-500 dark:text-slate-500">Patients</th>
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Status</th>
                    <th className="py-2 text-right font-medium text-slate-500 dark:text-slate-500">Manage</th>
                  </tr>
                </thead>
                <tbody>
                  {hospitals.map((h) => (
                    <tr
                      key={h.hospital_id}
                      id={`hospital-row-${h.hospital_id}`}
                      className={`border-b border-slate-100 dark:border-slate-900 ${
                        highlightId === h.hospital_id ? "bg-[#F0FDFF]" : ""
                      }`}
                    >
                      <td className="py-2">{h.name}</td>
                      <td className="py-2">{h.region}</td>
                      <td className="py-2 font-mono text-xs text-[#475569]">{h.nhis_code ?? "—"}</td>
                      <td className="py-2 text-right">{h.staff_count ?? "—"}</td>
                      <td className="py-2 text-right">{h.patient_count ?? "—"}</td>
                      <td className="py-2">
                        <span
                          className={`rounded px-2 py-0.5 text-xs font-semibold ${
                            h.is_active === false
                              ? "bg-slate-100 text-slate-700"
                              : "bg-green-100 text-green-800"
                          }`}
                        >
                          {h.is_active === false ? "Inactive" : "Active"}
                        </span>
                      </td>
                      <td className="py-2 text-right">
                        <Link href={`/admin/facilities?hospital=${encodeURIComponent(h.hospital_id)}`}>
                          <Button size="sm" variant="secondary">
                            Manage →
                          </Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Dialog open={onboardOpen} onOpenChange={setOnboardOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent className="max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Onboard hospital</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 pt-2">
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">Name *</label>
                <Input
                  className="mt-1"
                  value={onboardForm.name}
                  onChange={(e) =>
                    setOnboardForm((f) => ({ ...f, name: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">Region *</label>
                <Input
                  className="mt-1"
                  value={onboardForm.region}
                  onChange={(e) =>
                    setOnboardForm((f) => ({ ...f, region: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">NHIS code *</label>
                <Input
                  className="mt-1 font-mono text-sm"
                  value={onboardForm.nhis_code}
                  onChange={(e) =>
                    setOnboardForm((f) => ({ ...f, nhis_code: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">Address</label>
                <Input
                  className="mt-1"
                  value={onboardForm.address}
                  onChange={(e) =>
                    setOnboardForm((f) => ({ ...f, address: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">Phone</label>
                <Input
                  className="mt-1"
                  value={onboardForm.phone}
                  onChange={(e) =>
                    setOnboardForm((f) => ({ ...f, phone: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">Email</label>
                <Input
                  className="mt-1"
                  type="email"
                  value={onboardForm.email}
                  onChange={(e) =>
                    setOnboardForm((f) => ({ ...f, email: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="text-xs font-medium text-slate-500 dark:text-slate-500">Head of facility</label>
                <Input
                  className="mt-1"
                  value={onboardForm.head_of_facility}
                  onChange={(e) =>
                    setOnboardForm((f) => ({
                      ...f,
                      head_of_facility: e.target.value,
                    }))
                  }
                />
              </div>
              {onboardError ? (
                <p className="text-sm text-red-600">{onboardError}</p>
              ) : null}
              <div className="flex justify-end gap-2 pt-2">
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => setOnboardOpen(false)}
                  disabled={onboardLoading}
                >
                  Cancel
                </Button>
                <Button
                  type="button"
                  disabled={
                    onboardLoading ||
                    !onboardForm.name.trim() ||
                    !onboardForm.region.trim() ||
                    !onboardForm.nhis_code.trim()
                  }
                  onClick={() => void submitOnboard()}
                >
                  {onboardLoading ? "Creating…" : "Create hospital"}
                </Button>
              </div>
            </div>
          </DialogContent>
        </DialogPortal>
      </Dialog>
    </div>
  );
}

