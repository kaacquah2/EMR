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

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">
          Audit Logs
        </h1>
        <Button variant="secondary" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting..." : "Export CSV"}
        </Button>
      </div>

      <Card className="p-6">
        <div className="mb-4 flex flex-wrap items-end gap-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-500">Action type</label>
            <select
              className="h-10 rounded-lg border border-slate-300 dark:border-slate-700 px-3 text-sm"
              value={filters.action ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, action: e.target.value || undefined }))}
            >
              {AUDIT_ACTION_OPTIONS.map((a) => (
                <option key={a || "all"} value={a}>{a || "All"}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-500">Date from</label>
            <input
              type="date"
              className="h-10 rounded-lg border border-slate-300 dark:border-slate-700 px-3 text-sm"
              value={filters.date_from ?? ""}
              onChange={(e) => setFilters((f) => ({ ...f, date_from: e.target.value || undefined }))}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500 dark:text-slate-500">Date to</label>
            <input
              type="date"
              className="h-10 rounded-lg border border-slate-300 dark:border-slate-700 px-3 text-sm"
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
              <tr className="border-b border-slate-200 dark:border-slate-800">
                <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Timestamp</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">User</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Action</th>
                <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Resource</th>
                {user?.role === "super_admin" && (
                  <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">Hospital</th>
                )}
                <th className="px-4 py-2 text-left text-xs font-semibold text-slate-500 dark:text-slate-500">IP</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={user?.role === "super_admin" ? 6 : 5} className="px-4 py-8 text-center text-slate-500 dark:text-slate-500">Loading...</td></tr>
              ) : logs.length === 0 ? (
                <tr><td colSpan={user?.role === "super_admin" ? 6 : 5} className="px-4 py-8 text-center text-slate-500 dark:text-slate-500">No logs.</td></tr>
              ) : (
                logs.map((log) => (
                  <tr key={log.log_id} className="border-b border-slate-100 dark:border-slate-900">
                    <td className="px-4 py-2 font-mono text-xs">{log.timestamp?.slice(0, 19)}</td>
                    <td className="px-4 py-2">{log.user}</td>
                    <td className="px-4 py-2">
                      <span className="rounded-full bg-slate-100 dark:bg-slate-900 px-2 py-0.5 text-xs">{log.action}</span>
                    </td>
                    <td className="px-4 py-2 text-slate-500 dark:text-slate-500">{log.resource_type || "—"}</td>
                    {user?.role === "super_admin" && (
                      <td className="px-4 py-2 text-slate-500 dark:text-slate-500">{log.hospital ?? "—"}</td>
                    )}
                    <td className="px-4 py-2 font-mono text-xs text-slate-900 dark:text-slate-100">{log.ip_address?.trim() || "—"}</td>
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
