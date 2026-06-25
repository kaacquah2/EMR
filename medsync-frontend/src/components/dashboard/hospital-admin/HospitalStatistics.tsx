"use client";

import React from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown, Users, Activity, BedDouble, AlertTriangle } from "lucide-react";
import { useDashboardAnalytics } from "@/hooks/use-analytics";
import { useAdmissions } from "@/hooks/use-admissions";

interface SparklineProps {
  data: { value: number }[];
  color: string;
}

function Sparkline({ data, color }: SparklineProps) {
  if (!data || data.length === 0) return <div className="h-10 w-24" />;
  return (
    <div className="h-10 w-24">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data}>
          <Line
            type="monotone"
            dataKey="value"
            stroke={color}
            strokeWidth={2}
            dot={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

interface StatItemProps {
  label: string;
  value: string | number;
  trend?: number;
  data: { value: number }[];
  color: string;
  icon: React.ReactNode;
}

function StatItem({ label, value, trend, data, color, icon }: StatItemProps) {
  return (
    <div className="flex items-center justify-between p-4 rounded-xl border border-slate-100 dark:border-slate-800 bg-white dark:bg-slate-900 shadow-sm">
      <div className="flex items-center gap-4">
        <div className="p-3 rounded-lg bg-slate-100 dark:bg-slate-800">
          {React.cloneElement(icon as React.ReactElement<{ className?: string }>, {
            className: `h-5 w-5 ${color}`,
          })}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <div className="flex items-center gap-2">
            <h4 className="text-2xl font-bold text-slate-900 dark:text-white">{value}</h4>
            {trend !== undefined && (
              <span className={`text-xs font-bold flex items-center ${trend >= 0 ? "text-emerald-600" : "text-rose-600"}`}>
                {trend >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                {Math.abs(trend)}%
              </span>
            )}
          </div>
        </div>
      </div>
      <Sparkline data={data} color={color.replace("text-", "#").replace("slate-600", "475569").replace("emerald-600", "059669").replace("amber-600", "d97706").replace("rose-600", "e11d48")} />
    </div>
  );
}

export function HospitalStatistics() {
  const today = new Date();
  const sevenDaysAgo = new Date(today);
  sevenDaysAgo.setDate(today.getDate() - 7);
  const from = sevenDaysAgo.toISOString().split("T")[0];
  const to = today.toISOString().split("T")[0];

  const { data, loading } = useDashboardAnalytics(from, to, "day", true);
  const { admissions } = useAdmissions();

  const patientSpark = (data?.patients_by_day ?? []).map((d) => ({ value: d.count }));
  const encounterSpark = (data?.encounters_by_day ?? []).map((d) => ({ value: d.count }));

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 mt-6">
      <StatItem
        label="New Patients (7d)"
        value={loading ? "—" : (data?.patients_total ?? 0)}
        data={patientSpark}
        color="text-[#0B8A96]"
        icon={<Users />}
      />
      <StatItem
        label="Encounters (7d)"
        value={loading ? "—" : (data?.encounters_total ?? 0)}
        data={encounterSpark}
        color="text-emerald-600"
        icon={<Activity />}
      />
      <StatItem
        label="Active Admissions"
        value={admissions.length}
        data={[]}
        color="text-amber-600"
        icon={<BedDouble />}
      />
      <StatItem
        label="Pending Alerts"
        value="—"
        data={[]}
        color="text-rose-600"
        icon={<AlertTriangle />}
      />
    </div>
  );
}
