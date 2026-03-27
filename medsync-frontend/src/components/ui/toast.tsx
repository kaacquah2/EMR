"use client";

import * as React from "react";
import type { ToastVariant } from "@/lib/toast-context";

const variantStyles: Record<ToastVariant, string> = {
  error: "bg-[#FEF2F2] border-[#FECACA] text-[#B91C1C]",
  success: "bg-[#F0FDF4] border-[#BBF7D0] text-[#15803D]",
  info: "bg-[#F0F9FF] border-[#BAE6FD] text-[#0C1F3D]",
};

export function Toast({
  message,
  variant,
  onDismiss,
}: {
  message: string;
  variant: ToastVariant;
  onDismiss: () => void;
}) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 shadow-sm ${variantStyles[variant]}`}
      role="alert"
    >
      <div className="flex items-start justify-between gap-3">
        <p className="text-sm font-medium flex-1">{message}</p>
        <button
          type="button"
          onClick={onDismiss}
          className="shrink-0 rounded p-1 hover:opacity-80 focus:outline-none focus-visible:ring-2 focus-visible:ring-[#0B8A96]"
          aria-label="Dismiss"
        >
          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}
