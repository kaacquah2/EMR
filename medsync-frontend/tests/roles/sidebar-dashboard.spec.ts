import { test, expect } from "../fixtures/auth";
import { SidebarPage } from "../pages/SidebarPage";
import { E2E_NAV_LABELS } from "../utils/constants";
import { NAV_BY_ROLE, ROLES, type Role } from "../utils/roles";

/** Sidebar label for each href (en). Nurse sees "My Ward" for patient search. */
const HREF_TO_LABEL: Record<string, string> = {
  "/dashboard": E2E_NAV_LABELS.Dashboard,
  "/worklist": E2E_NAV_LABELS.Worklist,
  "/patients/search": E2E_NAV_LABELS.PatientSearch,
  "/patients/register": E2E_NAV_LABELS.RegisterPatient,
  "/appointments": E2E_NAV_LABELS.Appointments,
  "/admissions": E2E_NAV_LABELS.Admissions,
  "/alerts": E2E_NAV_LABELS.Alerts,
  "/referrals": E2E_NAV_LABELS.Referrals,
  "/admin/users": E2E_NAV_LABELS.UserManagement,
  "/admin/audit-logs": E2E_NAV_LABELS.AuditLogs,
  "/admin/facilities": E2E_NAV_LABELS.Facilities,
  "/superadmin": E2E_NAV_LABELS.SuperAdmin,
  "/lab/orders": E2E_NAV_LABELS.LabOrders,
};

/** Nurse has "My Ward" instead of "Patient Search" for /patients/search. */
function getVisibleLabels(role: Role): string[] {
  const hrefs = NAV_BY_ROLE[role];
  return hrefs.map((href) => (role === "nurse" && href === "/patients/search" ? E2E_NAV_LABELS.MyWard : HREF_TO_LABEL[href] ?? href));
}

/** All labels that must not appear for this role. */
const FORBIDDEN_LABELS: Record<Role, string[]> = {
  super_admin: [],
  hospital_admin: [E2E_NAV_LABELS.SuperAdmin, E2E_NAV_LABELS.Facilities],
  doctor: [E2E_NAV_LABELS.UserManagement, E2E_NAV_LABELS.AuditLogs, E2E_NAV_LABELS.Facilities, E2E_NAV_LABELS.SuperAdmin, E2E_NAV_LABELS.LabOrders],
  nurse: [E2E_NAV_LABELS.UserManagement, E2E_NAV_LABELS.AuditLogs, E2E_NAV_LABELS.Facilities, E2E_NAV_LABELS.SuperAdmin, E2E_NAV_LABELS.LabOrders, E2E_NAV_LABELS.Referrals, E2E_NAV_LABELS.RegisterPatient],
  receptionist: [E2E_NAV_LABELS.Worklist, E2E_NAV_LABELS.Admissions, E2E_NAV_LABELS.Alerts, E2E_NAV_LABELS.Referrals, E2E_NAV_LABELS.UserManagement, E2E_NAV_LABELS.AuditLogs, E2E_NAV_LABELS.Facilities, E2E_NAV_LABELS.SuperAdmin, E2E_NAV_LABELS.LabOrders, E2E_NAV_LABELS.RegisterPatient],
  lab_technician: [E2E_NAV_LABELS.Worklist, E2E_NAV_LABELS.PatientSearch, E2E_NAV_LABELS.RegisterPatient, E2E_NAV_LABELS.Appointments, E2E_NAV_LABELS.Admissions, E2E_NAV_LABELS.Alerts, E2E_NAV_LABELS.Referrals, E2E_NAV_LABELS.UserManagement, E2E_NAV_LABELS.AuditLogs, E2E_NAV_LABELS.Facilities, E2E_NAV_LABELS.SuperAdmin],
};

test.describe("Sidebar and dashboard by role", () => {
  for (const role of ROLES) {
    test(`${role}: sees correct sidebar links and dashboard`, async ({ page, loginAs, getCreds }) => {
      const creds = getCreds(role);
      test.skip(!creds, `E2E_${role.toUpperCase().replace("_", "_")}_EMAIL/PASSWORD not set`);
      const ok = await loginAs(role);
      expect(ok).toBe(true);
      const sidebar = new SidebarPage(page);
      const visible = getVisibleLabels(role);
      const forbidden = FORBIDDEN_LABELS[role];
      await sidebar.expectVisibleNavLabels(visible, forbidden);
      await sidebar.expectDashboardVisible();
      await page.goto("/dashboard");
      await expect(page).toHaveURL(/\/dashboard/);
      await expect(page.getByText(/dashboard|good (morning|afternoon|evening)|worklist|appointments|lab orders/i).first()).toBeVisible({ timeout: 10_000 });
    });
  }
});
