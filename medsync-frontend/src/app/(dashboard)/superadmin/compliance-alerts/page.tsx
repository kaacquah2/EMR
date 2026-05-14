"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type ComplianceAlert = { id: string; severity: "info" | "warning" | "critical"; title: string; detail: string };

export default function SuperAdminComplianceAlertsPage() {
  const api = useApi();
  const [alerts, setAlerts] = useState<ComplianceAlert[]>([]);

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        const r = await api.get<{ data: ComplianceAlert[] }>("/superadmin/compliance-alerts");
        if (!cancelled) setAlerts(Array.isArray(r?.data) ? r.data : []);
      } catch {
        if (!cancelled) setAlerts([]);
      }
    };
    run();
    const t = window.setInterval(run, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
  }, [api]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Compliance alerts</h1>
          <p className="text-sm text-slate-500 dark:text-slate-500">Auto-generated network-wide signals</p>
        </div>
        <Link className="text-sm font-medium text-[#2563EB]" href="/superadmin/cross-facility-activity-log">Cross-facility monitor →</Link>
      </div>

      <Card className="p-6">
        {alerts.length === 0 ? (
          <div className="text-sm text-slate-500 dark:text-slate-500">No alerts.</div>
        ) : (
          <div className="space-y-2 text-sm">
            {alerts.map((a) => {
              const sev = a.severity === "critical" ? "danger" : a.severity === "warning" ? "warning" : "secondary";
              return (
                <div key={a.id} className="rounded border border-slate-200 dark:border-slate-800 px-3 py-2">
                  <div className="flex items-center gap-2">
                    <Badge variant={sev as never}>{a.severity}</Badge>
                    <span className="font-medium text-slate-900 dark:text-slate-100">{a.title}</span>
                  </div>
                  <div className="mt-1 text-slate-500 dark:text-slate-500">{a.detail}</div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}

