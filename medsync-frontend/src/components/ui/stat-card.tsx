"use client";

import * as React from "react";
import { Card, CardContent } from "@/components/ui/card";

type Accent = "teal" | "navy" | "green" | "amber";

export interface StatCardProps {
  /** Metric label, e.g. "Patients in queue" */
  label: string;
  /** Metric value */
  value: number | string;
  /** Optional sub-text below the value */
  subtitle?: string;
  /** Left accent border colour */
  accent?: Accent;
  /** Extra className on the value <p> (e.g. "text-red-600") */
  valueClassName?: string;
}

export function StatCard({
  label,
  value,
  subtitle,
  accent,
  valueClassName,
}: StatCardProps) {
  return (
    <Card accent={accent} aria-label={`${label}: ${value}`}>
      <CardContent className="pt-6">
        <p className="text-sm font-medium text-[var(--gray-500)]">{label}</p>
        <p
          className={`mt-2 text-3xl font-bold leading-none tabular-nums text-[var(--gray-900)] ${valueClassName ?? ""}`}
        >
          {value}
        </p>
        {subtitle && (
          <p className="mt-1 text-xs text-[var(--gray-500)]">{subtitle}</p>
        )}
      </CardContent>
    </Card>
  );
}
