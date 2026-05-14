"use client";

import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useApi } from "@/hooks/use-api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type ActivityResponse = {
  consents: Array<{
    id: string;
    created_at: string;
    global_patient__full_name: string;
    granted_to_facility__name: string;
    scope: string;
  }>;
  referrals: Array<{
    id: string;
    created_at: string;
    global_patient__full_name: string;
    from_facility__name: string;
    to_facility__name: string;
    status: string;
  }>;
  break_glass_events: Array<{
    id: string;
    created_at: string;
    global_patient__full_name: string;
    facility__name: string;
    accessed_by__full_name: string;
    reason: string;
  }>;
  period_days: number;
  summary: {
    total_consents: number;
    total_referrals: number;
    total_break_glass: number;
  };
};

export default function CrossFacilityActivityLogPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();
  const [days, setDays] = useState(30);
  const [data, setData] = useState<ActivityResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const canAccess = user?.role === "super_admin";
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  useEffect(() => {
    if (!canAccess) return;
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const r = await api.get<ActivityResponse>(`/superadmin/cross-facility-activity?days=${encodeURIComponent(String(days))}`);
        if (!cancelled) setData(r ?? null);
      } catch {
        if (!cancelled) setData(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [api, canAccess, days]);

  const summary = useMemo(() => data?.summary ?? null, [data]);

  if (user && !canAccess) {
    return (
      <div className="flex min-h-[200px] items-center justify-center text-slate-500 dark:text-slate-500">
        Redirecting...
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Cross-Facility Monitor</h1>
          <p className="text-sm text-slate-500 dark:text-slate-500">System-wide activity across facilities</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-500">
            Period
          </label>
          <select
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
            className="rounded border border-slate-300 dark:border-slate-700 bg-white px-2 py-1 text-sm text-slate-900 dark:text-slate-100"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>
          <Link href="/superadmin/hospitals">
            <Button variant="secondary">Hospitals</Button>
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card accent="teal">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-500">Consents</p>
            <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{summary ? summary.total_consents : "—"}</p>
          </CardContent>
        </Card>
        <Card accent="navy">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-500">Referrals</p>
            <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{summary ? summary.total_referrals : "—"}</p>
          </CardContent>
        </Card>
        <Card accent="amber">
          <CardContent className="pt-6">
            <p className="text-sm font-medium text-slate-500 dark:text-slate-500">Break-glass events</p>
            <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{summary ? summary.total_break_glass : "—"}</p>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <p className="text-sm text-slate-500 dark:text-slate-500">Loading…</p>
          ) : !data ? (
            <p className="text-sm text-slate-500 dark:text-slate-500">No activity.</p>
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="font-sora text-lg font-semibold text-slate-900 dark:text-slate-100">Break-glass</h3>
                {data.break_glass_events.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-500">No break-glass events.</p>
                ) : (
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800">
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Time</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">User</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Hospital</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Patient</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Reason</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.break_glass_events.slice(0, 50).map((e) => (
                          <tr key={e.id} className="border-b border-slate-100 dark:border-slate-900">
                            <td className="py-2 font-mono text-xs">{e.created_at.slice(0, 19)}</td>
                            <td className="py-2">{e.accessed_by__full_name}</td>
                            <td className="py-2">{e.facility__name}</td>
                            <td className="py-2">{e.global_patient__full_name}</td>
                            <td className="py-2 text-slate-500 dark:text-slate-500">{String(e.reason ?? "").slice(0, 64)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div>
                <h3 className="font-sora text-lg font-semibold text-slate-900 dark:text-slate-100">Referrals</h3>
                {data.referrals.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-500">No referrals.</p>
                ) : (
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800">
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Time</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Patient</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">From</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">To</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Status</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.referrals.slice(0, 50).map((r) => (
                          <tr key={r.id} className="border-b border-slate-100 dark:border-slate-900">
                            <td className="py-2 font-mono text-xs">{r.created_at.slice(0, 19)}</td>
                            <td className="py-2">{r.global_patient__full_name}</td>
                            <td className="py-2">{r.from_facility__name}</td>
                            <td className="py-2">{r.to_facility__name}</td>
                            <td className="py-2">
                              <span className="rounded bg-slate-200 dark:bg-slate-800 px-2 py-0.5 text-xs font-semibold text-slate-900 dark:text-slate-100">
                                {r.status}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>

              <div>
                <h3 className="font-sora text-lg font-semibold text-slate-900 dark:text-slate-100">Consents</h3>
                {data.consents.length === 0 ? (
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-500">No consents.</p>
                ) : (
                  <div className="mt-2 overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-200 dark:border-slate-800">
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Time</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Patient</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Facility</th>
                          <th className="py-2 text-left font-medium text-slate-500 dark:text-slate-500">Scope</th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.consents.slice(0, 50).map((c) => (
                          <tr key={c.id} className="border-b border-slate-100 dark:border-slate-900">
                            <td className="py-2 font-mono text-xs">{c.created_at.slice(0, 19)}</td>
                            <td className="py-2">{c.global_patient__full_name}</td>
                            <td className="py-2">{c.granted_to_facility__name}</td>
                            <td className="py-2">
                              <span className="rounded bg-slate-200 dark:bg-slate-800 px-2 py-0.5 text-xs font-semibold text-slate-900 dark:text-slate-100">
                                {c.scope}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

