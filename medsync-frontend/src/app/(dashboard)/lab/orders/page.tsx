"use client";

import React, { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth-context";
import { useLabOrders } from "@/hooks/use-lab";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";

export default function LabOrdersPage() {
  const router = useRouter();
  const { user } = useAuth();
  const [tab, setTab] = useState<"all" | "pending" | "in_progress" | "resulted_today" | "verified">("all");
  const { orders, stats, loading } = useLabOrders(tab);

  const canAccess = user?.role === "lab_technician";
  useEffect(() => {
    if (user && !canAccess) router.replace("/unauthorized");
  }, [user, canAccess, router]);

  const urgencyClass = (urgency: string) =>
    urgency === "stat" ? "bg-red-100 text-red-700" : urgency === "urgent" ? "bg-amber-100 text-amber-700" : "bg-slate-100 text-slate-700";
  const statusLabel = (status: string) =>
    status === "in_progress"
      ? "In Progress"
      : status === "resulted"
        ? "Resulted"
        : status === "verified"
          ? "Verified"
          : status === "collected"
            ? "Collected"
            : "Ordered";

  const rows = useMemo(
    () =>
      [...orders].sort((a, b) => {
        if (a.urgency_rank !== b.urgency_rank) return a.urgency_rank - b.urgency_rank;
        return new Date(a.ordered_at).getTime() - new Date(b.ordered_at).getTime();
      }),
    [orders]
  );

  const tatText = (minutesRemaining: number | null) => {
    if (minutesRemaining == null) return { label: "N/A", cls: "text-[#64748B]" };
    if (minutesRemaining < 0) return { label: `OVERDUE ${Math.abs(minutesRemaining)} min`, cls: "text-[#DC2626] font-semibold" };
    if (minutesRemaining < 30) return { label: `Due in ${minutesRemaining} min`, cls: "text-[#DC2626] font-semibold" };
    return { label: `Due in ${minutesRemaining} min`, cls: "text-[#334155]" };
  };

  if (user && !canAccess) return <div className="flex min-h-[200px] items-center justify-center text-[#64748B]">Redirecting...</div>;

  return (
    <div className="space-y-6">
      <h1 className="font-sora text-2xl font-bold text-[#0F172A]">
        Lab Worklist
      </h1>

      <div className="grid gap-3 md:grid-cols-4">
        <Card className="p-4"><p className="text-sm text-[#64748B]">STAT orders</p><p className="text-2xl font-bold text-red-700">{stats.stat_orders}</p></Card>
        <Card className="p-4"><p className="text-sm text-[#64748B]">Urgent orders</p><p className="text-2xl font-bold text-amber-700">{stats.urgent_orders}</p></Card>
        <Card className="p-4"><p className="text-sm text-[#64748B]">Routine orders</p><p className="text-2xl font-bold text-slate-700">{stats.routine_orders}</p></Card>
        <Card className="p-4"><p className="text-sm text-[#64748B]">In progress</p><p className="text-2xl font-bold text-blue-700">{stats.in_progress_orders}</p></Card>
      </div>

      <div className="flex gap-2 border-b border-[#CBD5E1]">
        {[
          ["all", "All"],
          ["pending", "Pending"],
          ["in_progress", "In Progress"],
          ["resulted_today", "Resulted (today)"],
          ["verified", "Verified"],
        ].map(([value, label]) => (
          <button
            key={value}
            type="button"
            onClick={() => setTab(value as typeof tab)}
            className={`border-b-2 px-3 py-2 text-sm font-medium ${
              tab === value ? "border-[#0B8A96] text-[#0B8A96]" : "border-transparent text-[#64748B]"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <Card className="p-6">
        {loading ? (
          <p className="text-[#64748B]">Loading...</p>
        ) : rows.length === 0 ? (
          <p className="text-[#64748B]">No matching orders.</p>
        ) : (
          <div className="space-y-2">
            {rows.map((o) => {
              const tat = tatText(o.minutes_remaining);
              return (
              <div
                key={o.id}
                className="flex cursor-pointer items-center justify-between rounded-lg border border-[#E2E8F0] p-4 hover:bg-[#F8FAFC]"
                onClick={() => router.push(`/lab/orders/${o.id}`)}
              >
                <div>
                  <p className="font-medium">{o.patient_name} ({o.gha_id}) - {o.test_name}</p>
                  <p className="text-sm text-[#64748B]">
                    {o.ordering_doctor_name} - {o.ordered_at?.slice(0, 16)}
                  </p>
                  <p className={`text-sm ${tat.cls}`}>{tat.label}</p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge className={urgencyClass(o.urgency)}>{o.urgency.toUpperCase()}</Badge>
                  <Badge className="bg-blue-100 text-blue-700">{statusLabel(o.status)}</Badge>
                </div>
              </div>
            )})}
          </div>
        )}
      </Card>
    </div>
  );
}
