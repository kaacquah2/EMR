"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { DASHBOARD_HEALTH_ROWS, runbookHref } from "@/lib/ops-runbooks";

type ServiceStatus = { status?: string; latency_ms?: number; response_ms?: number; last_run?: string; last_validated?: string };
type HealthResponse = {
  services?: Record<string, ServiceStatus | undefined>;
};

function dot(status: string | undefined) {
  const v = (status || "").toLowerCase();
  if (v === "ok") return "bg-emerald-500";
  if (v === "slow" || v === "degraded" || v === "warn") return "bg-amber-500";
  return "bg-red-500";
}

const RUNBOOK_BLURBS: Record<string, string[]> = {
  api: [
    "Local dev: confirm Django is listening on http://127.0.0.1:8000 (Windows: `netstat -ano | findstr :8000`).",
    "Check `medsync-backend/.env`: DEBUG=True, ALLOWED_HOSTS includes localhost/127.0.0.1, CORS_ALLOWED_ORIGINS includes http://localhost:3000.",
    "If clients time out: confirm frontend `NEXT_PUBLIC_API_URL` matches backend (default http://localhost:8000/api/v1).",
  ],
  database: [
    "Verify DATABASE_URL connectivity (Neon/managed Postgres): check cloud console or run backend `/api/v1/health` and confirm database status is ok.",
    "Confirm migrations applied: `python manage.py migrate`.",
  ],
  redis: [
    "Confirm `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` are set to full redis:// URIs (not host:port).",
    "If Redis is down, background jobs/caching will degrade; API should still run. Re-check `/api/v1/health` after fixing env and restarting backend workers.",
  ],
  ai_inference: [
    "If AI shows degraded/offline, verify any configured model/env settings and that the AI endpoints respond (see /superadmin/ai-integration).",
    "AI failures should not block core API; treat as a separate incident and validate fallbacks.",
  ],
  kms: [
    "Confirm encryption key is configured for the environment (never commit raw keys).",
  ],
  audit_chain: [
    "Run audit chain validation from the dashboard or `/superadmin/audit-chain-integrity`.",
    "Investigate any reported mismatch with security before dismissing.",
  ],
  backup: [
    "Configure automated DB backups and off-site retention per your compliance policy.",
  ],
};

export default function SuperAdminSystemHealthPage() {
  const api = useApi();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const h = await api.get<HealthResponse>("/health?deep=1");
        if (!cancelled) {
          setHealth(h || null);
          setRefreshedAt(new Date().toISOString());
        }
      } catch {
        if (!cancelled) {
          setHealth(null);
          setRefreshedAt(new Date().toISOString());
        }
      }
    };
    run();
    const t = window.setInterval(run, 30_000);
    return () => {
      cancelled = true;
      clearInterval(t);
    };
  }, [api]);

  const services = health?.services || {};
  const externalDocs = Boolean(process.env.NEXT_PUBLIC_OPS_DOCS_BASE);

  return (
    <div className="space-y-6">
      <div>
        <Link href="/superadmin" className="text-sm font-medium text-[#2563EB]">
          ← Dashboard
        </Link>
        <h1 className="mt-2 font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">System health</h1>
        <p className="text-sm text-slate-500 dark:text-slate-500">Last refreshed {refreshedAt ? refreshedAt.slice(11, 16) : "—"}</p>
      </div>

      <Card className="p-6">
        <div className="space-y-3 text-sm">
          {Object.keys(services).length === 0 ? (
            <div className="text-slate-500 dark:text-slate-500">No health data.</div>
          ) : (
            DASHBOARD_HEALTH_ROWS.map(({ label, key }) => {
              const svc = services[key];
              const ms = svc?.latency_ms ?? svc?.response_ms;
              return (
                <div key={key} className="flex flex-wrap items-center justify-between gap-3 rounded border border-slate-200 dark:border-slate-800 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <span className={`h-2.5 w-2.5 rounded-full ${dot(svc?.status)}`} />
                    <span className="font-medium text-slate-900 dark:text-slate-100">{label}</span>
                    <span className="text-slate-500 dark:text-slate-500">{svc?.status ?? "unknown"}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-slate-500 dark:text-slate-500">{ms ? `${Math.trunc(ms)}ms` : "—"}</div>
                    <Link
                      href={runbookHref(key)}
                      className="text-xs font-medium text-[#2563EB] hover:underline"
                      target={externalDocs ? "_blank" : undefined}
                      rel={externalDocs ? "noopener noreferrer" : undefined}
                    >
                      Runbook
                    </Link>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </Card>

      <div>
        <h2 className="font-sora text-lg font-semibold text-slate-900 dark:text-slate-100">Runbooks</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-500">
          Quick checks per service. For external wiki links, set{" "}
          <code className="rounded bg-slate-100 dark:bg-slate-900 px-1">NEXT_PUBLIC_OPS_DOCS_BASE</code> in the frontend env.
        </p>
        <div className="mt-4 space-y-6">
          {DASHBOARD_HEALTH_ROWS.map(({ label, key }) => (
            <section key={key} id={`svc-${key}`} className="scroll-mt-24 rounded-lg border border-slate-200 dark:border-slate-800 bg-white p-4">
              <h3 className="font-semibold text-slate-900 dark:text-slate-100">{label}</h3>
              <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-slate-500 dark:text-slate-500">
                {(RUNBOOK_BLURBS[key] ?? ["No additional notes."]).map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </div>
    </div>
  );
}
