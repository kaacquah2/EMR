"use client";

import * as React from "react";

interface SlideOverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  children: React.ReactNode;
}

export function SlideOver({ open, onOpenChange, title, children }: SlideOverProps) {
  const panelRef = React.useRef<HTMLDivElement>(null);

  // Auto-focus the panel on open
  React.useEffect(() => {
    if (open && panelRef.current) {
      panelRef.current.focus();
    }
  }, [open]);

  // Close on Escape key
  React.useEffect(() => {
    if (!open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onOpenChange(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [open, onOpenChange]);

  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />
      <div
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ?? "Panel"}
        tabIndex={-1}
        className="fixed right-0 top-0 z-50 h-full w-full max-w-[480px] overflow-y-auto bg-white dark:bg-slate-800 dark:bg-slate-200 shadow-xl focus:outline-none"
      >
        <div className="flex h-14 items-center justify-between border-b border-[var(--gray-300)] dark:border-[#334155] px-6">
          {title && (
            <h2 className="font-sora text-lg font-semibold text-[var(--gray-900)]">
              {title}
            </h2>
          )}
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded p-2 text-[var(--gray-500)] hover:bg-[var(--gray-100)] dark:hover:bg-[#334155] hover:text-[var(--gray-900)]"
            aria-label="Close"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </>
  );
}
