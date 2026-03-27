"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { isBenignApiNetworkFailure } from "@/lib/api-client";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { API_BASE } from "@/lib/api-base";

function getBreadcrumb(pathname: string): string[] {
  const parts = pathname.split("/").filter(Boolean);
  const labels: Record<string, string> = {
    dashboard: "Dashboard",
    patients: "Patients",
    search: "Search",
    register: "Register",
    admin: "Admin",
    users: "User Management",
    "audit-logs": "Audit Logs",
    lab: "Lab",
    orders: "Orders",
    superadmin: "Super Admin",
  };
  return parts.map((p) => labels[p] || p);
}

type FacilityOption = { facility_id: string; name: string };

export function TopBar() {
  const pathname = usePathname();
  const router = useRouter();
  const { user, viewAsHospitalId, viewAsHospitalName, setViewAs, getAccessToken, getViewAsHeader } = useAuth();
  const api = useApi();
  const toast = useToast();
  const [facilities, setFacilities] = useState<FacilityOption[]>([]);
  const [facilitiesError, setFacilitiesError] = useState<string | null>(null);
  const [validatingChain, setValidatingChain] = useState(false);
  const [exportingAudit, setExportingAudit] = useState(false);
  const breadcrumb = getBreadcrumb(pathname);
  const now = new Date();
  const timeStr = now.toLocaleTimeString("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
  });

  useEffect(() => {
    if (user?.role !== "super_admin") return;
    api
      .get<{
        data: Array<{
          hospital_id: string;
          name: string;
        }>;
      }>("/superadmin/hospitals")
      .then((r) => {
        const rows = Array.isArray(r?.data) ? r.data : [];
        setFacilities(
          rows.map((h) => ({ facility_id: h.hospital_id, name: h.name }))
        );
        setFacilitiesError(rows.length ? null : "No hospitals in network.");
      })
      .catch((err) => {
        if (!isBenignApiNetworkFailure(err)) {
          console.error("Failed to fetch hospitals for View-As:", err);
        }
        setFacilitiesError(
          isBenignApiNetworkFailure(err)
            ? "Could not reach the API (timeout or offline). Is the backend running on port 8000?"
            : "Failed to load hospitals. Please try again."
        );
      });
  }, [user?.role, api]);

  const facilityLabel = user
    ? (viewAsHospitalId && viewAsHospitalName
        ? viewAsHospitalName
        : user.hospital_name ?? (user.role === "super_admin" && !user.hospital_id ? "All hospitals" : "Hospital"))
    : null;

  const exportAuditCsv = async () => {
    if (user?.role !== "hospital_admin") return;
    setExportingAudit(true);
    try {
      const headers: HeadersInit = { Accept: "text/csv" };
      const token = getAccessToken?.();
      if (token) headers.Authorization = `Bearer ${token}`;
      const vh = getViewAsHeader?.() ?? null;
      if (vh) (headers as Record<string, string>)["X-View-As-Hospital"] = vh;
      const res = await fetch(`${API_BASE}/reports/audit/export?days=90`, { method: "GET", headers });
      if (!res.ok) {
        throw new Error(`Export failed (${res.status})`);
      }
      const countHeader = res.headers.get("X-Export-Count");
      const blob = await res.blob();
      const fname = `audit-${(user.hospital_name ?? "hospital").replace(/\s+/g, "-")}-${new Date().toISOString().slice(0, 10)}.csv`;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = fname;
      a.click();
      URL.revokeObjectURL(url);
      const n = countHeader ? parseInt(countHeader, 10) : NaN;
      toast.success(
        Number.isFinite(n) ? `Exported ${n.toLocaleString()} records` : "Audit CSV downloaded"
      );
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Export failed");
    } finally {
      setExportingAudit(false);
    }
  };

  const validateChain = async () => {
    if (user?.role !== "super_admin") return;
    setValidatingChain(true);
    try {
      const res = await api.post<{ status?: string; message?: string }>(
        "/audit/validate-chain",
        {}
      );
      const status = (res?.status || "").toLowerCase();
      if (status === "valid" || status === "ok") {
        toast.success("Audit chain validated: intact.");
      } else if (status === "invalid" || status === "tampered") {
        toast.error("Audit chain validation failed: tamper flags detected.");
      } else {
        toast.info(res?.message ? `Audit chain: ${res.message}` : "Audit chain validation complete.");
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Validation failed";
      toast.error(`Validate chain failed: ${msg}`);
    } finally {
      setValidatingChain(false);
    }
  };

  return (
    <>
      {user?.role === "super_admin" && viewAsHospitalId && (
        <div className="flex w-full items-center gap-2 border-b border-[#5DCAA5] bg-[#E1F5EE] px-6 py-2 text-[13px] text-[#085041]">
          <span aria-hidden className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-[#BFECDD] text-[#085041]">
            i
          </span>
          <span className="flex-1 truncate">
            Viewing as: <strong>{viewAsHospitalName ?? viewAsHospitalId}</strong> — all actions are scoped to this hospital
          </span>
          <button
            type="button"
            onClick={() => setViewAs(null, null)}
            className="rounded-md px-3 py-1 text-[13px] font-semibold text-[#085041] hover:bg-[#BFECDD] focus:outline-none focus:ring-2 focus:ring-[#5DCAA5]"
          >
            Return to system view ×
          </button>
        </div>
      )}
      <header className="flex h-14 items-center justify-between border-b-2 border-[#0B8A96]/20 bg-white px-6 shadow-sm">
        <nav className="flex items-center gap-2 text-sm">
          {breadcrumb.map((label, i) => (
            <React.Fragment key={i}>
              {i > 0 && (
                <span className="text-[#475569]">/</span>
              )}
              <span className={i === breadcrumb.length - 1 ? "font-medium text-[#0F172A]" : "text-[#475569]"}>
                {label}
              </span>
            </React.Fragment>
          ))}
        </nav>
        <div className="flex items-center gap-4">
          {user?.role === "hospital_admin" && (
            <>
              <Button
                size="sm"
                variant="secondary"
                type="button"
                onClick={() => router.push("/admin/users?action=invite")}
              >
                + Invite staff
              </Button>
              <Button
                size="sm"
                variant="secondary"
                type="button"
                onClick={() => void exportAuditCsv()}
                disabled={exportingAudit}
              >
                {exportingAudit ? "Exporting…" : "Export audit CSV"}
              </Button>
            </>
          )}
          {user?.role === "super_admin" && (
            <>
              {facilitiesError ? (
                <div className="text-xs text-red-600 font-medium" title={facilitiesError}>
                  {facilitiesError}
                </div>
              ) : facilities.length > 0 ? (
                <select
                  value={viewAsHospitalId ?? ""}
                  onChange={(e) => {
                    const v = e.target.value;
                    if (!v) {
                      setViewAs(null, null);
                      return;
                    }
                    const f = facilities.find((x) => x.facility_id === v);
                    setViewAs(v, f?.name ?? null);
                  }}
                  className="rounded border border-[#0B8A96]/40 bg-white px-2 py-1 text-xs text-[#0F172A] focus:border-[#0B8A96] focus:outline-none"
                  title="View as facility (support)"
                >
                  <option value="">All hospitals</option>
                  {facilities.map((f) => (
                    <option key={f.facility_id} value={f.facility_id}>{f.name}</option>
                  ))}
                </select>
              ) : null}
            </>
          )}
          {facilityLabel && (
            <span className="text-xs font-medium text-[#0B8A96]" title="Facility context">
              Operating in: {facilityLabel}
            </span>
          )}
          {user?.role === "super_admin" && (
            <Button
              size="sm"
              variant="secondary"
              onClick={() => void validateChain()}
              disabled={validatingChain}
            >
              {validatingChain ? "Validating…" : "Validate chain"}
            </Button>
          )}
          <span className="font-mono text-sm text-[#475569]">{timeStr}</span>
        </div>
      </header>
    </>
  );
}
