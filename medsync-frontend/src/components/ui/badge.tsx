import * as React from "react";

export type BadgeVariant =
  | "active"
  | "pending"
  | "inactive"
  | "critical"
  | "success"
  | "default";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variantStyles: Record<BadgeVariant, string> = {
  active: "bg-[#D1FAE5] text-[#047857] dark:bg-[#047857]/20 dark:text-[#6EE7B7]",
  pending: "bg-[#FEF3C7] text-[#B45309] dark:bg-[#B45309]/20 dark:text-[#FDE68A]",
  inactive: "bg-[#F1F5F9] text-[#64748B] dark:bg-[#334155] dark:text-[#94A3B8]",
  critical: "bg-[#FEE2E2] text-[#B91C1C] dark:bg-[#B91C1C]/20 dark:text-[#FCA5A5]",
  success: "bg-[#D1FAE5] text-[#047857] dark:bg-[#047857]/20 dark:text-[#6EE7B7]",
  default: "bg-[#F1F5F9] text-[#334155] dark:bg-[#334155] dark:text-[#CBD5E1]",
};

/** MedSync Role Specs accent colours for role badge (sidebar/topbar). */
export const roleAccentColours: Record<string, string> = {
  super_admin: "#DC2626",
  hospital_admin: "#6D28D9",
  doctor: "#1D6FA4",
  nurse: "#059669",
  lab_technician: "#D97706",
  receptionist: "#0B8A96",
};

const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ className = "", variant = "default", ...props }, ref) => (
    <span
      ref={ref}
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-bold uppercase ${variantStyles[variant]} ${className}`}
      {...props}
    />
  )
);
Badge.displayName = "Badge";

/* ---- Triage Badge ---- */

export const triageVariants: Record<string, string> = {
  critical: "bg-[#FEE2E2] text-[#B91C1C] border-[#FECACA] dark:bg-[#B91C1C]/20 dark:text-[#FCA5A5] dark:border-[#B91C1C]/40",
  urgent:   "bg-[#FEF3C7] text-[#B45309] border-[#FDE68A] dark:bg-[#B45309]/20 dark:text-[#FDE68A] dark:border-[#B45309]/40",
  routine:  "bg-[#DBEAFE] text-[#1E40AF] border-[#BFDBFE] dark:bg-[#1E40AF]/20 dark:text-[#93C5FD] dark:border-[#1E40AF]/40",
};

function getTriageLabel(value?: string): "CRITICAL" | "URGENT" | "LESS URGENT" {
  const normalized = (value || "").trim().toLowerCase();
  if (normalized === "critical") return "CRITICAL";
  if (normalized === "urgent") return "URGENT";
  return "LESS URGENT";
}

export function triageSortRank(value?: string): number {
  const label = getTriageLabel(value);
  if (label === "CRITICAL") return 0;
  if (label === "URGENT") return 1;
  return 2;
}

export function TriageBadge({ triage }: { triage?: string }) {
  const label = getTriageLabel(triage);
  const key = label === "CRITICAL" ? "critical" : label === "URGENT" ? "urgent" : "routine";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${triageVariants[key]}`}
    >
      {label}
    </span>
  );
}

export { Badge };
