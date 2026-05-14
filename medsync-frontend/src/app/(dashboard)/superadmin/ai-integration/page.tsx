"use client";

import React, { useEffect, useState } from "react";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { AIDisclaimer } from "@/components/ui/AIDisclaimer";

type AiStatusResponse = {
  status: string;
  analyses_24h: number;
  avg_response_ms: number | null;
  target_response_ms: number;
  uptime_7d_pct: number | null;
  modules: Record<string, string>;
  models?: Record<string, { configured: boolean; present: boolean }>;
};

export default function SuperAdminAiIntegrationPage() {
  const api = useApi();
  const [s, setS] = useState<AiStatusResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const r = await api.get<AiStatusResponse>("/ai/status");
        if (!cancelled) setS(r || null);
      } catch {
        if (!cancelled) setS(null);
      }
    };
    run();
    return () => {
      cancelled = true;
    };
  }, [api]);

  return (
    <div className="space-y-6">
      <AIDisclaimer />
      <div>
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">AI integration</h1>
        <p className="text-sm text-slate-500 dark:text-slate-500">Status and configuration overview</p>
      </div>

      <Card className="p-6">
        {!s ? (
          <div className="text-sm text-slate-500 dark:text-slate-500">No AI status.</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 text-sm">
              <div><span className="text-slate-500 dark:text-slate-500">Status:</span> <span className="font-medium text-slate-900 dark:text-slate-100">{s.status}</span></div>
              <div><span className="text-slate-500 dark:text-slate-500">Analyses (24h):</span> <span className="font-medium text-slate-900 dark:text-slate-100">{Math.trunc(s.analyses_24h)}</span></div>
              <div>
                <span className="text-slate-500 dark:text-slate-500">Avg response:</span>{" "}
                <span className="font-medium text-slate-900 dark:text-slate-100">
                  {typeof s.avg_response_ms === "number" && Number.isFinite(s.avg_response_ms)
                    ? `${Math.trunc(s.avg_response_ms)}ms`
                    : "—"}
                </span>
              </div>
              <div><span className="text-slate-500 dark:text-slate-500">Target:</span> <span className="font-medium text-slate-900 dark:text-slate-100">{Math.trunc(s.target_response_ms)}ms</span></div>
              <div>
                <span className="text-slate-500 dark:text-slate-500">Uptime (7d):</span>{" "}
                <span className="font-medium text-slate-900 dark:text-slate-100">
                  {typeof s.uptime_7d_pct === "number" && Number.isFinite(s.uptime_7d_pct)
                    ? `${Math.trunc(s.uptime_7d_pct)}%`
                    : "—"}
                </span>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="font-medium text-slate-900 dark:text-slate-100">Modules</div>
              {Object.entries(s.modules || {}).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between rounded border border-slate-200 dark:border-slate-800 px-3 py-2">
                  <span className="capitalize">{k.replaceAll("_", " ")}</span>
                  <span className="text-slate-500 dark:text-slate-500">{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

