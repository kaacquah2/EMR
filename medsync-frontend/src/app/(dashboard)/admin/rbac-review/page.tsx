"use client";

import React, { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/lib/toast-context";
import { hasRole, ALL_ADMIN_ROLES } from "@/lib/permissions";

type RbacRow = {
  user_id: string;
  full_name: string;
  role: string;
  days_overdue: number;
  last_role_reviewed_at: string | null;
};

export default function RbacReviewPage() {
  const { user } = useAuth();
  const api = useApi();
  const toast = useToast();
  const [rows, setRows] = useState<RbacRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const r = await api.get<{ data: RbacRow[] }>("/admin/rbac-review");
      setRows(Array.isArray(r?.data) ? r.data : []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  const markReviewed = async (userId: string) => {
    setBusy(userId);
    try {
      await api.patch(`/admin/users/${userId}/role`, {
        last_role_reviewed_at: new Date().toISOString(),
      });
      toast.success("Marked as reviewed");
      await load();
    } catch {
      toast.error("Update failed");
    } finally {
      setBusy(null);
    }
  };

  // RBAC-03: both hospital_admin AND super_admin can access this page
  if (!user || !hasRole(user.role, ALL_ADMIN_ROLES)) {
    return (
      <div className="p-8">
        <p className="text-slate-500 dark:text-slate-500">Access denied.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-header-title">RBAC role review — {user.hospital_name ?? "Hospital"}</h1>
        <p className="page-header-desc">
          Staff whose role has not been reviewed in 90+ days appear below. Mark each row after review.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Staff</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-slate-500 dark:text-slate-500">Loading…</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-200 dark:border-slate-800">
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Staff member</th>
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Role</th>
                    <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Last reviewed</th>
                    <th className="py-2 text-right font-medium text-slate-500 dark:text-slate-500">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.user_id} className="border-b border-slate-100 dark:border-slate-900">
                      <td className="py-2 font-medium text-slate-900 dark:text-slate-100">{r.full_name}</td>
                      <td className="py-2 text-slate-500 dark:text-slate-500">{r.role.replace(/_/g, " ")}</td>
                      <td className="py-2 text-slate-500 dark:text-slate-500">
                        {r.last_role_reviewed_at
                          ? new Date(r.last_role_reviewed_at).toLocaleDateString("en-GB")
                          : "Never"}
                      </td>
                      <td className="py-2 text-right">
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busy === r.user_id}
                          onClick={() => void markReviewed(r.user_id)}
                        >
                          {busy === r.user_id ? "…" : "Mark reviewed"}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {rows.length === 0 ? <p className="mt-4 text-slate-500 dark:text-slate-500">No staff to list.</p> : null}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
