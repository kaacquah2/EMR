"use client";

import React from "react";
import {
  LineChart,
  Line,
  ResponsiveContainer,
} from "recharts";
import { TrendingUp, TrendingDown, Users, Bed, LogOut, Clock } from "lucide-react";

interface SparklineProps {
  data: { value: number }[];
  color: string;
}

function Sparkline({ data, color }: SparklineProps) {
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
        <div className={`p-3 rounded-lg ${color.replace('stroke-', 'bg-').replace('600', '100')} dark:${color.replace('stroke-', 'bg-').replace('600', '950/30')}`}>
          {React.cloneElement(icon as React.ReactElement<{ className?: string }>, { className: `h-5 w-5 ${color.replace('stroke-', 'text-')}` })}
        </div>
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">{label}</p>
          <div className="flex items-center gap-2">
            <h4 className="text-2xl font-bold text-slate-900 dark:text-white">{value}</h4>
            {trend !== undefined && (
              <span className={`text-xs font-bold flex items-center ${trend >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                {trend >= 0 ? <TrendingUp className="h-3 w-3 mr-1" /> : <TrendingDown className="h-3 w-3 mr-1" />}
                {Math.abs(trend)}%
              </span>
            )}
          </div>
        </div>
      </div>
      <Sparkline data={data} color={color.replace('stroke-', '#')} />
    </div>
  );
}

export function HospitalStatistics() {
  // Mock data for trends
  const mockTrend = [
    { value: 10 }, { value: 15 }, { value: 8 }, { value: 12 }, { value: 20 }, { value: 18 }, { value: 25 }
  ];

  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4 mt-6">
      <StatItem
        label="Admissions (24h)"
        value="42"
        trend={12}
        data={mockTrend}
        color="stroke-blue-600"
        icon={<Users />}
      />
      <StatItem
        label="Discharges (24h)"
        value="38"
        trend={-5}
        data={mockTrend.map(d => ({ value: 30 - d.value }))}
        color="stroke-emerald-600"
        icon={<LogOut />}
      />
      <StatItem
        label="Bed Occupancy"
        value="88%"
        trend={2}
        data={mockTrend.map(d => ({ value: 70 + d.value }))}
        color="stroke-amber-600"
        icon={<Bed />}
      />
      <StatItem
        label="Avg Waiting Time"
        value="18m"
        trend={-15}
        data={mockTrend.map(d => ({ value: 40 - d.value }))}
        color="stroke-rose-600"
        icon={<Clock />}
      />
    </div>
  );
}
