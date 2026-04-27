"use client";

import React, { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { isBenignApiNetworkFailure } from "@/lib/api-client";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { ConnectionStatusIndicator } from "@/components/ui/ConnectionStatusIndicator";
import { API_BASE } from "@/lib/api-base";
import { Search } from "lucide-react";

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
      <header className="flex h-14 items-center justify-between border-b-2 border-[var(--teal-500)]/20 bg-white dark:bg-[#1E293B] px-4 md:px-6 shadow-sm">
        <div className="flex items-center gap-2">
          {/* UX-24: Hamburger button for mobile sidebar */}
          <button
            className="lg:hidden mr-1 flex h-8 w-8 items-center justify-center rounded-lg hover:bg-[var(--gray-100)] transition-colors"
            aria-label="Open navigation menu"
            onClick={() => {
              // Dispatch a custom event that the Sidebar listens for
              document.dispatchEvent(new CustomEvent('sidebar:open'));
            }}
          >
            <svg className="h-5 w-5 text-[var(--gray-700)]" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>

          <nav className="flex items-center gap-2 text-sm" aria-label="Breadcrumb">
            {breadcrumb.map((label, i) => (
              <React.Fragment key={i}>
                {i > 0 && <span className="text-[var(--gray-500)]" aria-hidden="true">/</span>}
                <span className={i === breadcrumb.length - 1 ? "font-medium text-[var(--gray-900)]" : "text-[var(--gray-500)]"}>{label}</span>
              </React.Fragment>
            ))}
            {/* Ward context pill for nurses */}
            {user?.role === "nurse" && user?.ward_name && (
              <>
                <span className="text-[#475569]">/</span>
                <span className="rounded-full bg-[#059669]/10 px-3 py-1 text-xs font-medium text-[#059669]">
                  Ward {user.ward_name}
                </span>
              </>
            )}
          </nav>
        </div>
        <div className="flex items-center gap-2 md:gap-4 flex-wrap justify-end">
          {/* UX-25: OS-aware keyboard shortcut hint */}
          <button
            onClick={() => {
              const event = new KeyboardEvent('keydown', { key: 'k', metaKey: true, bubbles: true });
              document.dispatchEvent(event);
            }}
            className="hidden md:flex items-center gap-2 px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground border rounded-lg hover:bg-muted transition-colors"
            title="Open command palette"
            aria-label="Open command palette"
          >
            <Search className="h-4 w-4" />
            <span>Search</span>
            <kbd
              className="ml-2 px-1.5 py-0.5 text-xs bg-muted rounded font-mono"
              aria-label={typeof navigator !== 'undefined' && /Mac/.test(navigator.platform) ? 'Command K' : 'Control K'}
            >
              {typeof navigator !== 'undefined' && /Mac/.test(navigator.platform) ? '⌘K' : 'Ctrl+K'}
            </kbd>
          </button>
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
          <ConnectionStatusIndicator />
          <span className="font-mono text-sm text-[#475569]">{timeStr}</span>
        </div>
      </header>
    </>
  );
}
