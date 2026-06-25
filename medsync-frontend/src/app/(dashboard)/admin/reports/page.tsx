'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/lib/auth-context';
import { useDashboardAnalytics } from '@/hooks/use-analytics';
import { useApi } from '@/hooks/use-api';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { hasRole, ALL_ADMIN_ROLES } from '@/lib/permissions';
import { Download, Users, Activity, Calendar } from 'lucide-react';

function toDateStr(d: Date) {
  return d.toISOString().split('T')[0];
}

export default function AdminReportsPage() {
  const router = useRouter();
  const { user } = useAuth();
  const api = useApi();

  const today = new Date();
  const thirtyDaysAgo = new Date(today);
  thirtyDaysAgo.setDate(today.getDate() - 30);

  const [from, setFrom] = useState(toDateStr(thirtyDaysAgo));
  const [to, setTo] = useState(toDateStr(today));
  const [exporting, setExporting] = useState(false);

  const canAccess = hasRole(user?.role, ALL_ADMIN_ROLES);
  useEffect(() => {
    if (user && !canAccess) router.replace('/unauthorized');
  }, [user, canAccess, router]);

  const { data, loading, fetch: refetch } = useDashboardAnalytics(from, to, 'day', canAccess);

  const downloadBlob = async (blob: Blob, filename: string) => {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleAuditExport = async () => {
    setExporting(true);
    try {
      const blob = await api.getBlob(`/reports/audit/export?from=${from}&to=${to}`);
      await downloadBlob(blob, `audit-${from}-to-${to}.csv`);
    } catch {
      // best-effort
    } finally {
      setExporting(false);
    }
  };

  const handlePatientExport = async () => {
    setExporting(true);
    try {
      const blob = await api.getBlob(`/reports/export?type=patients&from=${from}&to=${to}`);
      await downloadBlob(blob, `patients-${from}-to-${to}.csv`);
    } catch {
      // best-effort
    } finally {
      setExporting(false);
    }
  };

  if (user && !canAccess) {
    return <div className="flex min-h-[200px] items-center justify-center text-slate-500">Redirecting…</div>;
  }

  const maxCount = data
    ? Math.max(
        ...(data.patients_by_day?.map((d) => d.count) ?? [0]),
        ...(data.encounters_by_day?.map((d) => d.count) ?? [0]),
        1
      )
    : 1;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 dark:text-slate-100">Reports & Analytics</h1>
          <p className="text-sm text-slate-500 dark:text-slate-400">
            Activity overview for {user?.hospital_name ?? 'your facility'}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={handlePatientExport} disabled={exporting}>
            <Download className="mr-2 h-4 w-4" />
            Export Patients CSV
          </Button>
          <Button variant="outline" size="sm" onClick={handleAuditExport} disabled={exporting}>
            <Download className="mr-2 h-4 w-4" />
            Export Audit CSV
          </Button>
        </div>
      </div>

      {/* Date range filter */}
      <Card>
        <CardContent className="pt-5">
          <div className="flex flex-wrap items-end gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">From</label>
              <input
                type="date"
                value={from}
                max={to}
                onChange={(e) => setFrom(e.target.value)}
                className="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2 text-sm bg-white dark:bg-slate-800"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 dark:text-slate-400 mb-1">To</label>
              <input
                type="date"
                value={to}
                min={from}
                max={toDateStr(today)}
                onChange={(e) => setTo(e.target.value)}
                className="rounded-lg border border-slate-300 dark:border-slate-700 px-3 py-2 text-sm bg-white dark:bg-slate-800"
              />
            </div>
            <Button size="sm" onClick={() => refetch()} disabled={loading}>
              {loading ? 'Loading…' : 'Apply'}
            </Button>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => {
                setFrom(toDateStr(thirtyDaysAgo));
                setTo(toDateStr(today));
              }}
            >
              Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Summary stats */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
              <Users className="h-4 w-4 text-[#0B8A96]" /> Total Patients
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-black text-slate-900 dark:text-slate-100">
              {loading ? '—' : (data?.patients_total ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-slate-400 mt-1">in selected range</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
              <Activity className="h-4 w-4 text-emerald-500" /> Total Encounters
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-4xl font-black text-slate-900 dark:text-slate-100">
              {loading ? '—' : (data?.encounters_total ?? 0).toLocaleString()}
            </p>
            <p className="text-xs text-slate-400 mt-1">in selected range</p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-slate-500">
              <Calendar className="h-4 w-4 text-violet-500" /> Date Range
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-lg font-bold text-slate-900 dark:text-slate-100">
              {from} → {to}
            </p>
            <p className="text-xs text-slate-400 mt-1">
              {Math.round((new Date(to).getTime() - new Date(from).getTime()) / 86_400_000)} days
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Patients by day chart */}
      {data?.patients_by_day && data.patients_by_day.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>New Patients per Day</CardTitle>
            <CardDescription>Patient registrations across the selected period</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-1 h-40 overflow-x-auto pb-2">
              {data.patients_by_day.map((d) => {
                const pct = maxCount > 0 ? (d.count / maxCount) * 100 : 0;
                return (
                  <div key={d.date} className="flex flex-col items-center gap-1 min-w-[24px] group">
                    <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
                      {d.count}
                    </span>
                    <div
                      className="w-4 rounded-t bg-[#0B8A96] hover:bg-[#067A85] transition-colors"
                      style={{ height: `${Math.max(pct, 2)}%` }}
                      title={`${d.date}: ${d.count}`}
                    />
                    <span className="text-[9px] text-slate-400 rotate-45 origin-left whitespace-nowrap">
                      {d.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Encounters by day chart */}
      {data?.encounters_by_day && data.encounters_by_day.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Encounters per Day</CardTitle>
            <CardDescription>Clinical encounters across the selected period</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-end gap-1 h-40 overflow-x-auto pb-2">
              {data.encounters_by_day.map((d) => {
                const pct = maxCount > 0 ? (d.count / maxCount) * 100 : 0;
                return (
                  <div key={d.date} className="flex flex-col items-center gap-1 min-w-[24px] group">
                    <span className="text-[10px] text-slate-400 opacity-0 group-hover:opacity-100 transition-opacity">
                      {d.count}
                    </span>
                    <div
                      className="w-4 rounded-t bg-emerald-500 hover:bg-emerald-600 transition-colors"
                      style={{ height: `${Math.max(pct, 2)}%` }}
                      title={`${d.date}: ${d.count}`}
                    />
                    <span className="text-[9px] text-slate-400 rotate-45 origin-left whitespace-nowrap">
                      {d.date.slice(5)}
                    </span>
                  </div>
                );
              })}
            </div>
          </CardContent>
        </Card>
      )}

      {loading && (
        <div className="flex items-center justify-center py-12 text-slate-400">Loading analytics…</div>
      )}

      {!loading && !data && (
        <div className="flex items-center justify-center py-12 text-slate-400">
          No analytics data available for the selected range.
        </div>
      )}
    </div>
  );
}
