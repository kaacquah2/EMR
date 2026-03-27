/**
 * E2E constants. Nav labels match `lib/navigation.ts` sidebar copy.
 */
export const E2E_TIMEOUT = 15_000;
export const E2E_NAV_LABELS = {
  Dashboard: "Dashboard",
  Worklist: "Worklist",
  PatientSearch: "Patient Search",
  RegisterPatient: "Register Patient",
  Appointments: "Appointments",
  Admissions: "Admissions",
  Alerts: "Alerts",
  Referrals: "Referrals",
  UserManagement: "User Management",
  AuditLogs: "Audit Logs",
  Facilities: "Facilities",
  SuperAdmin: "Super Admin",
  LabOrders: "Lab Orders",
  MyWard: "My Ward",
  LogOut: "Log out",
} as const;

export const UNAUTHORIZED_PAGE_TITLE = "Access denied";
export const UNAUTHORIZED_PAGE_MESSAGE = "You do not have permission to view this page.";
export const LOGIN_SIGN_IN_TITLE = "Sign in to MedSync";
