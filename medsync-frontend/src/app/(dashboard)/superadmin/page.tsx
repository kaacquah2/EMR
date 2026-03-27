"use client";

import React, { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { DASHBOARD_HEALTH_ROWS, runbookHref } from "@/lib/ops-runbooks";
import { collectHospitalNamesFromComplianceAlerts, downloadHospitalNamesCsv } from "@/lib/export-compliance-csv";

type ServiceStatus = { status?: string; latency_ms?: number; response_ms?: number; last_run?: string; last_validated?: string };
type HealthResponse = {
  services?: {
    api?: ServiceStatus;
    database?: ServiceStatus;
    redis?: ServiceStatus;
    ai_inference?: ServiceStatus;
    kms?: ServiceStatus;
    audit_chain?: ServiceStatus;
    backup?: ServiceStatus;
  };
};

type AiStatusResponse = {
  status: "online" | "degraded" | "offline";
  analyses_24h: number;
  avg_response_ms: number | null;
  target_response_ms: number;
  uptime_7d_pct: number | null;
  modules: Record<string, string>;
};

type HospitalRow = {
  hospital_id: string;
  id: string;
  name: string;
  region: string;
  staff_count: number;
  patient_count: number;
  hospital_admin_count: number;
  onboarding_pct: number;
  is_active?: boolean;
};

type OnboardingRow = { hospital_id: string; name: string; completion_pct: number; missing_items: string[] };
type ComplianceAlert = { id: string; severity: "info" | "warning" | "critical"; title: string; detail: string };
type AuditRow = {
  log_id?: string;
  user: string;
  action: string;
  timestamp: string;
  hospital?: string | null;
  resource_type?: string | null;
  ip_address?: string;
};
type PendingAdminGrants = {
  hospitals_no_admin: Array<{ hospital_id: string; hospital_name: string }>;
  pending_invites: Array<{ user_id: string; email: string; hospital_name: string | null; expires_soon?: boolean }>;
  pending_grants: Array<{ access_id: string; super_admin_email: string; hospital_name: string }>;
};

type DashboardBundle = {
  generated_at: string;
  health: HealthResponse;
  ai_status: AiStatusResponse;
  hospitals: { data: HospitalRow[] };
  onboarding: { data: OnboardingRow[] };
  compliance_alerts: { data: ComplianceAlert[] };
  pending_admin_grants: PendingAdminGrants;
  audit_logs_preview: { data: AuditRow[] };
  break_glass_summary_7d: { total: number; unreviewed: number };
};

function statAccent(accent: "teal" | "blue" | "purple" | "amber" | "green" | "red") {
  switch (accent) {
    case "teal":
      return "border-t-teal-500";
    case "blue":
      return "border-t-blue-500";
    case "purple":
      return "border-t-purple-500";
    case "amber":
      return "border-t-amber-500";
    case "green":
      return "border-t-emerald-500";
    case "red":
      return "border-t-red-500";
  }
}

function dot(status: "ok" | "warn" | "down") {
  if (status === "ok") return "bg-emerald-500";
  if (status === "warn") return "bg-amber-500";
  return "bg-red-500";
}

function healthToLevel(s?: string): "ok" | "warn" | "down" {
  const v = (s || "").toLowerCase();
  if (v === "ok") return "ok";
  if (v === "slow" || v === "degraded" || v === "warn") return "warn";
  return "down";
}

function fmtInt(n: number | undefined | null) {
  if (typeof n !== "number" || !Number.isFinite(n)) return "—";
  return String(Math.trunc(n));
}

/** Avoid misleading "0ms" when the backend omits latency or reports zero before sampling. */
function fmtLatencyMs(ms: number | undefined | null) {
  if (typeof ms !== "number" || !Number.isFinite(ms) || ms <= 0) return null;
  return `${Math.trunc(ms)}ms`;
}

function ComplianceAlertDetail({ text }: { text: string }) {
  const parts = text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
  if (parts.length <= 1) {
    return <p className="mt-1 text-[#64748B]">{text}</p>;
  }
  return (
    <ul className="mt-2 max-h-40 list-inside list-disc space-y-1 overflow-y-auto text-[#64748B] [scrollbar-gutter:stable]">
      {parts.map((p, i) => (
        <li key={`${i}-${p.slice(0, 48)}`} className="text-sm leading-snug">
          {p}
        </li>
      ))}
    </ul>
  );
}

export default function SuperAdminPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthRefreshedAt, setHealthRefreshedAt] = useState<string | null>(null);
  const [aiStatus, setAiStatus] = useState<AiStatusResponse | null>(null);
  const [hospitals, setHospitals] = useState<HospitalRow[]>([]);
  const [onboarding, setOnboarding] = useState<OnboardingRow[]>([]);
  const [complianceAlerts, setComplianceAlerts] = useState<ComplianceAlert[]>([]);
  const [pending, setPending] = useState<PendingAdminGrants | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditRow[]>([]);
  const [breakGlass7d, setBreakGlass7d] = useState<{ total: number; unreviewed: number } | null>(null);

  const loadDashboard = useCallback(async () => {
    if (user?.role !== "super_admin") return;
    try {
      const b = await api.get<DashboardBundle>("/superadmin/dashboard-bundle");
      setHealth(b.health ?? null);
      setHealthRefreshedAt(new Date().toISOString());
      setAiStatus(b.ai_status ?? null);
      setHospitals(Array.isArray(b.hospitals?.data) ? b.hospitals.data : []);
      setOnboarding(Array.isArray(b.onboarding?.data) ? b.onboarding.data : []);
      setComplianceAlerts((Array.isArray(b.compliance_alerts?.data) ? b.compliance_alerts.data : []).slice(0, 5));
      setPending(b.pending_admin_grants ?? null);
      setAuditLogs(Array.isArray(b.audit_logs_preview?.data) ? b.audit_logs_preview.data : []);
      const s = b.break_glass_summary_7d;
      if (s && typeof s.total === "number" && typeof s.unreviewed === "number") {
        setBreakGlass7d({ total: s.total, unreviewed: s.unreviewed });
      } else {
        setBreakGlass7d(null);
      }
    } catch {
      setHealth(null);
      setHealthRefreshedAt(new Date().toISOString());
      setAiStatus(null);
      setHospitals([]);
      setOnboarding([]);
      setComplianceAlerts([]);
      setPending(null);
      setAuditLogs([]);
      setBreakGlass7d(null);
    }
  }, [api, user?.role]);

  useEffect(() => {
    if (user?.role !== "super_admin") return;
    // Defer so the effect body does not synchronously invoke code that updates state (react-hooks/set-state-in-effect).
    const tid = window.setTimeout(() => {
      void loadDashboard();
    }, 0);
    const intervalId = window.setInterval(() => {
      void loadDashboard();
    }, 60_000);
    return () => {
      clearTimeout(tid);
      clearInterval(intervalId);
    };
  }, [user?.role, loadDashboard]);

  const canAccess = user?.role === "super_admin";
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  const hospitalTotals = useMemo(() => {
    const totalHospitals = hospitals.length;
    const totalUsers = hospitals.reduce((acc, h) => acc + (h.staff_count || 0), 0);
    const totalPatients = hospitals.reduce((acc, h) => acc + (h.patient_count || 0), 0);
    const onboardingNeedsAttention = hospitals.filter((h) => (h.onboarding_pct ?? 0) < 60).length;
    return { totalHospitals, totalUsers, totalPatients, onboardingNeedsAttention };
  }, [hospitals]);

  const apiSvc = health?.services?.api;
  const apiLevel = healthToLevel(apiSvc?.status);
  const apiCardAccent = apiLevel === "down" ? "red" : apiLevel === "warn" ? "amber" : "green";
  const apiLatencyPretty = fmtLatencyMs(apiSvc?.latency_ms);

  const anyDown = useMemo(() => {
    const s = health?.services || {};
    const keys = Object.keys(s) as Array<keyof NonNullable<HealthResponse["services"]>>;
    if (keys.length === 0) return false;
    return keys.some((k) => healthToLevel(s[k]?.status) === "down");
  }, [health]);

  const downServiceLabels = useMemo(() => {
    const s = health?.services ?? {};
    // If health payload is missing (e.g. dashboard bundle failed to load), do not mis-report every service as down.
    if (Object.keys(s).length === 0) return [];
    return DASHBOARD_HEALTH_ROWS.filter(({ key }) => healthToLevel(s[key]?.status) === "down").map(({ label }) => label);
  }, [health]);

  const complianceHospitalNamesForCsv = useMemo(
    () => collectHospitalNamesFromComplianceAlerts(complianceAlerts),
    [complianceAlerts]
  );

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

  return (
    <div className="space-y-6">
      {downServiceLabels.length > 0 && (
        <div
          className="flex flex-wrap items-start justify-between gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900"
          role="status"
        >
          <div>
            <span className="font-semibold">Critical: {downServiceLabels.length} service(s) down</span>
            <span className="mt-1 block text-red-800/90">{downServiceLabels.join(" · ")}</span>
            {downServiceLabels.some((l) => l.includes("Redis")) ? (
              <span className="mt-1 block text-xs text-red-800/80">
                Background jobs and caching may be affected until Redis/Celery is healthy.
              </span>
            ) : null}
          </div>
          <Link className="shrink-0 font-medium text-red-800 underline underline-offset-2" href="/superadmin/system-health">
            Troubleshoot →
          </Link>
        </div>
      )}

      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-sora text-2xl font-bold text-[#0F172A]">Dashboard</h1>
          <p className="text-sm text-[#64748B]">Network-wide visibility and controls</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card className={`border-t-4 p-5 ${statAccent("teal")}`}>
          <div className="text-sm text-[#64748B]">Total hospitals</div>
          <div className="mt-2 text-3xl font-semibold text-[#0F172A]">{fmtInt(hospitalTotals.totalHospitals)}</div>
          <div className="mt-1 text-sm text-[#64748B]">{fmtInt(hospitalTotals.onboardingNeedsAttention)} onboarding need attention</div>
        </Card>
        <Card className={`border-t-4 p-5 ${statAccent("blue")}`}>
          <div className="text-sm text-[#64748B]">Total active users</div>
          <div className="mt-2 text-3xl font-semibold text-[#0F172A]">{fmtInt(hospitalTotals.totalUsers)}</div>
          <div className="mt-1 text-sm text-[#64748B]">Network-wide</div>
        </Card>
        <Card className={`border-t-4 p-5 ${statAccent("purple")}`}>
          <div className="text-sm text-[#64748B]">Total patients</div>
          <div className="mt-2 text-3xl font-semibold text-[#0F172A]">{fmtInt(hospitalTotals.totalPatients)}</div>
          <div className="mt-1 text-sm text-[#64748B]">Network-wide</div>
        </Card>
        <Card className={`border-t-4 p-5 ${statAccent("green")}`}>
          <div className="text-sm text-[#64748B]">Break-glass events (7d)</div>
          <div className="mt-2 text-3xl font-semibold text-[#0F172A]">{fmtInt(breakGlass7d?.total ?? 0)}</div>
          <div className="mt-1 text-sm text-[#64748B]">{fmtInt(breakGlass7d?.unreviewed ?? 0)} need review</div>
        </Card>
        <Card className={`border-t-4 p-5 ${statAccent(apiCardAccent)}`}>
          <div className="text-sm text-[#64748B]">Backend API</div>
          <div className="mt-2 flex items-center gap-2 text-lg font-semibold text-[#0F172A]">
            <span className={`h-2.5 w-2.5 rounded-full ${dot(apiLevel)}`} />
            {apiLevel === "down" ? "Down" : apiLevel === "warn" ? "Degraded" : "Running"}
          </div>
          <div className="mt-1 text-sm text-[#64748B]">
            {apiLatencyPretty ? `${apiLatencyPretty} avg` : "Latency not sampled"}
          </div>
        </Card>
        <Card
          className={`border-t-4 p-5 ${statAccent(
            aiStatus?.status === "offline" ? "red" : aiStatus?.status === "degraded" ? "amber" : "green"
          )}`}
        >
          <div className="text-sm text-[#64748B]">AI service</div>
          <div className="mt-2 flex items-center gap-2 text-lg font-semibold text-[#0F172A]">
            <span className={`h-2.5 w-2.5 rounded-full ${dot(aiStatus?.status === "offline" ? "down" : aiStatus?.status === "degraded" ? "warn" : "ok")}`} />
            {aiStatus?.status ? (aiStatus.status === "offline" ? "Offline" : aiStatus.status === "degraded" ? "Degraded" : "Online") : "—"}
          </div>
          <div className="mt-1 text-sm text-[#64748B]">
            {typeof aiStatus?.uptime_7d_pct === "number" && Number.isFinite(aiStatus.uptime_7d_pct)
              ? `${fmtInt(aiStatus.uptime_7d_pct)}% uptime (7d)`
              : "Uptime not measured (7d)"}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className={`p-6 lg:col-span-2 ${anyDown ? "border border-red-200" : ""}`}>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-sora text-lg font-semibold text-[#0F172A]">System health</h2>
              <p className="text-sm text-[#64748B]">
                Last refreshed {healthRefreshedAt ? healthRefreshedAt.slice(11, 16) : "—"}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void loadDashboard()}
                className="text-sm font-medium text-[#0F172A] underline-offset-2 hover:underline"
              >
                Refresh
              </button>
              <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/system-health">
                View all →
              </Link>
            </div>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            {DASHBOARD_HEALTH_ROWS.map(({ label, key }) => {
              const svc = health?.services?.[key];
              const level = healthToLevel(svc?.status);
              const rawMs = svc?.latency_ms ?? svc?.response_ms;
              const msLabel = fmtLatencyMs(rawMs ?? null);
              return (
                <div
                  key={key}
                  className="flex flex-wrap items-center justify-between gap-2 rounded border border-[#E2E8F0] px-3 py-2"
                >
                  <div className="flex min-w-0 flex-1 items-center gap-2">
                    <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${dot(level)}`} />
                    <span className="font-medium text-[#0F172A]">{label}</span>
                    <span className="text-[#64748B]">{level === "down" ? "Down" : level === "warn" ? "Degraded" : "OK"}</span>
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    <span className="text-[#64748B]">{msLabel ?? "—"}</span>
                    <Link
                      href={runbookHref(key)}
                      className="text-xs font-medium text-[#2563EB] hover:underline"
                      target={process.env.NEXT_PUBLIC_OPS_DOCS_BASE ? "_blank" : undefined}
                      rel={process.env.NEXT_PUBLIC_OPS_DOCS_BASE ? "noopener noreferrer" : undefined}
                    >
                      Docs
                    </Link>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>

        <div className="space-y-4">
          <Card className="p-6">
            <div className="flex items-center justify-between gap-3">
              <h2 className="font-sora text-lg font-semibold text-[#0F172A]">AI integration</h2>
              <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/ai-integration">Config →</Link>
            </div>
            <div className="mt-4 grid grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-[#64748B]">Status</div>
                <div className="mt-1 font-semibold text-[#0F172A]">{aiStatus?.status ?? "—"}</div>
              </div>
              <div>
                <div className="text-[#64748B]">Analyses</div>
                <div className="mt-1 font-semibold text-[#0F172A]">{fmtInt(aiStatus?.analyses_24h ?? 0)}</div>
                <div className="text-xs text-[#64748B]">(24h)</div>
              </div>
              <div>
                <div className="text-[#64748B]">Avg response</div>
                <div className="mt-1 font-semibold text-[#0F172A]">
                  {typeof aiStatus?.avg_response_ms === "number" && Number.isFinite(aiStatus.avg_response_ms)
                    ? `${fmtInt(aiStatus.avg_response_ms)}ms`
                    : "—"}
                </div>
                <div className="text-xs text-[#64748B]">
                  Target {fmtInt(aiStatus?.target_response_ms ?? 0)}ms ·{" "}
                  {typeof aiStatus?.avg_response_ms !== "number" || !Number.isFinite(aiStatus.avg_response_ms)
                    ? "Not measured"
                    : aiStatus.avg_response_ms > aiStatus.target_response_ms
                      ? "↑ Above target"
                      : "Within target"}
                </div>
              </div>
            </div>
            <div className="mt-4 text-sm text-[#64748B]">
              {aiStatus?.modules
                ? Object.entries(aiStatus.modules).map(([k, v]) => (
                    <div key={k} className="flex items-center justify-between">
                      <span className="capitalize">{k.replaceAll("_", " ")}</span>
                      <span>{v}</span>
                    </div>
                  ))
                : "—"}
            </div>
          </Card>

          <Card className="p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Compliance alerts</h2>
              <div className="flex flex-wrap items-center gap-3">
                {complianceHospitalNamesForCsv.length > 0 ? (
                  <button
                    type="button"
                    onClick={() => downloadHospitalNamesCsv(complianceHospitalNamesForCsv)}
                    className="text-sm font-medium text-[#0F172A] underline-offset-2 hover:underline"
                  >
                    Export hospital names (CSV)
                  </button>
                ) : null}
                <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/compliance-alerts">
                  View all →
                </Link>
              </div>
            </div>
            <div className="mt-4 space-y-2 text-sm">
              {complianceAlerts.length === 0 ? (
                <div className="text-[#64748B]">No alerts.</div>
              ) : (
                complianceAlerts.map((a) => {
                  const sev = a.severity === "critical" ? "danger" : a.severity === "warning" ? "warning" : "secondary";
                  return (
                    <div key={a.id} className="flex items-start justify-between gap-3 rounded border border-[#E2E8F0] px-3 py-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <Badge variant={sev as never}>{a.severity}</Badge>
                          <span className="font-medium text-[#0F172A]">{a.title}</span>
                        </div>
                        <ComplianceAlertDetail text={a.detail} />
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </Card>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card className="p-6">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Hospital onboarding progress</h2>
            <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/hospitals">Hospitals →</Link>
          </div>
          <div className="mt-4 space-y-3 text-sm">
            {onboarding.slice(0, 5).map((h) => {
              const pct = h.completion_pct ?? 0;
              const bar = pct >= 100 ? "bg-emerald-500" : pct >= 60 ? "bg-amber-500" : "bg-red-500";
              return (
                <Link
                  key={h.hospital_id}
                  href={`/superadmin/hospitals?highlight=${h.hospital_id}`}
                  className="block rounded border border-[#E2E8F0] px-3 py-2 hover:bg-[#F8FAFC]"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium text-[#0F172A]">{h.name}</div>
                    <div className="text-[#64748B]">{fmtInt(pct)}%</div>
                  </div>
                  <div className="mt-2 h-2 w-full rounded bg-[#E2E8F0]">
                    <div className={`h-2 rounded ${bar}`} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
                  </div>
                </Link>
              );
            })}
          </div>
        </Card>

        <Card className="p-6">
          <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Pending hospital admin assignments</h2>
          <div className="mt-4 space-y-2 text-sm">
            {pending?.hospitals_no_admin?.slice(0, 3)?.map((h) => (
              <div key={h.hospital_id} className="flex items-center justify-between gap-3 rounded border border-[#E2E8F0] px-3 py-2">
                <div>
                  <div className="font-medium text-[#0F172A]">{h.hospital_name}</div>
                  <div className="text-[#64748B]">No admin assigned</div>
                </div>
                <Link
                  className="text-sm font-medium text-[#2563EB]"
                  href={`/superadmin/user-management?hospital=${encodeURIComponent(h.hospital_id)}&action=invite_admin`}
                >
                  Invite admin →
                </Link>
              </div>
            ))}
            {pending?.pending_invites?.slice(0, 2)?.map((i) => (
              <div key={i.user_id} className="flex items-center justify-between gap-3 rounded border border-[#E2E8F0] px-3 py-2">
                <div>
                  <div className="font-medium text-[#0F172A]">{i.email}</div>
                  <div className="text-[#64748B]">
                    Invite sent{(i.expires_soon ? " · expires soon" : "")}{i.hospital_name ? ` · ${i.hospital_name}` : ""}
                  </div>
                </div>
                <Link
                  className="text-sm font-medium text-[#2563EB]"
                  href={`/superadmin/user-management?resendInvite=${encodeURIComponent(i.user_id)}&inviteeEmail=${encodeURIComponent(i.email)}`}
                >
                  Resend →
                </Link>
              </div>
            ))}
            {pending?.pending_grants?.slice(0, 1)?.map((g) => (
              <div key={g.access_id} className="flex items-center justify-between gap-3 rounded border border-[#E2E8F0] px-3 py-2">
                <div>
                  <div className="font-medium text-[#0F172A]">{g.super_admin_email}</div>
                  <div className="text-[#64748B]">Grant sent · {g.hospital_name}</div>
                </div>
                <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/hospitals">View →</Link>
              </div>
            ))}
            <div className="pt-1">
              <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/user-management">Manage all →</Link>
            </div>
          </div>
        </Card>

        <Card className="p-6 lg:col-span-2">
          <div className="flex items-center justify-between gap-3">
            <h2 className="font-sora text-lg font-semibold text-[#0F172A]">Recent audit events</h2>
            <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/audit-logs">View full log →</Link>
          </div>
          <div className="mt-4 space-y-2 text-sm">
            {auditLogs.length === 0 ? (
              <div className="text-[#64748B]">No recent events.</div>
            ) : (
              auditLogs.slice(0, 5).map((l, idx) => (
                <div key={l.log_id || idx} className="flex flex-wrap items-center justify-between gap-3 rounded border border-[#E2E8F0] px-3 py-2">
                  <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2">
                    <Badge variant="default">{l.action}</Badge>
                    <span className="font-medium text-[#0F172A]">{l.user}</span>
                    <span className="text-[#64748B]">{l.hospital || "—"}</span>
                    {l.ip_address ? (
                      <span className="font-mono text-xs text-[#64748B]" title="IP address">
                        {l.ip_address}
                      </span>
                    ) : null}
                  </div>
                  <div className="shrink-0 font-mono text-xs text-[#64748B]">{l.timestamp?.slice(0, 19)}</div>
                </div>
              ))
            )}
          </div>
        </Card>
      </div>
    </div>
  );
}
