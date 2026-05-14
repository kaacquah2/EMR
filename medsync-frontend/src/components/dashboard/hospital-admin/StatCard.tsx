"use client";

import React from "react";

const ACCENT: Record<string, string> = {
  teal: "#1D9E75",
  blue: "#378ADD",
  purple: "#7F77DD",
  amber: "#EF9F27",
  red: "#E24B4A",
};

export function StatCard(props: {
  label: string;
  value: React.ReactNode;
  sub?: React.ReactNode;
  accentColor: keyof typeof ACCENT;
  loading?: boolean;
}) {
  const { label, value, sub, accentColor, loading } = props;
  const color = ACCENT[accentColor] ?? ACCENT.teal;
  return (
    <div
      className="rounded-xl border border-slate-200 dark:border-slate-800/80 bg-white p-5 shadow-sm"
      style={{ borderTop: `2px solid ${color}` }}
    >
      <p className="text-sm font-medium text-slate-500 dark:text-slate-500">{label}</p>
      {loading ? (
        <div className="mt-2 h-9 w-20 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
      ) : (
        <p className="mt-1 text-2xl font-bold text-slate-900 dark:text-slate-100">{value}</p>
      )}
      {sub != null && !loading ? (
        <p className="mt-1 text-xs text-slate-500 dark:text-slate-500">{sub}</p>
      ) : loading ? (
        <div className="mt-2 h-3 w-32 animate-pulse rounded bg-slate-100 dark:bg-slate-900" />
      ) : null}
    </div>
  );
}
