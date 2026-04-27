"use client";

import * as React from "react";
import { Button } from "@/components/ui/button";

export interface ErrorBannerProps {
  /** Error message to display */
  message: string;
  /** Optional retry callback — renders a "Retry" button */
  onRetry?: () => void;
}

/**
 * Inline error banner for data-fetch failures.
 * Replaces inconsistent inline error divs across feature components.
 */
export function ErrorBanner({ message, onRetry }: ErrorBannerProps) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-[var(--red-600)]/30 bg-[#FEF2F2] p-4 text-sm text-[var(--red-600)] dark:bg-[#450A0A] dark:border-[var(--red-600)]/40 dark:text-[#FCA5A5]"
    >
      <p>{message}</p>
      {onRetry && (
        <Button
          size="sm"
          variant="ghost"
          onClick={onRetry}
          className="mt-2"
        >
          Retry
        </Button>
      )}
    </div>
  );
}
