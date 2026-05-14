"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AIDisclaimer } from "@/components/ui/AIDisclaimer";

type RecentPatient = {
  id: string;
  full_name: string;
  ghana_health_id: string;
};

export default function AIInsightsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const [patients, setPatients] = React.useState<RecentPatient[]>([]);
  const [loading, setLoading] = React.useState(true);

  React.useEffect(() => {
    if (!user) return;
    if (user.role !== "doctor") {
      router.replace("/unauthorized");
      return;
    }
    (async () => {
      setLoading(true);
      try {
        const res = await api.get<{ recent_patients?: RecentPatient[] }>("/dashboard");
        setPatients(Array.isArray(res.recent_patients) ? res.recent_patients : []);
      } catch {
        setPatients([]);
      } finally {
        setLoading(false);
      }
    })();
  }, [api, router, user]);

  if (!user || user.role !== "doctor") {
    return null;
  }

  return (
    <div className="space-y-6">
      <AIDisclaimer />
      <div>
        <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">AI Insights</h1>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-500">
          Open a patient and review risk, triage, and recommendation insights.
        </p>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-lg">Recent patients</CardTitle>
          <Link href="/patients/search">
            <Button size="sm" variant="secondary">Find patient</Button>
          </Link>
        </CardHeader>
        <CardContent className="space-y-3">
          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-500">Loading…</p>
          ) : patients.length === 0 ? (
            <p className="text-sm text-slate-500 dark:text-slate-500">No recent patients. Use patient search to open AI insights.</p>
          ) : (
            patients.map((p) => (
              <div key={p.id} className="flex items-center justify-between gap-3 rounded-lg border border-slate-200 dark:border-slate-800 p-3">
                <div>
                  <p className="text-sm font-semibold text-slate-900 dark:text-slate-100">{p.full_name}</p>
                  <p className="text-xs text-slate-500 dark:text-slate-500">{p.ghana_health_id}</p>
                </div>
                <Link href={`/patients/${p.id}/ai-insights`}>
                  <Button size="sm">Open AI Insights</Button>
                </Link>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
