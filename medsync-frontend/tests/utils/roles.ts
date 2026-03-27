/**
 * Role-to-routes mapping for E2E. Mirrors src/lib/navigation.ts navByRole.
 * Used to assert sidebar visibility and route authorization.
 */
export const ROLES = [
  "super_admin",
  "hospital_admin",
  "doctor",
  "nurse",
  "receptionist",
  "lab_technician",
] as const;

export type Role = (typeof ROLES)[number];

/** Routes each role has in sidebar (hrefs). */
export const NAV_BY_ROLE: Record<Role, string[]> = {
  doctor: [
    "/dashboard",
    "/worklist",
    "/patients/search",
    "/patients/register",
    "/appointments",
    "/alerts",
    "/referrals",
    "/admissions",
  ],
  nurse: [
    "/dashboard",
    "/worklist",
    "/patients/search", // My Ward label
    "/appointments",
    "/alerts",
    "/admissions",
  ],
  receptionist: ["/dashboard", "/patients/search", "/appointments"],
  lab_technician: ["/dashboard", "/lab/orders"],
  hospital_admin: [
    "/dashboard",
    "/patients/search",
    "/appointments",
    "/admissions",
    "/alerts",
    "/referrals",
    "/admin/users",
    "/admin/audit-logs",
  ],
  super_admin: [
    "/dashboard",
    "/patients/search",
    "/appointments",
    "/admissions",
    "/alerts",
    "/referrals",
    "/admin/facilities",
    "/admin/users",
    "/admin/audit-logs",
    "/superadmin",
  ],
};

/** Routes that must be forbidden for a role (direct URL access leads to /unauthorized). */
export const FORBIDDEN_BY_ROLE: Record<Role, string[]> = {
  receptionist: ["/admin/users", "/admin/audit-logs", "/admin/facilities", "/superadmin", "/lab/orders", "/referrals", "/admissions", "/patients/register", "/worklist"],
  nurse: ["/admin/users", "/admin/audit-logs", "/admin/facilities", "/superadmin", "/lab/orders", "/referrals", "/patients/register"],
  lab_technician: ["/admin/users", "/admin/audit-logs", "/admin/facilities", "/superadmin", "/referrals", "/admissions", "/appointments", "/patients/search", "/patients/register", "/worklist"],
  doctor: ["/admin/users", "/admin/audit-logs", "/admin/facilities", "/superadmin"],
  hospital_admin: ["/superadmin", "/admin/facilities"],
  super_admin: [],
};
