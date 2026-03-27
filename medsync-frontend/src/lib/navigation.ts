/**
 * Navigation configuration for all user roles
 * Single source of truth for sidebar navigation structure
 */

export interface NavItem {
  href: string;
  label: string;
}

export interface NavigationOptions {
  /** For super_admin: whether view-as is active (hospital selected). */
  viewAsActive?: boolean;
}

const COMMON_NAV = {
  dashboard: { href: "/dashboard", label: "Dashboard" },
  patientSearch: { href: "/patients/search", label: "Patient Search" },
  appointments: { href: "/appointments", label: "Appointments" },
  admissions: { href: "/admissions", label: "Admissions" },
  alerts: { href: "/alerts", label: "Alerts" },
  referrals: { href: "/referrals", label: "Referrals" },
  userManagement: { href: "/admin/users", label: "User Management" },
  auditLogs: { href: "/admin/audit-logs", label: "Audit Logs" },
  facilities: { href: "/admin/facilities", label: "Facility config" },
  rbacReview: { href: "/admin/rbac-review", label: "RBAC review" },
  superAdminDashboard: { href: "/superadmin", label: "Dashboard" },
  superAdminHospitals: { href: "/superadmin/hospitals", label: "Hospitals" },
  crossFacilityMonitor: {
    href: "/superadmin/cross-facility-activity-log",
    label: "Cross-Facility Monitor",
  },
  superAdminAuditLogs: { href: "/superadmin/audit-logs", label: "Audit Logs" },
  superAdminUserManagement: { href: "/superadmin/user-management", label: "User Management" },
  superAdminFacilities: { href: "/superadmin/facilities", label: "Facilities" },
  superAdminBreakGlassReview: { href: "/superadmin/break-glass-review", label: "Break-glass review" },
  superAdminSystemHealth: { href: "/superadmin/system-health", label: "System health" },
  superAdminAiIntegration: { href: "/superadmin/ai-integration", label: "AI integration" },
};

export const navByRole: Record<string, NavItem[]> = {
  doctor: [
    COMMON_NAV.dashboard,
    { href: "/worklist", label: "Worklist" },
    { href: "/ai-insights", label: "AI Insights" },
    COMMON_NAV.patientSearch,
    COMMON_NAV.appointments,
    COMMON_NAV.alerts,
    COMMON_NAV.referrals,
  ],

  nurse: [
    COMMON_NAV.dashboard,
    { href: "/worklist", label: "Worklist" },
    { href: "/patients/search", label: "My Ward" },
    COMMON_NAV.appointments,
    COMMON_NAV.alerts,
    COMMON_NAV.admissions,
  ],

  receptionist: [
    COMMON_NAV.dashboard,
    COMMON_NAV.patientSearch,
    COMMON_NAV.appointments,
  ],

  lab_technician: [
    COMMON_NAV.dashboard,
    { href: "/lab/orders", label: "Lab Orders" },
  ],

  hospital_admin: [
    COMMON_NAV.dashboard,
    COMMON_NAV.patientSearch,
    COMMON_NAV.appointments,
    COMMON_NAV.admissions,
    COMMON_NAV.alerts,
    COMMON_NAV.referrals,
    COMMON_NAV.userManagement,
    COMMON_NAV.facilities,
    COMMON_NAV.rbacReview,
    COMMON_NAV.auditLogs,
  ],

  super_admin: [
    COMMON_NAV.referrals,
    COMMON_NAV.superAdminDashboard,
    COMMON_NAV.superAdminHospitals,
    COMMON_NAV.crossFacilityMonitor,
    COMMON_NAV.superAdminAuditLogs,
    COMMON_NAV.superAdminUserManagement,
    COMMON_NAV.superAdminBreakGlassReview,
    COMMON_NAV.superAdminFacilities,
    COMMON_NAV.superAdminSystemHealth,
    COMMON_NAV.superAdminAiIntegration,
  ],
};

export const KNOWN_ROLES = Object.keys(navByRole) as string[];

const MINIMAL_NAV: NavItem[] = [COMMON_NAV.dashboard];

function superAdminNavigation(options?: NavigationOptions): NavItem[] {
  const base = navByRole.super_admin;
  if (!options?.viewAsActive) return base;
  return [
    ...base,
    COMMON_NAV.patientSearch,
    COMMON_NAV.appointments,
    COMMON_NAV.admissions,
    COMMON_NAV.alerts,
  ];
}

export function getNavigation(role: string, options?: NavigationOptions): NavItem[] {
  if (role === "super_admin") return superAdminNavigation(options);
  return navByRole[role] ?? MINIMAL_NAV;
}

export function isRouteAccessible(role: string, route: string): boolean {
  const nav = getNavigation(role);
  return nav.some((item) => item.href === route);
}

const UUID_REGEX = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

function pathSegmentIsUuid(segment: string): boolean {
  return UUID_REGEX.test(segment);
}

const DOCTOR_EXACT_ALLOWED = new Set([
  "/dashboard",
  "/worklist",
  "/ai-insights",
  "/patients/search",
  "/appointments",
  "/alerts",
  "/referrals",
  "/unauthorized",
]);

function isDoctorPathnameAccessible(path: string): boolean {
  if (DOCTOR_EXACT_ALLOWED.has(path)) return true;
  const segments = path.split("/").filter(Boolean);
  if (segments[0] !== "patients" || !segments[1] || !pathSegmentIsUuid(segments[1])) {
    return false;
  }

  // Doctors can open patient chart and clinical subflows, but not registration/admissions management routes.
  if (segments.length === 2) return true;
  if (segments[2] === "ai-insights") return true;
  if (segments[2] === "admissions") return false;
  if (segments[2] === "encounter" || segments[2] === "encounters") return true;
  if (segments[2] === "records" || segments[2] === "vitals") return true;
  return false;
}

const NURSE_EXACT_ALLOWED = new Set([
  "/dashboard",
  "/worklist",
  "/patients/search",
  "/appointments",
  "/alerts",
  "/admissions",
  "/unauthorized",
]);

function isNursePathnameAccessible(path: string): boolean {
  if (NURSE_EXACT_ALLOWED.has(path)) return true;
  const segments = path.split("/").filter(Boolean);
  if (segments[0] !== "patients" || !segments[1] || !pathSegmentIsUuid(segments[1])) {
    return false;
  }

  // Nurse can open patient chart and nurse-facing clinical entry flows.
  if (segments.length === 2) return true;
  if (segments[2] === "vitals" && segments[3] === "new") return true;
  if (segments[2] === "records") return true;
  return false;
}

const LAB_TECH_EXACT_ALLOWED = new Set([
  "/dashboard",
  "/lab/orders",
  "/unauthorized",
]);

function isLabTechnicianPathnameAccessible(path: string): boolean {
  if (LAB_TECH_EXACT_ALLOWED.has(path)) return true;
  const segments = path.split("/").filter(Boolean);
  if (segments[0] !== "lab" || segments[1] !== "orders") return false;
  return !!segments[2] && pathSegmentIsUuid(segments[2]);
}

const RECEPTIONIST_EXACT_ALLOWED = new Set([
  "/dashboard",
  "/patients/search",
  "/appointments",
  "/unauthorized",
]);

function isReceptionistPathnameAccessible(path: string): boolean {
  return RECEPTIONIST_EXACT_ALLOWED.has(path);
}

export function isPathnameAccessible(role: string, pathname: string, options?: NavigationOptions): boolean {
  const path = pathname.replace(/\/$/, "") || "/";
  if (path === "/unauthorized") return true;
  if (path === "" || path === "/") return true;
  if (role === "doctor") return isDoctorPathnameAccessible(path);
  if (role === "nurse") return isNursePathnameAccessible(path);
  if (role === "lab_technician") return isLabTechnicianPathnameAccessible(path);
  if (role === "receptionist") return isReceptionistPathnameAccessible(path);

  const nav = getNavigation(role, options);

  if (nav.some((item) => item.href === path)) return true;

  const segments = path.split("/").filter(Boolean);

  if (segments[0] === "patients" && segments.length >= 2) {
    if (segments[1] === "search" || segments[1] === "register")
      return nav.some((item) => item.href === `/patients/${segments[1]}`);
    if (pathSegmentIsUuid(segments[1])) {
      if (segments[2] === "ai-insights") return role === "doctor";
      if (role === "receptionist") return false;
      return nav.some((item) => item.href === "/patients/search");
    }
  }

  if (segments[0] === "lab" && segments[1] === "orders" && segments.length >= 3) {
    return nav.some((item) => item.href === "/lab/orders");
  }

  if (segments[0] === "cross-facility-records" && segments.length >= 2 && pathSegmentIsUuid(segments[1])) {
    return nav.some((item) => item.href === "/referrals");
  }

  if (segments[0] === "admin" && segments.length >= 2) {
    const sub = `/${segments[0]}/${segments[1]}`;
    if (sub === "/admin/facilities") return role === "super_admin" || role === "hospital_admin";
    if (sub === "/admin/rbac-review") return role === "hospital_admin" || role === "super_admin";
    // Super Admin sidebar links to /superadmin/* which redirect here; nav hrefs differ so allow role explicitly.
    if (sub === "/admin/users" || sub === "/admin/audit-logs") {
      return role === "hospital_admin" || role === "super_admin";
    }
  }

  if (segments[0] === "superadmin" && segments.length >= 1) {
    const sub = `/${segments[0]}/${segments[1] ?? ""}`.replace(/\/$/, "");
    if (sub === "/superadmin") {
      return role === "super_admin";
    }
    if (sub === "/superadmin/hospitals" || sub === "/superadmin/cross-facility-activity-log") {
      return role === "super_admin";
    }
  }

  return false;
}
