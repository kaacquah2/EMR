"use client";

import * as React from "react";

interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
}

const DialogContext = React.createContext<{
  open: boolean;
  onOpenChange: (open: boolean) => void;
} | null>(null);

function Dialog({ open, onOpenChange, children }: DialogProps) {
  return (
    <DialogContext.Provider value={{ open, onOpenChange }}>
      {children}
    </DialogContext.Provider>
  );
}

function DialogTrigger({
  asChild,
  children,
  ...props
}: {
  asChild?: boolean;
  children: React.ReactNode;
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const ctx = React.useContext(DialogContext);
  if (!ctx) return null;
  if (asChild && React.isValidElement(children)) {
    return React.cloneElement(children as React.ReactElement<{ onClick?: () => void }>, {
      onClick: () => ctx.onOpenChange(true),
    });
  }
  return (
    <button type="button" onClick={() => ctx.onOpenChange(true)} {...props}>
      {children}
    </button>
  );
}

function DialogPortal({ children }: { children: React.ReactNode }) {
  const ctx = React.useContext(DialogContext);
  if (!ctx?.open) return null;
  return <>{children}</>;
}

function DialogOverlay({
  className = "",
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(DialogContext);
  if (!ctx) return null;
  return (
    <div
      className={`fixed inset-0 z-50 bg-black/50 backdrop-blur-sm ${className}`}
      onClick={() => ctx.onOpenChange(false)}
      aria-hidden="true"
      {...props}
    />
  );
}

function DialogContent({
  className = "",
  children,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  const ctx = React.useContext(DialogContext);
  const contentRef = React.useRef<HTMLDivElement>(null);

  // Auto-focus the dialog on open
  React.useEffect(() => {
    if (ctx?.open && contentRef.current) {
      contentRef.current.focus();
    }
  }, [ctx?.open]);

  // Close on Escape key
  React.useEffect(() => {
    if (!ctx?.open) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        ctx.onOpenChange(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [ctx]);

  if (!ctx) return null;
  return (
    <div
      ref={contentRef}
      role="dialog"
      aria-modal="true"
      tabIndex={-1}
      className={`fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2 rounded-2xl bg-white dark:bg-[#1E293B] p-8 shadow-[0_20px_60px_rgba(0,0,0,0.15)] focus:outline-none ${className}`}
      onClick={(e) => e.stopPropagation()}
      {...props}
    >
      {children}
    </div>
  );
}

function DialogHeader({ className = "", ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={`mb-4 ${className}`} {...props} />;
}

function DialogTitle({ className = "", ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h2 className={`font-sora text-xl font-bold text-[var(--gray-900)] ${className}`} {...props} />
  );
}

function DialogClose({ className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  const ctx = React.useContext(DialogContext);
  if (!ctx) return null;
  return (
    <button
      type="button"
      className={`absolute right-4 top-4 text-[var(--gray-500)] hover:text-[var(--gray-700)] dark:hover:text-[var(--gray-300)] ${className}`}
      onClick={() => ctx.onOpenChange(false)}
      aria-label="Close"
      {...props}
    >
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <path d="M18 6L6 18M6 6l12 12" />
      </svg>
    </button>
  );
}

export {
  Dialog,
  DialogTrigger,
  DialogPortal,
  DialogOverlay,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogClose,
};
