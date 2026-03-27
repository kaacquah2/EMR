"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useAuditLogs, type AuditLogFilters } from "@/hooks/use-admin";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { downloadCsv } from "@/lib/export-csv";

const AUDIT_ACTION_OPTIONS = [
  "", "VIEW", "VIEW_PATIENT_RECORD", "VIEW_CROSS_FACILITY_RECORD", "CREATE", "UPDATE", "DEACTIVATE",
  "EXPORT", "LOGIN", "LOGOUT", "LOGIN_FAILED", "ROLE_CHANGE", "INVITE_SENT", "ACCOUNT_ACTIVATED",
  "EMERGENCY_ACCESS", "CROSS_FACILITY_ACCESS_REVOKED", "BULK_IMPORT", "VIEW_AS_HOSPITAL", "permission_denied",
];

export default function AuditLogsPage() {
  const router = useRouter();
  const { user, getAccessToken } = useAuth();
  const [filters, setFilters] = useState<AuditLogFilters>({});
  const { logs, loading, fetch } = useAuditLogs(filters);
  const [exporting, setExporting] = useState(false);
  const canAccess = user?.role === "hospital_admin" || user?.role === "super_admin";
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);
  const handleExport = async () => {
    setExporting(true);
    try {
      await downloadCsv("/reports/audit/export", getAccessToken(), "audit_logs_export.csv");
    } catch {
      // ignore
    } finally {
      setExporting(false);
    }
  };

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
          Audit Logs
        </h1>
        <Button variant="secondary" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </div>

      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[#64748B]">Action type</label>
            <select
              className="h-10 rounded-lg border border-[#CBD5E1] px-3 text-sm"
              value={filters.action ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value || undefined }))}
            >
              {AUDIT_ACTION_OPTIONS.map((a) => (
                <option key={a || "all"} value={a}>{a || "All"}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#64748B]">Date from</label>
            <input
              type="date"
              className="h-10 rounded-lg border border-[#CBD5E1] px-3 text-sm"
              value={filters.date_from ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value || undefined }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-[#64748B]">Date to</label>
            <input
              type="date"
              className="h-10 rounded-lg border border-[#CBD5E1] px-3 text-sm"
              value={filters.date_to ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, date_to: e.target.value || undefined }))}
            />
          </div>
          <Button variant="secondary" size="sm" onClick={() => fetch()}>
            Apply
          </Button>
        </div>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-[#E2E8F0]">
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Timestamp</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">User</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Action</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Resource</th>
                {user?.role === "super_admin" && (
                  <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">Hospital</th>
                )}
                <th className="px-4 py-2 text-left text-xs font-semibold text-[#64748B]">IP</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={user?.role === "super_admin" ? 6 : 5} className="px-4 py-8 text-center text-[#64748B]">Loading...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={user?.role === "super_admin" ? 6 : 5} className="px-4 py-8 text-center text-[#64748B]">No logs.</td></tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.log_id} className="border-b border-[#F1F5F9]">
                    <td className="px-4 py-2 font-mono text-xs">{log.timestamp?.slice(0, 19)}</td>
                    <td className="px-4 py-2">{log.user}</td>
                    <td className="px-4 py-2">
                      <span className="rounded-full bg-[#F1F5F9] px-2 py-0.5 text-xs">{log.action}</span>
                    </td>
                    <td className="px-4 py-2 text-[#64748B]">{log.resource_type || "—"}</td>
                    {user?.role === "super_admin" && (
                      <td className="px-4 py-2 text-[#64748B]">{log.hospital ?? "—"}</td>
                    )}
                    <td className="px-4 py-2 font-mono text-xs text-[#0F172A]">{log.ip_address?.trim() || "—"}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
