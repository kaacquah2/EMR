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
  active: "bg-[#D1FAE5] text-[#047857]",
  pending: "bg-[#FEF3C7] text-[#B45309]",
  inactive: "bg-[#F1F5F9] text-[#64748B]",
  critical: "bg-[#FEE2E2] text-[#B91C1C]",
  success: "bg-[#D1FAE5] text-[#047857]",
  default: "bg-[#F1F5F9] text-[#334155]",
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

export { Badge };
