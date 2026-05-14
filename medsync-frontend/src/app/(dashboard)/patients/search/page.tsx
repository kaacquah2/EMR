"use client";

import React, { useState, useCallback, useEffect } from "react";
import { List } from "react-window";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { ROLES, PATIENT_SEARCH_ROLES, REGISTER_PATIENT_ROLES, hasRole } from "@/lib/permissions";
import { usePatientSearch } from "@/hooks/use-patients";
import type { Patient } from "@/lib/types";
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
import {
  Table,
  TableHeader,
  TableRow,
  TableHead,
  TableBody,
  TableCell,
} from "@/components/ui/Table";
import { downloadCsv } from "@/lib/export-csv";
import { EmptyState } from "@/components/ui/empty-state";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { SearchX } from "lucide-react";

// RBAC-01: moved to centralised permissions.ts

const VirtualPatientList = ({ 
  patients, 
  isReceptionist 
}: { 
  patients: Patient[], 
  isReceptionist: boolean 
}) => {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const Row = ({ index, style }: any) => {
    const p = patients[index];
    return (
      <div 
        style={style} 
        className="flex items-center border-b border-slate-200 dark:border-slate-800 hover:bg-slate-50 dark:bg-slate-900 px-4"
      >
        <div className="w-[25%] font-medium text-slate-900 dark:text-slate-100 truncate pr-4">{p.full_name}</div>
        <div className="w-[20%] font-mono text-sm text-slate-500 dark:text-slate-500 truncate pr-4">{p.ghana_health_id}</div>
        <div className="w-[10%] text-sm text-slate-500 dark:text-slate-500">
          {Math.max(0, new Date().getFullYear() - new Date(p.date_of_birth).getFullYear())}
        </div>
        <div className="w-[10%] text-sm text-slate-500 dark:text-slate-500">{p.gender}</div>
        <div className="w-[15%] text-sm text-slate-500 dark:text-slate-500 truncate">{p.nhis_number || "—"}</div>
        <div className="w-[20%] flex justify-end gap-3 text-sm">
          {isReceptionist ? (
            <>
              <Link href="/appointments" className="text-[#0B8A96] hover:underline">
                Book
              </Link>
              <span className="text-[#0B8A96] cursor-pointer hover:underline">Info</span>
            </>
          ) : (
            <Link href={`/patients/${p.patient_id}`} className="text-[#0B8A96] hover:underline">
              View
            </Link>
          )}
        </div>
      </div>
    );
  };

  return (
    <List
      rowCount={patients.length}
      rowHeight={56}
      style={{ height: 400, width: "100%" }}
      rowComponent={Row}
      rowProps={{}}
    />
  );
};

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
    // UX-18: 300ms debounce (was 150ms)
    const id = setTimeout(() => {
      if (v.trim()) doSearch();
      setDebounceRef(null);
    }, 300);
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

  const isReceptionist = user?.role === ROLES.RECEPTIONIST;
  const canRegister = hasRole(user?.role, REGISTER_PATIENT_ROLES);
  const canExport = hasRole(user?.role, [ROLES.HOSPITAL_ADMIN, ROLES.SUPER_ADMIN]);

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <Breadcrumbs items={[{ label: "Patients" }]} />
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">
          Patient Search
        </h1>
        <div className="flex gap-2">
          {canExport && (
            <Button variant="secondary" onClick={handleExportPatients} disabled={exporting}>
              {exporting ? "Exporting..." : "Export CSV"}
            </Button>
          )}
          {canRegister && (
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
              data-testid="patient-search-input"
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
                    : "bg-slate-100 dark:bg-slate-900 text-slate-500 dark:text-slate-500 hover:bg-slate-200 dark:bg-slate-800"
                }`}
              >
                {t === "ghana_id" ? "Ghana Health ID" : t === "dob" ? "Date of Birth" : "Name"}
              </button>
            ))}
          </div>
          <Button onClick={doSearch} disabled={loading} data-testid="patient-search-submit">
            {loading ? "Searching..." : "Search"}
          </Button>
        </div>
      </Card>

      {error && (
        <p className="text-sm text-[#DC2626]">{error}</p>
      )}

      {loading && (
        <div className="rounded-lg border border-slate-300 dark:border-slate-700 bg-white p-8 text-center text-slate-500 dark:text-slate-500">
          Loading...
        </div>
      )}

      {!loading && results.length === 0 && query.trim() && (
        <Card className="p-0">
          <EmptyState
            icon={<SearchX className="h-12 w-12" />}
            title="Patient not found"
            description={`No local patients matched "${query}".`}
            action={
              canRegister ? (
                <Link href="/patients/register">
                  <Button variant="secondary">Register new patient</Button>
                </Link>
              ) : undefined
            }
          />
        </Card>
      )}

      {!loading && results.length > 0 && (
        <Card className="overflow-hidden p-0">
          <div className="overflow-x-auto">
            <Table className="w-full table-fixed">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[25%] uppercase text-xs">Name</TableHead>
                  <TableHead className="w-[20%] uppercase text-xs">Ghana Health ID</TableHead>
                  <TableHead className="w-[10%] uppercase text-xs">Age</TableHead>
                  <TableHead className="w-[10%] uppercase text-xs">Gender</TableHead>
                  <TableHead className="w-[15%] uppercase text-xs">NHIS</TableHead>
                  <TableHead align="right" className="w-[20%] uppercase text-xs">Actions</TableHead>
                </TableRow>
              </TableHeader>
            </Table>
            
            <div className="h-[400px] w-full">
              <VirtualPatientList 
                patients={results} 
                isReceptionist={isReceptionist} 
              />
            </div>
          </div>
        </Card>
      )}

      {!isReceptionist && (
      <div className="mt-10 border-t border-[var(--gray-300)] pt-8">
        {/* UX-20: contextual help text */}
        <h2 className="font-sora text-xl font-bold text-[var(--gray-900)] mb-2">
          Nationwide registry search
        </h2>
        <p className="mb-4 text-sm text-[var(--gray-500)]">
          Use this to find patients who visited <strong>other facilities</strong>. Results can be linked to this hospital so their records are accessible here.
          Use the local search above for patients already registered at your facility.
        </p>
        <Card className="p-4">
          <div className="flex flex-col gap-4 sm:flex-row">
            <div className="flex-1">
              <Input
                label="Search by name, national ID, phone, or email"
                value={globalQuery}
                onChange={(e) => setGlobalQuery(e.target.value)}
                placeholder="e.g. name or national ID"
                data-testid="patient-global-search-input"
                onKeyDown={(e) => e.key === "Enter" && globalSearch(globalQuery)}
              />
            </div>
            <Button
              onClick={() => globalSearch(globalQuery)}
              disabled={globalLoading}
              data-testid="patient-global-search-submit"
            >
              {globalLoading ? "Searching..." : "Search nationwide"}
            </Button>
          </div>
        </Card>
        {globalError && <p className="mt-2 text-sm text-[#DC2626]">{globalError}</p>}
        {globalLoading && (
          <div className="mt-4 rounded-lg border border-slate-300 dark:border-slate-700 bg-white p-8 text-center text-slate-500 dark:text-slate-500">
            Loading...
          </div>
        )}
        {!globalLoading && globalResults.length > 0 && (
          <Card className="mt-4 overflow-hidden p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="uppercase text-xs">Name</TableHead>
                    <TableHead className="uppercase text-xs">National ID</TableHead>
                    <TableHead className="uppercase text-xs">DOB</TableHead>
                    <TableHead className="uppercase text-xs">Facilities</TableHead>
                    <TableHead className="uppercase text-xs">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {globalResults.map((gp) => (
                    <TableRow key={gp.global_patient_id}>
                      <TableCell className="font-medium text-slate-900 dark:text-white">{gp.full_name}</TableCell>
                      <TableCell className="font-mono text-sm text-slate-500 dark:text-slate-400">{gp.national_id ?? "—"}</TableCell>
                      <TableCell className="text-sm text-slate-500 dark:text-slate-400">{gp.date_of_birth}</TableCell>
                      <TableCell className="text-sm text-slate-500 dark:text-slate-400">
                        {(gp.facility_names && gp.facility_names.length > 0)
                          ? gp.facility_names.join(", ")
                          : "—"}
                      </TableCell>
                      <TableCell className="flex gap-2">
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={() => openLinkModal({ global_patient_id: gp.global_patient_id, full_name: gp.full_name })}
                          data-testid="patient-link-to-facility"
                        >
                          Link to this facility
                        </Button>
                        <Link href={`/cross-facility-records/${gp.global_patient_id}`}>
                          <Button variant="secondary" size="sm">View records</Button>
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </Card>
        )}
        {!globalLoading && globalQuery.trim() && globalResults.length === 0 && (
          <Card className="mt-4 p-0">
            <EmptyState
              icon={<SearchX className="h-12 w-12" />}
              title="No global patient found"
              description="No patients found in the nationwide registry matching your query."
            />
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
              <p className="text-sm text-slate-500 dark:text-slate-500">
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
