"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useApi } from "@/hooks/use-api";
import { useToast } from "@/lib/toast-context";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "./StatCard";

type HaUser = {
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  account_status: string;
  ward_name?: string | null;
  lab_unit_name?: string | null;
  department_name?: string | null;
  mfa_enabled?: boolean;
  last_login?: string | null;
  created_at?: string | null;
  invitation_expires_at?: string | null;
};

type RbacRow = {
  user_id: string;
  full_name: string;
  role: string;
  days_overdue: number;
  last_role_reviewed_at: string | null;
};

type WardOcc = {
  id: string;
  name: string;
  ward_type: string;
  total_beds: number;
  occupied_beds: number;
  is_active: boolean;
};

type AuditEv = {
  action: string;
  user_name: string;
  timestamp: string;
};

function formatAuditTime(isoString: string): string {
  const date = new Date(isoString);
  const now = new Date();
  const isToday = date.toDateString() === now.toDateString();
  if (isToday) {
    return date.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit" });
  }
  const yesterday = new Date(now);
  yesterday.setDate(now.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return "yesterday";
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

const AUDIT_BADGE: Record<string, string> = {
  LOGIN: "bg-slate-100 text-slate-800",
  LOGOUT: "bg-slate-100 text-slate-800",
  MFA_VERIFY: "bg-slate-100 text-slate-800",
  VIEW: "bg-slate-100 text-slate-800",
  CREATE: "bg-sky-100 text-sky-900",
  RECORD_CREATED: "bg-sky-100 text-sky-900",
  UPDATE: "bg-amber-100 text-amber-900",
  RECORD_AMENDED: "bg-amber-100 text-amber-900",
  ROLE_CHANGE: "bg-amber-100 text-amber-900",
  ROLE_CHANGED: "bg-amber-100 text-amber-900",
  ACCOUNT_LOCKOUT: "bg-red-100 text-red-900",
  LOGIN_FAILED: "bg-red-100 text-red-900",
  EMERGENCY_ACCESS: "bg-red-100 text-red-900",
  BREAK_GLASS: "bg-red-100 text-red-900",
};

function relAgo(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  const diff = Date.now() - d.getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

function inviteDaysLeft(iso?: string | null): { text: string; tone: "green" | "amber" | "red" } {
  if (!iso) return { text: "—", tone: "amber" };
  const exp = new Date(iso).getTime();
  const daysLeft = Math.ceil((exp - Date.now()) / (1000 * 60 * 60 * 24));
  if (daysLeft <= 0) return { text: "Expired", tone: "red" };
  if (daysLeft <= 2) return { text: `${daysLeft}d left`, tone: "amber" };
  return { text: `${daysLeft}d left`, tone: "green" };
}

function rbacBadge(days: number): { text: string; cls: string } {
  if (days >= 90) return { text: `${days}d overdue`, cls: "bg-red-100 text-red-900" };
  if (days >= 70) return { text: `${days}d`, cls: "bg-amber-100 text-amber-900" };
  return { text: `${days}d`, cls: "bg-slate-100 text-slate-700" };
}

export function HospitalAdminDashboard({
  metrics,
  loading,
}: {
  metrics: Record<string, unknown>;
  loading: boolean;
}) {
  const api = useApi();
  const toast = useToast();
  const router = useRouter();
  const [staff, setStaff] = useState<HaUser[]>([]);
  const [rbacRows, setRbacRows] = useState<RbacRow[]>([]);
  const [wards, setWards] = useState<WardOcc[]>([]);
  const [actionKey, setActionKey] = useState<string | null>(null);

  const loadAux = useCallback(async () => {
    try {
      const u = await api.get<{ data: HaUser[] }>("/admin/users?ordering=-last_login&limit=5");
      setStaff(Array.isArray(u?.data) ? u.data : []);
    } catch {
      setStaff([]);
    }
    try {
      const r = await api.get<{ data: RbacRow[] }>("/admin/rbac-review");
      const rows = Array.isArray(r?.data) ? r.data : [];
      setRbacRows(rows.filter((x) => x.days_overdue >= 70).slice(0, 5));
    } catch {
      setRbacRows([]);
    }
    try {
      const w = await api.get<{ data: WardOcc[] }>("/admin/wards/occupancy");
      setWards(Array.isArray(w?.data) ? w.data : []);
    } catch {
      setWards([]);
    }
  }, [api]);

  useEffect(() => {
    void loadAux();
  }, [loadAux]);

  const pendingList = useMemo(
    () => (Array.isArray(metrics.pending_invitations_list) ? metrics.pending_invitations_list : []) as Record<string, unknown>[],
    [metrics.pending_invitations_list]
  );

  const auditList = useMemo(
    () => (Array.isArray(metrics.recent_audit_events) ? metrics.recent_audit_events : []) as AuditEv[],
    [metrics.recent_audit_events]
  );

  const mNum = (k: string): number | undefined => {
    const v = metrics[k];
    return typeof v === "number" ? v : undefined;
  };

  const runAction = async (id: string, fn: () => Promise<void>) => {
    setActionKey(id);
    try {
      await fn();
      toast.success("Done");
      await loadAux();
      // eslint-disable-next-line @typescript-eslint/no-unused-vars
    } catch (e) {
      toast.error("Action failed");
    } finally {
      setActionKey(null);
    }
  };

  const staffSubtitle = (u: HaUser): string => {
    const role = u.role?.replace(/_/g, " ") ?? "";
    if (u.ward_name) return `${role} · ${u.ward_name}`;
    if (u.lab_unit_name) return `${role} · ${u.lab_unit_name}`;
    if (u.department_name) return `${role} · ${u.department_name}`;
    return role;
  };

  const staffBadge = (u: HaUser) => {
    if (u.account_status === "locked") return { label: "Locked", cls: "bg-red-100 text-red-800" };
    if (u.account_status === "pending") return { label: "Invite pending", cls: "bg-amber-100 text-amber-900" };
    if (u.account_status === "suspended") return { label: "Suspended", cls: "bg-red-100 text-red-800" };
    if (u.account_status === "active" && u.mfa_enabled === false) {
      return { label: "Pending MFA", cls: "bg-amber-100 text-amber-900" };
    }
    return { label: "Active", cls: "bg-emerald-100 text-emerald-900" };
  };

  const lockedCount = mNum("locked_accounts_count") ?? 0;

  return (
    <div className="space-y-8">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <StatCard
          label="Total patients"
          value={mNum("total_patients") ?? "—"}
          sub="Registered at hospital"
          accentColor="teal"
          loading={loading}
        />
        <StatCard
          label="Active staff"
          value={mNum("total_users") ?? "—"}
          sub={
            mNum("pending_invite_count") != null
              ? `${mNum("pending_invite_count")} pending invite`
              : undefined
          }
          accentColor="blue"
          loading={loading}
        />
        <StatCard
          label="Encounters today"
          value={mNum("encounters_today") ?? "—"}
          sub={
            mNum("encounters_in_consultation") != null
              ? `${mNum("encounters_in_consultation")} in progress`
              : undefined
          }
          accentColor="purple"
          loading={loading}
        />
        <StatCard
          label="Active admissions"
          value={mNum("admission_count") ?? "—"}
          sub={mNum("beds_available") != null ? `${mNum("beds_available")} beds available` : undefined}
          accentColor="amber"
          loading={loading}
        />
        <StatCard
          label="Locked accounts"
          value={mNum("locked_accounts_count") ?? "—"}
          sub={lockedCount > 0 ? "Needs admin action" : "All accounts OK"}
          accentColor="red"
          loading={loading}
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <div className="space-y-6 lg:col-span-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Staff — recent activity</CardTitle>
              <Link href="/admin/users" className="text-sm font-medium text-[#0B8A96] hover:underline">
                Manage all →
              </Link>
            </CardHeader>
            <CardContent className="space-y-0 divide-y divide-[#E2E8F0]">
              {staff.length === 0 ? (
                <p className="py-4 text-sm text-slate-500 dark:text-slate-500">No staff loaded.</p>
              ) : (
                staff.map((u) => {
                  const b = staffBadge(u);
                  const busy = actionKey === u.user_id;
                  return (
                    <div key={u.user_id} className="flex flex-wrap items-start justify-between gap-2 py-3 first:pt-0">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-slate-100">{u.full_name || u.email}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-500">{staffSubtitle(u)}</p>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${b.cls}`}>{b.label}</span>
                        {u.account_status === "active" ? (
                          <span className="text-xs text-slate-500 dark:text-slate-500">{relAgo(u.last_login)}</span>
                        ) : null}
                        {u.account_status === "active" && u.mfa_enabled === false ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() =>
                              void runAction(u.user_id, () => api.post(`/admin/users/${u.user_id}/reset-mfa`, {}))
                            }
                          >
                            {busy ? "…" : "Reset MFA"}
                          </Button>
                        ) : null}
                        {u.account_status === "locked" ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() =>
                              void runAction(u.user_id, () =>
                                api.patch(`/admin/users/${u.user_id}`, { account_status: "active" })
                              )
                            }
                          >
                            {busy ? "…" : "Unlock"}
                          </Button>
                        ) : null}
                        {u.account_status === "pending" ? (
                          <Button
                            size="sm"
                            variant="secondary"
                            disabled={busy}
                            onClick={() =>
                              void runAction(u.user_id, () => api.post(`/admin/users/${u.user_id}/resend-invite`, {}))
                            }
                          >
                            {busy ? "…" : "Resend"}
                          </Button>
                        ) : null}
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Ward occupancy</CardTitle>
              <Link href="/admin/facilities" className="text-sm font-medium text-[#0B8A96] hover:underline">
                Facility config →
              </Link>
            </CardHeader>
            <CardContent className="space-y-3">
              {wards.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-500">No ward data.</p>
              ) : (
                wards.map((w) => {
                  const total = w.total_beds || 0;
                  const occ = w.occupied_beds || 0;
                  const pct = total > 0 ? occ / total : 0;
                  const barColor = pct >= 1 ? "#E24B4A" : pct >= 0.75 ? "#EF9F27" : "#639922";
                  const full = pct >= 1 && total > 0;
                  return (
                    <div key={w.id}>
                      <div className="mb-1 flex justify-between text-sm">
                        <span className="font-medium text-slate-900 dark:text-slate-100">{w.name}</span>
                        <span className={full ? "font-semibold text-[#E24B4A]" : "text-slate-500 dark:text-slate-500"}>
                          {occ}/{total} beds{full ? " FULL" : ""}
                        </span>
                      </div>
                      <div className="h-2 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                        <div
                          className="h-full rounded-full transition-all"
                          style={{
                            width: `${Math.min(100, pct * 100)}%`,
                            backgroundColor: barColor,
                          }}
                        />
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-6 lg:col-span-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Pending invitations</CardTitle>
              <button
                type="button"
                className="text-sm font-medium text-[#0B8A96] hover:underline"
                onClick={() => router.push("/admin/users?action=invite")}
              >
                Invite staff →
              </button>
            </CardHeader>
            <CardContent className="space-y-0 divide-y divide-[#E2E8F0]">
              {pendingList.length === 0 ? (
                <p className="py-4 text-sm text-slate-500 dark:text-slate-500">No pending invitations.</p>
              ) : (
                pendingList.slice(0, 8).map((row) => {
                  const email = String(row.email ?? "");
                  const role = String(row.role ?? "").replace(/_/g, " ");
                  const exp = row.invitation_expires_at as string | undefined;
                  const created = row.created_at as string | undefined;
                  const iv = inviteDaysLeft(exp);
                  const busy = actionKey === String(row.user_id);
                  return (
                    <div key={String(row.user_id)} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-slate-100">{email}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-500">
                          {role}
                          {created ? ` · sent ${relAgo(created)}` : ""}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <span
                          className={`text-xs font-semibold ${
                            iv.tone === "red"
                              ? "text-red-600"
                              : iv.tone === "amber"
                                ? "text-amber-700"
                                : "text-emerald-700"
                          }`}
                        >
                          {iv.text}
                        </span>
                        <Button
                          size="sm"
                          variant="secondary"
                          disabled={busy}
                          onClick={() =>
                            void runAction(String(row.user_id), () =>
                              api.post(`/admin/users/${String(row.user_id)}/resend-invite`, {})
                            )
                          }
                        >
                          {busy ? "…" : "Resend"}
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">RBAC review due</CardTitle>
              <Link href="/admin/rbac-review" className="text-sm font-medium text-[#0B8A96] hover:underline">
                Review all →
              </Link>
            </CardHeader>
            <CardContent className="space-y-0 divide-y divide-[#E2E8F0]">
              {rbacRows.length === 0 ? (
                <p className="py-4 text-sm text-slate-500 dark:text-slate-500">No reviews overdue (70+ days).</p>
              ) : (
                rbacRows.map((r) => {
                  const badge = rbacBadge(r.days_overdue);
                  return (
                    <div key={r.user_id} className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0">
                      <div>
                        <p className="font-medium text-slate-900 dark:text-slate-100">{r.full_name}</p>
                        <p className="text-xs text-slate-500 dark:text-slate-500">{r.role.replace(/_/g, " ")}</p>
                      </div>
                      <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badge.cls}`}>{badge.text}</span>
                    </div>
                  );
                })
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg">Recent audit events</CardTitle>
              <Link href="/admin/audit-logs" className="text-sm font-medium text-[#0B8A96] hover:underline">
                View full log →
              </Link>
            </CardHeader>
            <CardContent>
              {auditList.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-500">No recent events.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {auditList.slice(0, 5).map((e, i) => {
                    const ac = String(e.action ?? "");
                    const badgeCls = AUDIT_BADGE[ac] ?? "bg-slate-100 text-slate-800";
                    return (
                      <li key={i} className="flex flex-wrap items-center gap-2">
                        <span className={`rounded px-2 py-0.5 text-xs font-semibold ${badgeCls}`}>{ac}</span>
                        <span className="text-slate-900 dark:text-slate-100">{e.user_name}</span>
                        <span className="ml-auto text-xs text-slate-500 dark:text-slate-500">{formatAuditTime(e.timestamp)}</span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
