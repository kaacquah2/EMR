"use client";

import React, { useEffect, useState } from "react";
import { useApi } from "@/hooks/use-api";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type BreakGlassEntry = {
  break_glass_id: string;
  user_name: string;
  user_email: string;
  hospital_name: string;
  hospital_id: string;
  patient_name: string;
  global_patient_id: string;
  reason: string;
  created_at: string;
  reviewed?: boolean;
  excessive_usage?: boolean;
};

export default function SuperAdminBreakGlassReviewPage() {
  const api = useApi();
  const [rows, setRows] = useState<BreakGlassEntry[]>([]);
  const [showReviewed, setShowReviewed] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);

  const load = async () => {
    const q = showReviewed ? "" : "?reviewed=false";
    const r = await api.get<{ data: BreakGlassEntry[] }>("/superadmin/break-glass-list-global" + q);
    setRows(Array.isArray(r?.data) ? r.data : []);
  };

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      try {
        await load();
      } catch {
        if (!cancelled) setRows([]);
      }
    };
    run();
    const t = window.setInterval(run, 60_000);
    return () => {
      cancelled = true;
      window.clearInterval(t);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showReviewed]);

  const markReviewed = async (id: string) => {
    setBusyId(id);
    try {
      await api.post(`/superadmin/break-glass/${id}/review`, {});
      await load();
    } finally {
      setBusyId(null);
    }
  };

  const flagAbuse = async (id: string) => {
    setBusyId(id);
    try {
      await api.post(`/superadmin/break-glass/${id}/flag-abuse`, {});
      await load();
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="font-sora text-2xl font-bold text-slate-900 dark:text-slate-100">Break-glass review</h1>
          <p className="text-sm text-slate-500 dark:text-slate-500">Review emergency access events and flag suspicious usage</p>
        </div>
        <Button variant="secondary" onClick={() => setShowReviewed((v) => !v)}>
          {showReviewed ? "Show unreviewed" : "Show reviewed"}
        </Button>
      </div>

      <Card className="p-6">
        {rows.length === 0 ? (
          <div className="text-sm text-slate-500 dark:text-slate-500">No events.</div>
        ) : (
          <div className="space-y-2 text-sm">
            {rows.slice(0, 200).map((e) => (
              <div key={e.break_glass_id} className="rounded border border-slate-200 dark:border-slate-800 px-3 py-2">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={e.excessive_usage ? "critical" : "default"}>{e.excessive_usage ? "abuse" : "event"}</Badge>
                    <span className="font-medium text-slate-900 dark:text-slate-100">{e.user_name || e.user_email}</span>
                    <span className="text-slate-500 dark:text-slate-500">{e.hospital_name}</span>
                    <span className="font-mono text-xs text-slate-500 dark:text-slate-500">{e.created_at?.slice(0, 19)}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    {!e.reviewed && (
                      <Button size="sm" disabled={busyId === e.break_glass_id} onClick={() => markReviewed(e.break_glass_id)}>
                        Mark reviewed
                      </Button>
                    )}
                    {!e.excessive_usage && (
                      <Button size="sm" variant="secondary" disabled={busyId === e.break_glass_id} onClick={() => flagAbuse(e.break_glass_id)}>
                        Flag abuse
                      </Button>
                    )}
                  </div>
                </div>
                <div className="mt-2 text-slate-500 dark:text-slate-500">{e.reason}</div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}

