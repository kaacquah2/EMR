"use client";

import React, { useEffect, useState } from "react";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";

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
      <div>
        <h1 className="font-sora text-2xl font-bold text-[#0F172A]">AI integration</h1>
        <p className="text-sm text-[#64748B]">Status and configuration overview</p>
      </div>

      <Card className="p-6">
        {!s ? (
          <div className="text-sm text-[#64748B]">No AI status.</div>
        ) : (
          <div className="grid gap-4 md:grid-cols-2">
            <div className="space-y-2 text-sm">
              <div><span className="text-[#64748B]">Status:</span> <span className="font-medium text-[#0F172A]">{s.status}</span></div>
              <div><span className="text-[#64748B]">Analyses (24h):</span> <span className="font-medium text-[#0F172A]">{Math.trunc(s.analyses_24h)}</span></div>
              <div>
                <span className="text-[#64748B]">Avg response:</span>{" "}
                <span className="font-medium text-[#0F172A]">
                  {typeof s.avg_response_ms === "number" && Number.isFinite(s.avg_response_ms)
                    ? `${Math.trunc(s.avg_response_ms)}ms`
                    : "—"}
                </span>
              </div>
              <div><span className="text-[#64748B]">Target:</span> <span className="font-medium text-[#0F172A]">{Math.trunc(s.target_response_ms)}ms</span></div>
              <div>
                <span className="text-[#64748B]">Uptime (7d):</span>{" "}
                <span className="font-medium text-[#0F172A]">
                  {typeof s.uptime_7d_pct === "number" && Number.isFinite(s.uptime_7d_pct)
                    ? `${Math.trunc(s.uptime_7d_pct)}%`
                    : "—"}
                </span>
              </div>
            </div>
            <div className="space-y-2 text-sm">
              <div className="font-medium text-[#0F172A]">Modules</div>
              {Object.entries(s.modules || {}).map(([k, v]) => (
                <div key={k} className="flex items-center justify-between rounded border border-[#E2E8F0] px-3 py-2">
                  <span className="capitalize">{k.replaceAll("_", " ")}</span>
                  <span className="text-[#64748B]">{v}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}

