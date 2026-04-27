"use client";

import * as React from "react";

export interface EmptyStateProps {
  /** Optional icon rendered above the title */
  icon?: React.ReactNode;
  /** Primary message */
  title: string;
  /** Secondary description */
  description?: string;
  /** Optional action button / link */
  action?: React.ReactNode;
}

/**
 * Consistent empty-state placeholder used when a list, table, or panel
 * has no data to display. Replaces ad-hoc <p> tags across 10+ components.
 */
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      {icon && (
        <div className="mb-4 text-[var(--gray-300)]" aria-hidden="true">
          {icon}
        </div>
      )}
      <h3 className="text-sm font-semibold text-[var(--gray-700)]">{title}</h3>
      {description && (
        <p className="mt-1 max-w-sm text-sm text-[var(--gray-500)]">
          {description}
        </p>
      )}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
