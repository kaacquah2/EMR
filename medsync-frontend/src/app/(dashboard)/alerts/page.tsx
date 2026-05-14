"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useAlerts, useResolveAlert } from "@/hooks/use-alerts";
import { canResolveAlerts } from "@/lib/permissions";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

const severityColor: Record<string, "default" | "active" | "pending"> = {
  critical: "active",
  high: "active",
  medium: "pending",
  low: "default",
};

export default function AlertsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [statusFilter, setStatusFilter] = useState<string>("active");
  const { alerts, loading, fetch } = useAlerts(statusFilter, undefined, user?.hospital_id ?? undefined);
  const { resolve, loading: resolving } = useResolveAlert();

  useEffect(() => {
    if (user?.role === "receptionist" || user?.role === "lab_technician") {
      router.replace("/unauthorized");
    }
  }, [user?.role, router]);

  const canResolve = canResolveAlerts(user?.role);

  const handleResolve = async (id: string) => {
    const ok = await resolve(id);
    if (ok) fetch();
  };

  if (!user) return null;

  return (
    <div className="space-y-6">
      <div className="page-header">
        <h1 className="page-header-title">Clinical Alerts</h1>
        <p className="page-header-desc">View and resolve patient alerts</p>
      </div>

      <div className="flex flex-wrap gap-2">
        {["active", "resolved", "dismissed"].map((s) => (
          <Button
            key={s}
            variant={statusFilter === s ? "primary" : "secondary"}
            size="sm"
            onClick={() => setStatusFilter(s)}
          >
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </Button>
        ))}
      </div>

      <Card accent="teal">
        <CardHeader>
          <CardTitle>Alerts</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-slate-500 dark:text-slate-500">Loading...</p>
          ) : alerts.length === 0 ? (
            <p className="text-slate-500 dark:text-slate-500">No alerts</p>
          ) : (
            <ul className="space-y-3">
              {alerts.map((a) => (
                <li
                  key={a.id}
                  className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-slate-200 dark:border-slate-800 p-3"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={severityColor[a.severity] ?? "default"}>{a.severity}</Badge>
                      <span className="text-sm text-slate-500 dark:text-slate-500">{a.status}</span>
                    </div>
                    <p className="mt-1 font-medium text-slate-900 dark:text-slate-100">{a.message}</p>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-500">
                      Patient:{" "}
                      <Link href={`/patients/${a.patient_id}`} className="text-[#0EAFBE] hover:underline">
                        {a.patient_name} ({a.ghana_health_id})
                      </Link>
                    </p>
                    <p className="text-xs text-slate-500 dark:text-slate-500">{new Date(a.created_at).toLocaleString()}</p>
                  </div>
                  {canResolve && a.status === "active" && (
                    <Button
                      size="sm"
                      disabled={resolving}
                      onClick={() => handleResolve(a.id)}
                    >
                      Resolve
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
