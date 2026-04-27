"use client";

import * as React from "react";

export type ProgressVariant = "teal" | "green" | "amber" | "red";

export interface ProgressBarProps {
  /** Progress percentage (0–100) */
  percent: number;
  /** Bar colour variant */
  variant?: ProgressVariant;
  /** Optional label for screen readers */
  label?: string;
  className?: string;
}

const variantColors: Record<ProgressVariant, string> = {
  teal: "bg-[var(--teal-500)]",
  green: "bg-[var(--green-600)]",
  amber: "bg-[var(--amber-600)]",
  red: "bg-[var(--red-600)]",
};

/**
 * Shared progress bar — replaces 4+ inline implementations across
 * UserImportForm, BulkInvitationDashboard, BatchOperationsDashboard,
 * and ai-analysis-progress.
 */
export function ProgressBar({
  percent,
  variant = "teal",
  label,
  className = "",
}: ProgressBarProps) {
  const clamped = Math.min(100, Math.max(0, percent));

  return (
    <div
      className={`h-2 w-full overflow-hidden rounded-full bg-[var(--gray-100)] dark:bg-[var(--gray-300)] ${className}`}
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={label ?? `${clamped}% complete`}
    >
      <div
        className={`h-full rounded-full transition-all duration-300 ${variantColors[variant]}`}
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}
