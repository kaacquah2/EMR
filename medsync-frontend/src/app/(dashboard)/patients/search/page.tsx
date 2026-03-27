"use client";

import React, { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { usePatientSearch } from "@/hooks/use-patients";
import { useGlobalPatientSearch, useLinkFacilityPatient } from "@/hooks/use-interop";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { downloadCsv } from "@/lib/export-csv";

const PATIENT_SEARCH_ROLES = ["doctor", "hospital_admin", "super_admin", "nurse", "receptionist"];

export default function PatientSearchPage() {
  const router = useRouter();
  const { user, getAccessToken } = useAuth();
  const canAccess = user?.role && PATIENT_SEARCH_ROLES.includes(user.role);
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);
  const [exporting, setExporting] = useState(false);
  const handleExportPatients = async () => {
    setExporting(true);
    try {
      await downloadCsv("/reports/patients/export", getAccessToken(), "patients_export.csv");
    } catch {
      //
    } finally {
      setExporting(false);
    }
  };
  const { results, loading, error, search } = usePatientSearch();
  const {
    results: globalResults,
    loading: globalLoading,
    error: globalError,
    search: globalSearch,
  } = useGlobalPatientSearch();
  const { link, loading: linkLoading, error: linkError } = useLinkFacilityPatient();

  const [query, setQuery] = useState("");
  const [searchType, setSearchType] = useState<"ghana_id" | "name" | "dob">("name");
  const [debounceRef, setDebounceRef] = useState<ReturnType<typeof setTimeout> | null>(null);
  const [globalQuery, setGlobalQuery] = useState("");
  const [linkModalOpen, setLinkModalOpen] = useState(false);
  const [linkGlobalPatient, setLinkGlobalPatient] = useState<{
    global_patient_id: string;
    full_name: string;
  } | null>(null);
  const [localPatientId, setLocalPatientId] = useState("");
  const [linkSuccess, setLinkSuccess] = useState<string | null>(null);

  const doSearch = useCallback(() => {
    search(query, searchType);
  }, [search, query, searchType]);

  const handleChange = (v: string) => {
    setQuery(v);
    if (debounceRef) clearTimeout(debounceRef);
    const id = setTimeout(() => {
      if (v.trim()) doSearch();
      setDebounceRef(null);
    }, 150);
    setDebounceRef(id);
  };

  const openLinkModal = (gp: { global_patient_id: string; full_name: string }) => {
    setLinkGlobalPatient(gp);
    setLocalPatientId("");
    setLinkSuccess(null);
    setLinkModalOpen(true);
  };

  const doLink = useCallback(async () => {
    if (!linkGlobalPatient) return;
    try {
      const res = await link({
        global_patient_id: linkGlobalPatient.global_patient_id,
        local_patient_id: localPatientId.trim() || undefined,
      });
      setLinkSuccess(
        res.patient_id
          ? `Linked. Local patient: ${res.patient_id}`
          : "Linked to this facility."
      );
      setTimeout(() => {
        setLinkModalOpen(false);
        setLinkGlobalPatient(null);
        if (res.patient_id) router.push(`/patients/${res.patient_id}`);
      }, 1500);
    } catch {
      // error in linkError
    }
  }, [link, linkGlobalPatient, localPatientId, router]);

  const isReceptionist = user?.role === "receptionist";
  const canRegister = user?.role === "doctor" || user?.role === "hospital_admin" || user?.role === "super_admin";
  const canExport = canRegister;

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
          Patient Search
        </h1>
        <div className="flex gap-2">
          {canExport && !isReceptionist && (
            <Button variant="secondary" onClick={handleExportPatients} disabled={exporting}>
              {exporting ? "Exporting..." : "Export CSV"}
            </Button>
          )}
          {canRegister && !isReceptionist && (
            <Link href="/patients/register">
              <Button>Register New Patient</Button>
            </Link>
          )}
        </div>
      </div>

      <Card accent="teal" className="p-4">
        <div className="flex flex-col gap-4 sm:flex-row">
          <div className="flex-1">
            <Input
              label="Search"
              value={query}
              onChange={(e) => handleChange(e.target.value)}
              placeholder={
                searchType === "ghana_id"
                  ? "GH-ACC-2025-003847"
                  : searchType === "dob"
                    ? "YYYY-MM-DD"
                    : "Search by name, Ghana Health ID, phone, or NHIS number"
              }
              onKeyDown={(e) => e.key === "Enter" && doSearch()}
            />
          </div>
          <div className="flex gap-2">
            {(["name", "ghana_id", "dob"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setSearchType(t)}
                className={`rounded-lg px-3 py-2 text-sm font-medium ${
                  searchType === t
                    ? "bg-[#0B8A96] text-white"
                    : "bg-[#F1F5F9] text-[#64748B] hover:bg-[#E2E8F0]"
                }`}
              >
                {t === "ghana_id" ? "Ghana Health ID" : t === "dob" ? "Date of Birth" : "Name"}
              </button>
            ))}
          </div>
          <Button onClick={doSearch} disabled={loading}>
            {loading ? "Searching..." : "Search"}
          </Button>
        </div>
      </Card>

      {error && (
        <p className="text-sm text-[#DC2626]">{error}</p>
      )}

      {loading && (
        <div className="rounded-lg border border-[#CBD5E1] bg-white p-8 text-center text-[#64748B]">
          Loading...
        </div>
      )}

      {!loading && results.length === 0 && query.trim() && (
        <Card className="p-8 text-center">
          <p className="text-[#64748B]">Patient not found.</p>
          {isReceptionist ? (
            <p className="mt-2 text-sm text-[#64748B]">
              To register a new patient, please ask a doctor or hospital admin.
            </p>
          ) : canRegister && (
            <Link href="/patients/register" className="mt-4 inline-block">
              <Button variant="secondary">Register them?</Button>
            </Link>
          )}
        </Card>
      )}

      {!loading && results.length > 0 && (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Name</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Ghana Health ID</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Age</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Gender</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">NHIS</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Phone</th>
                  <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Actions</th>
                </tr>
              </thead>
              <tbody>
                {results.map((p) => (
                  <tr key={p.patient_id} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC]">
                    <td className="px-4 py-3 font-medium text-[#0F172A]">{p.full_name}</td>
                    <td className="px-4 py-3 font-mono text-sm text-[#64748B]">{p.ghana_health_id}</td>
                    <td className="px-4 py-3 text-sm text-[#64748B]">
                      {Math.max(0, new Date().getFullYear() - new Date(p.date_of_birth).getFullYear())}
                    </td>
                    <td className="px-4 py-3 text-sm text-[#64748B]">{p.gender}</td>
                    <td className="px-4 py-3 text-sm text-[#64748B]">{p.nhis_number || "—"}</td>
                    <td className="px-4 py-3 text-sm text-[#64748B]">{p.phone || "—"}</td>
                    <td className="px-4 py-3">
                      {isReceptionist ? (
                        <div className="flex gap-3 text-sm">
                          <Link href="/appointments" className="text-[#0B8A96] hover:underline">
                            Book Appointment
                          </Link>
                          <span className="text-[#0B8A96]">View Demographics</span>
                        </div>
                      ) : (
                        <Link href={`/patients/${p.patient_id}`} className="text-[#0B8A96] hover:underline">
                          View
                        </Link>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {!isReceptionist && (
      <div className="mt-10 border-t border-[#E2E8F0] pt-8">
        <h2 className="font-sora text-xl font-bold text-[#0F172A] mb-4">
          Search nationwide (global registry)
        </h2>
        <Card className="p-4">
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="flex-1">
              <Input
                label="Search by name, national ID, phone, or email"
                value={globalQuery}
                onChange={(e) => setGlobalQuery(e.target.value)}
                placeholder="e.g. name or national ID"
                onKeyDown={(e) => e.key === "Enter" && globalSearch(globalQuery)}
              />
            </div>
            <Button
              onClick={() => globalSearch(globalQuery)}
              disabled={globalLoading}
            >
              {globalLoading ? "Searching..." : "Search nationwide"}
            </Button>
          </div>
        </Card>
        {globalError && <p className="mt-2 text-sm text-[#DC2626]">{globalError}</p>}
        {globalLoading && (
          <div className="mt-4 rounded-lg border border-[#CBD5E1] bg-white p-8 text-center text-[#64748B]">
            Loading...
          </div>
        )}
        {!globalLoading && globalResults.length > 0 && (
          <Card className="mt-4 overflow-hidden p-0">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-[#E2E8F0] bg-[#F8FAFC]">
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Name</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">National ID</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">DOB</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Facilities</th>
                    <th className="px-4 py-3 text-left text-xs font-semibold uppercase text-[#64748B]">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {globalResults.map((gp) => (
                    <tr key={gp.global_patient_id} className="border-b border-[#E2E8F0] hover:bg-[#F8FAFC]">
                      <td className="px-4 py-3 font-medium text-[#0F172A]">{gp.full_name}</td>
                      <td className="px-4 py-3 font-mono text-sm text-[#64748B]">{gp.national_id ?? "—"}</td>
                      <td className="px-4 py-3 text-sm text-[#64748B]">{gp.date_of_birth}</td>
                      <td className="px-4 py-3 text-sm text-[#64748B]">
                        {(gp.facility_names && gp.facility_names.length > 0)
                          ? gp.facility_names.join(", ")
                          : "—"}
                      </td>
                      <td className="px-4 py-3 flex gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => openLinkModal({ global_patient_id: gp.global_patient_id, full_name: gp.full_name })}
                        >
                          Link to this facility
                        </Button>
                        <Link href={`/cross-facility-records/${gp.global_patient_id}`}>
                          <Button variant="secondary" size="sm">View records</Button>
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        )}
        {!globalLoading && globalQuery.trim() && globalResults.length === 0 && (
          <Card className="mt-4 p-8 text-center">
            <p className="text-[#64748B]">No global patient found.</p>
          </Card>
        )}
      </div>
      )}

      <Dialog open={linkModalOpen} onOpenChange={setLinkModalOpen}>
        <DialogPortal>
          <DialogOverlay />
          <DialogContent>
          <DialogHeader>
            <DialogTitle>Link patient to this facility</DialogTitle>
          </DialogHeader>
          {linkGlobalPatient && (
            <>
              <p className="text-sm text-[#64748B]">
                Linking <strong>{linkGlobalPatient.full_name}</strong> to your facility.
              </p>
              <Input
                label="Local patient ID (optional)"
                value={localPatientId}
                onChange={(e) => setLocalPatientId(e.target.value)}
                placeholder="Existing patient UUID or leave blank"
              />
              {linkError && <p className="text-sm text-[#DC2626]">{linkError}</p>}
              {linkSuccess && <p className="text-sm text-[#0B8A96]">{linkSuccess}</p>}
            </>
          )}
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setLinkModalOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={doLink}
              disabled={linkLoading || !linkGlobalPatient}
            >
              {linkLoading ? "Linking..." : "Link"}
            </Button>
          </div>
        </DialogContent>
        </DialogPortal>
      </Dialog>
    </div>
  );
}
