"use client";

import * as React from "react";

interface SlideOverProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  children: React.ReactNode;
}

export function SlideOver({ open, onOpenChange, title, children }: SlideOverProps) {
  if (!open) return null;

  return (
    <>
      <div
        className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm"
        onClick={() => onOpenChange(false)}
        aria-hidden="true"
      />
      <div className="fixed right-0 top-0 z-50 h-full w-full max-w-[480px] overflow-y-auto bg-white shadow-xl">
        <div className="flex h-14 items-center justify-between border-b border-[#CBD5E1] px-6">
          {title && (
            <h2 className="font-sora text-lg font-semibold text-[#0F172A]">
              {title}
            </h2>
          )}
          <button
            type="button"
            onClick={() => onOpenChange(false)}
            className="rounded p-2 text-[#64748B] hover:bg-[#F1F5F9] hover:text-[#0F172A]"
            aria-label="Close"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="p-6">{children}</div>
      </div>
    </>
  );
}
