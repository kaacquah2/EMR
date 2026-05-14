"use client";

import React, { useEffect, useMemo, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useAuth } from "@/lib/auth-context";
import { useDashboardMetrics } from "@/hooks/use-dashboard";
import { HospitalAdminDashboard } from "@/components/dashboard/hospital-admin/HospitalAdminDashboard";
import { useDashboardAnalytics } from "@/hooks/use-analytics";
import { useApi } from "@/hooks/use-api";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";

const roleDashboardLoading = (
  <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">
    Loading dashboard…
  </div>
);

const NurseWardDashboard = dynamic(
  () =>
    import("@/components/features/NurseWardDashboardEnhanced").then((m) => ({
      default: m.NurseWardDashboardEnhanced,
    })),
  { loading: () => roleDashboardLoading },
);
const LabDashboard = dynamic(
  () =>
    import("@/components/features/LabDashboard").then((m) => ({ default: m.LabDashboard })),
  { loading: () => roleDashboardLoading },
);
const ReceptionistAppointmentUI = dynamic(
  () =>
    import("@/components/features/ReceptionistAppointmentUI").then((m) => ({
      default: m.ReceptionistAppointmentUI,
    })),
  { loading: () => roleDashboardLoading },
);
const DoctorDashboard = dynamic(
  () =>
    import("@/components/features/DoctorDashboard").then((m) => ({
      default: m.DoctorDashboard,
    })),
  { loading: () => roleDashboardLoading },
);

const ANALYTICS_ROLES = ["super_admin", "hospital_admin", "doctor"];

type BreakGlassEntry = { created_at?: string | null };
type ChainIntegrityStatus = {
  status: "valid" | "invalid" | "unknown";
  last_checked_at: string | null;
  message?: string | null;
};

type ComplianceAlert = {
  id: string;
  severity: "info" | "warning" | "critical";
  title: string;
  detail?: string | null;
};

type HospitalRow = { hospital_id: string; name: string };
type OnboardingStatus = {
  hospital_id: string;
  completion_pct: number;
  missing_items: string[];
};

type PendingAssignments = {
  hospitals_no_admin: Array<{ hospital_id: string; hospital_name: string }>;
  pending_admin_invites: Array<{
    user_id: string;
    email: string;
    full_name: string;
    hospital_id: string | null;
    hospital_name: string | null;
    sent_at: string | null;
    expires_at: string | null;
  }>;
  pending_view_as_grants: Array<{
    access_id: string;
    hospital_id: string;
    hospital_name: string;
    super_admin_email: string;
    sent_at: string | null;
  }>;
};

export default function DashboardPage() {
  const { user, viewAsHospitalId } = useAuth();
  const { metrics, loading: metricsLoading } = useDashboardMetrics();
  const api = useApi();

  const [breakGlass7dCount, setBreakGlass7dCount] = useState<number | null>(null);
  const [chainIntegrity, setChainIntegrity] = useState<ChainIntegrityStatus | null>(null);
  const [chainIntegrityLoading, setChainIntegrityLoading] = useState(false);
  const [complianceAlerts, setComplianceAlerts] = useState<ComplianceAlert[] | null>(null);
  const [pendingAssignments, setPendingAssignments] = useState<PendingAssignments | null>(null);
  const [hospitals, setHospitals] = useState<HospitalRow[]>([]);
  const [onboarding, setOnboarding] = useState<Record<string, OnboardingStatus>>({});

  const from = new Date();
  from.setDate(from.getDate() - 30);
  const to = new Date();
  const analyticsEnabled = !!user?.role && ANALYTICS_ROLES.includes(user.role);
  const { data: analytics, loading: analyticsLoading } = useDashboardAnalytics(
    from.toISOString().slice(0, 10),
    to.toISOString().slice(0, 10),
    "day",
    analyticsEnabled
  );

  const role = user?.role ?? "";
  const viewAsActive = role === "super_admin" && !!viewAsHospitalId;

  // Helper functions for admin dashboards
  const m = (k: string): React.ReactNode => {
    const v = metrics[k];
    if (v === undefined || v === null) return "—";
    if (typeof v === "string" || typeof v === "number") return v;
    return String(v);
  };

  const mArr = (k: string) =>
    (Array.isArray(metrics[k]) ? metrics[k] : []) as Record<string, unknown>[];

  const mObj = (k: string) =>
    (typeof metrics[k] === "object" && metrics[k] !== null
      ? metrics[k]
      : {}) as Record<string, number>;

  const welcomeTitle = useMemo(() => {
    const h = new Date().getHours();
    const greeting =
      h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
    return `${greeting}, ${user?.full_name ?? ""}`;
  }, [user?.full_name]);

  const superAdminStatsGridCols = useMemo(() => {
    // 5 cards on super_admin (includes Break-glass 7d)
    return role === "super_admin" ? "lg:grid-cols-5" : "lg:grid-cols-4";
  }, [role]);

  useEffect(() => {
    if (role !== "super_admin") return;
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<{ data: BreakGlassEntry[] }>("/superadmin/break-glass-list-global");
        const rows = Array.isArray(res?.data) ? res.data : [];
        const cutoff = Date.now() - 7 * 24 * 60 * 60 * 1000;
        const count = rows.filter((e) => {
          const ts = e?.created_at ? Date.parse(String(e.created_at)) : NaN;
          return Number.isFinite(ts) && ts >= cutoff;
        }).length;
        if (!cancelled) setBreakGlass7dCount(count);
      } catch {
        if (!cancelled) setBreakGlass7dCount(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, role]);

  useEffect(() => {
    if (role !== "super_admin") return;
    let cancelled = false;
    (async () => {
      try {
        const s = await api.get<ChainIntegrityStatus>("/superadmin/audit-chain-integrity");
        if (!cancelled) setChainIntegrity(s ?? null);
      } catch {
        if (!cancelled) setChainIntegrity({ status: "unknown", last_checked_at: null, message: "Unable to load chain status" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, role]);

  useEffect(() => {
    if (role !== "super_admin") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get<{ data: ComplianceAlert[] }>("/superadmin/compliance-alerts");
        if (!cancelled) setComplianceAlerts(Array.isArray(r?.data) ? r.data : []);
      } catch {
        if (!cancelled) setComplianceAlerts([]);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, role]);

  useEffect(() => {
    if (role !== "super_admin") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get<PendingAssignments>("/superadmin/pending-hospital-admin-assignments");
        if (!cancelled) setPendingAssignments(r ?? null);
      } catch {
        if (!cancelled) setPendingAssignments({ hospitals_no_admin: [], pending_admin_invites: [], pending_view_as_grants: [] });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, role]);

  const resendAdminInvite = async (userId: string) => {
    if (role !== "super_admin") return;
    try {
      await api.post(`/admin/users/${encodeURIComponent(userId)}/resend-invite`, {});
      const r = await api.get<PendingAssignments>("/superadmin/pending-hospital-admin-assignments");
      setPendingAssignments(r ?? null);
    } catch {
      //
    }
  };

  useEffect(() => {
    if (role !== "super_admin") return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get<{ data: HospitalRow[] }>("/superadmin/hospitals");
        const hs = Array.isArray(r?.data) ? r.data : [];
        if (cancelled) return;
        setHospitals(hs);
        const next: Record<string, OnboardingStatus> = {};
        await Promise.all(
          hs.map(async (h) => {
            try {
              const s = await api.get<OnboardingStatus>(`/superadmin/hospital-onboarding?hospital_id=${encodeURIComponent(h.hospital_id)}`);
              next[h.hospital_id] = s;
            } catch {
              next[h.hospital_id] = { hospital_id: h.hospital_id, completion_pct: 0, missing_items: ["Unable to load"] };
            }
          })
        );
        if (!cancelled) setOnboarding(next);
      } catch {
        if (!cancelled) {
          setHospitals([]);
          setOnboarding({});
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, role]);

  const validateChainNow = async () => {
    if (role !== "super_admin") return;
    setChainIntegrityLoading(true);
    try {
      const s = await api.post<ChainIntegrityStatus>("/superadmin/audit-chain-integrity/validate", {});
      setChainIntegrity(s ?? null);
    } catch {
      setChainIntegrity({ status: "unknown", last_checked_at: null, message: "Validation failed" });
    } finally {
      setChainIntegrityLoading(false);
    }
  };

  if (!user) return null;

  if (!user) return null;

  const renderDashboardContent = () => {
    // Route to role-specific optimized dashboards (Phase 3 UI components)
    if (role === "nurse") {
      return <NurseWardDashboard />;
    }

    if (role === "lab_technician") {
      return <LabDashboard />;
    }

    if (role === "receptionist") {
      return <ReceptionistAppointmentUI />;
    }

    if (role === "doctor") {
      return <DoctorDashboard />;
    }

    // Admin dashboard (super_admin and hospital_admin roles)
    return (
      <>
        {/* Super Admin Dashboard Stats */}
        {role === "super_admin" && (
          <div className={`grid gap-4 md:grid-cols-2 ${superAdminStatsGridCols}`}>
            <Card accent="teal">
              <CardContent className="pt-6">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-500">
                  Total Hospitals
                </p>
                <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {m("hospitals_count")}
                </p>
              </CardContent>
            </Card>
            <Card accent="navy">
              <CardContent className="pt-6">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-500">
                  Total Active Users
                </p>
                <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {m("total_users")}
                </p>
              </CardContent>
            </Card>
            <Card accent="green">
              <CardContent className="pt-6">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-500">
                  Total Patients
                </p>
                <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {m("total_patients")}
                </p>
              </CardContent>
            </Card>
            <Card accent="amber">
              <CardContent className="pt-6">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-500">DB Status</p>
                <p className="mt-1 flex items-center gap-2">
                  {typeof metrics.db_status === "string" ? (
                    <span
                      className={`inline-block h-3 w-3 rounded-full ${
                        metrics.db_status === "ok" ? "bg-green-500" : "bg-red-500"
                      }`}
                      aria-hidden
                    />
                  ) : (
                    <span
                      className="inline-block h-3 w-3 rounded-full bg-slate-300"
                      aria-hidden
                    />
                  )}
                  <span className="font-semibold text-slate-900 dark:text-slate-100">
                    {metrics.db_status === "ok"
                      ? "OK"
                      : typeof metrics.db_status === "string"
                        ? "Error"
                        : "Unknown"}
                  </span>
                </p>
              </CardContent>
            </Card>
            <Card accent="amber">
              <CardContent className="pt-6">
                <p className="text-sm font-medium text-slate-500 dark:text-slate-500">
                  Break-glass events (7d)
                </p>
                <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">
                  {breakGlass7dCount === null ? "—" : breakGlass7dCount}
                </p>
              </CardContent>
            </Card>
          </div>
        )}

        {role === "hospital_admin" && (
          <HospitalAdminDashboard metrics={metrics} loading={metricsLoading} />
        )}

        {/* Super Admin - audit + compliance + assignments + quick links */}
        {role === "super_admin" && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Recent Audit Events</CardTitle>
              </CardHeader>
              <CardContent>
                {role === "super_admin" && (
                  <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-900 px-3 py-2 text-sm">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-block h-2.5 w-2.5 rounded-full ${
                          chainIntegrity?.status === "valid"
                            ? "bg-green-500"
                            : chainIntegrity?.status === "invalid"
                              ? "bg-red-500"
                              : "bg-slate-300"
                        }`}
                        aria-hidden
                      />
                      <span className="font-medium text-slate-900 dark:text-slate-100">Chain integrity</span>
                      <span className="text-slate-500 dark:text-slate-500">
                        {chainIntegrity?.status === "valid"
                          ? "Valid"
                          : chainIntegrity?.status === "invalid"
                            ? "Tamper flags"
                            : "Unknown"}
                        {chainIntegrity?.last_checked_at ? ` — last checked ${chainIntegrity.last_checked_at.slice(0, 19)}` : ""}
                      </span>
                    </div>
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => void validateChainNow()}
                      disabled={chainIntegrityLoading}
                    >
                      {chainIntegrityLoading ? "Validating..." : "Validate now →"}
                    </Button>
                  </div>
                )}
                <div className="max-h-48 overflow-y-auto text-sm">
                  {mArr("recent_audit_events").length === 0 ? (
                    <p className="text-slate-500 dark:text-slate-500">No recent events.</p>
                  ) : (
                    <ul className="space-y-1">
                      {mArr("recent_audit_events")
                        .slice(0, 10)
                        .map((e: Record<string, unknown>, i: number) => (
                          <li key={i} className="flex flex-wrap gap-2 font-mono text-xs">
                            <span className="text-slate-500 dark:text-slate-500">
                              {(e.timestamp as string)?.slice(0, 19)}
                            </span>
                            <span>{e.user_name as string}</span>
                            <span className="rounded bg-slate-200 dark:bg-slate-800 px-1.5 py-0.5">
                              {e.action as string}
                            </span>
                          </li>
                        ))}
                    </ul>
                  )}
                </div>
                <Link href="/admin/audit-logs" className="mt-2 inline-block">
                  <Button variant="secondary" size="sm">
                    View full log
                  </Button>
                </Link>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Compliance alerts</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="max-h-56 overflow-y-auto text-sm">
                  {(complianceAlerts ?? []).length === 0 ? (
                    <p className="text-slate-500 dark:text-slate-500">No compliance alerts.</p>
                  ) : (
                    <ul className="space-y-2">
                      {(complianceAlerts ?? []).slice(0, 10).map((a) => (
                        <li key={a.id} className="rounded border border-slate-200 dark:border-slate-800 p-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-medium text-slate-900 dark:text-slate-100">{a.title}</span>
                            <span
                              className={`rounded px-2 py-0.5 text-xs font-semibold ${
                                a.severity === "critical"
                                  ? "bg-red-100 text-red-800"
                                  : a.severity === "warning"
                                    ? "bg-amber-100 text-amber-800"
                                    : "bg-slate-100 text-slate-700"
                              }`}
                            >
                              {a.severity.toUpperCase()}
                            </span>
                          </div>
                          {a.detail ? <p className="mt-1 text-slate-500 dark:text-slate-500">{a.detail}</p> : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
                <div className="mt-2 flex flex-wrap gap-2">
                  <Link href="/superadmin/cross-facility-activity-log">
                    <Button variant="secondary" size="sm">
                      Cross-Facility Monitor →
                    </Button>
                  </Link>
                  <Link href="/superadmin/hospitals">
                    <Button variant="secondary" size="sm">
                      Hospitals →
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>

            {role === "super_admin" && (
              <Card>
                <CardHeader>
                  <CardTitle>Pending Hospital Admin Assignments</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="max-h-64 overflow-y-auto text-sm">
                    {((pendingAssignments?.hospitals_no_admin ?? []).length === 0 &&
                      (pendingAssignments?.pending_admin_invites ?? []).length === 0 &&
                      (pendingAssignments?.pending_view_as_grants ?? []).length === 0) ? (
                      <p className="text-slate-500 dark:text-slate-500">No pending assignments.</p>
                    ) : (
                      <ul className="space-y-2">
                        {(pendingAssignments?.hospitals_no_admin ?? []).slice(0, 20).map((h) => (
                          <li key={`hna:${h.hospital_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 dark:border-slate-800 p-2">
                            <span className="text-slate-900 dark:text-slate-100">
                              <strong>{h.hospital_name}</strong> — No admin assigned
                            </span>
                            <Link href="/admin/users">
                              <Button size="sm">Invite Admin →</Button>
                            </Link>
                          </li>
                        ))}
                        {(pendingAssignments?.pending_admin_invites ?? []).slice(0, 20).map((u) => (
                          <li key={`pai:${u.user_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 dark:border-slate-800 p-2">
                            <span className="text-slate-900 dark:text-slate-100">
                              <strong>{u.email}</strong>
                              {" — "}
                              {u.hospital_name ?? "—"}
                              {" · sent "}
                              {u.sent_at ? u.sent_at.slice(0, 10) : "—"}
                            </span>
                            <Button size="sm" variant="secondary" onClick={() => void resendAdminInvite(u.user_id)}>
                              Resend
                            </Button>
                          </li>
                        ))}
                        {(pendingAssignments?.pending_view_as_grants ?? []).slice(0, 20).map((g) => (
                          <li key={`pvg:${g.access_id}`} className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 dark:border-slate-800 p-2">
                            <span className="text-slate-900 dark:text-slate-100">
                              Grant sent to <strong>{g.super_admin_email}</strong> for{" "}
                              <strong>{g.hospital_name}</strong>
                              {g.sent_at ? ` — sent ${g.sent_at.slice(0, 10)}` : ""}
                            </span>
                            <span className="text-xs font-semibold text-slate-500 dark:text-slate-500">Awaiting activation</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            <Card>
              <CardHeader>
                <CardTitle>Admin Quick Links</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-3">
                <Link href="/superadmin/hospitals">
                  <Button>Hospitals</Button>
                </Link>
                <Link href="/superadmin/cross-facility-activity-log">
                  <Button variant="secondary">Cross-Facility Monitor</Button>
                </Link>
                <Link href="/admin/audit-logs">
                  <Button variant="secondary">Audit Logs</Button>
                </Link>
              </CardContent>
            </Card>
          </>
        )}

        {(role === "hospital_admin" || viewAsActive) && (
          <Card>
            <CardHeader>
              <CardTitle>Today&apos;s Appointments Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-4 text-sm">
                <span>
                  Scheduled:{" "}
                  <strong>{mObj("appointment_summary").scheduled ?? 0}</strong>
                </span>
                <span>
                  Checked in:{" "}
                  <strong>{mObj("appointment_summary").checked_in ?? 0}</strong>
                </span>
                <span>
                  Completed:{" "}
                  <strong>{mObj("appointment_summary").completed ?? 0}</strong>
                </span>
                <span>
                  Cancelled:{" "}
                  <strong>{mObj("appointment_summary").cancelled ?? 0}</strong>
                </span>
                <span>
                  No-show:{" "}
                  <strong>{mObj("appointment_summary").no_show ?? 0}</strong>
                </span>
              </div>
            </CardContent>
          </Card>
        )}

        {role === "hospital_admin" && (
          <>
            <Card>
              <CardHeader>
                <CardTitle>Admin Quick Links</CardTitle>
              </CardHeader>
              <CardContent className="flex flex-wrap gap-3">
                <Link href="/admin/users">
                  <Button>Manage Users</Button>
                </Link>
                <Link href="/admin/audit-logs">
                  <Button variant="secondary">View Audit Log</Button>
                </Link>
                <Link href="/admin/reports">
                  <Button variant="secondary">View Reports</Button>
                </Link>
              </CardContent>
            </Card>
          </>
        )}

        {/* Super Admin - Onboarding status */}
        {role === "super_admin" && (
          <Card>
            <CardHeader>
              <CardTitle>Onboarding status</CardTitle>
            </CardHeader>
            <CardContent>
              {hospitals.length === 0 ? (
                <p className="text-sm text-slate-500 dark:text-slate-500">No hospitals.</p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-200 dark:border-slate-800">
                        <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Hospital</th>
                        <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Completion</th>
                        <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Missing items</th>
                      </tr>
                    </thead>
                    <tbody>
                      {hospitals.map((h) => {
                        const s = onboarding[h.hospital_id];
                        const pct = s?.completion_pct ?? 0;
                        const missing = s?.missing_items ?? [];
                        return (
                          <tr key={h.hospital_id} className="border-b border-slate-100 dark:border-slate-900">
                            <td className="py-2">{h.name}</td>
                            <td className="py-2">
                              <span
                                className={`rounded px-2 py-0.5 text-xs font-semibold ${
                                  pct >= 80
                                    ? "bg-green-100 text-green-800"
                                    : pct >= 40
                                      ? "bg-amber-100 text-amber-800"
                                      : "bg-red-100 text-red-800"
                                }`}
                              >
                                {pct}%
                              </span>
                            </td>
                            <td className="py-2 text-slate-500 dark:text-slate-500">
                              {missing.length === 0 ? "—" : missing.slice(0, 4).join(", ")}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Analytics (Admin roles) */}
        {(role === "super_admin" || role === "hospital_admin") && (
          <Card>
            <CardHeader>
              <CardTitle>Analytics (last 30 days)</CardTitle>
            </CardHeader>
            <CardContent>
              {analyticsLoading ? (
                <p className="text-slate-500 dark:text-slate-500">Loading analytics...</p>
              ) : analytics ? (
                <div className="space-y-3">
                  <p className="text-sm text-slate-500 dark:text-slate-500">
                    Patients registered: <strong>{analytics.patients_total}</strong> |
                    Encounters: <strong>{analytics.encounters_total}</strong>
                  </p>
                  {analytics.patients_by_day &&
                    analytics.patients_by_day.length > 0 && (
                      <div className="max-h-40 overflow-y-auto">
                        <table className="w-full text-sm">
                          <thead>
                            <tr className="border-b border-slate-200 dark:border-slate-800">
                              <th className="py-1 text-left text-slate-500 dark:text-slate-500">
                                Date
                              </th>
                              <th className="py-1 text-right text-slate-500 dark:text-slate-500">
                                Patients
                              </th>
                              <th className="py-1 text-right text-slate-500 dark:text-slate-500">
                                Encounters
                              </th>
                            </tr>
                          </thead>
                          <tbody>
                            {(analytics.patients_by_day || [])
                              .slice(-14)
                              .reverse()
                              .map((row) => {
                                const enc = (
                                  analytics.encounters_by_day || []
                                ).find((e) => e.date === row.date);
                                return (
                                  <tr key={row.date} className="border-b border-slate-100 dark:border-slate-900">
                                    <td className="py-1">{row.date}</td>
                                    <td className="py-1 text-right">{row.count}</td>
                                    <td className="py-1 text-right">
                                      {enc?.count ?? 0}
                                    </td>
                                  </tr>
                                );
                              })}
                          </tbody>
                        </table>
                      </div>
                    )}
                </div>
              ) : (
                <p className="text-slate-500 dark:text-slate-500">No analytics available.</p>
              )}
            </CardContent>
          </Card>
        )}
      </>
    );
  };

  return (
    <div className="space-y-8">
      <Breadcrumbs items={[{ label: "Dashboard" }]} />
      {/* Page Header (Global) */}
      <div className="page-header">
        <h1 className="page-header-title">{welcomeTitle}</h1>
        <p className="page-header-desc">
          {user.hospital_name ??
            (user.role === "super_admin" && !user.hospital_id
              ? "All hospitals"
              : "Your hospital")}
        </p>
      </div>

      {renderDashboardContent()}
    </div>
  );
}
