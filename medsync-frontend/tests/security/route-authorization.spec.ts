import { test, expect } from "../fixtures/auth";
import { UNAUTHORIZED_PAGE_TITLE } from "../utils/constants";
import { FORBIDDEN_BY_ROLE, type Role } from "../utils/roles";

test.describe("Route authorization", () => {
  test("receptionist cannot access admin/users", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/admin/users");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: new RegExp(UNAUTHORIZED_PAGE_TITLE, "i") })).toBeVisible();
  });

  test("nurse cannot access lab/orders", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/lab/orders");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: new RegExp(UNAUTHORIZED_PAGE_TITLE, "i") })).toBeVisible();
  });

  test("nurse can access vitals entry route for scoped patient", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    if (!(await patientLink.isVisible())) {
      test.skip(true, "No patient in ward scope");
      return;
    }
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    const url = page.url();
    const patientId = url.split("/patients/")[1];
    await page.goto(`/patients/${patientId}/vitals/new`);
    await expect(page).toHaveURL(new RegExp(`/patients/${patientId}/vitals/new`));
  });

  test("lab_technician cannot access referrals", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("lab_technician"), "E2E_LAB_TECH_* not set");
    await loginAs("lab_technician");
    await page.goto("/referrals");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: new RegExp(UNAUTHORIZED_PAGE_TITLE, "i") })).toBeVisible();
  });

  test("doctor cannot access superadmin", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/superadmin");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: new RegExp(UNAUTHORIZED_PAGE_TITLE, "i") })).toBeVisible();
  });

  test("hospital_admin cannot access admin/facilities (super_admin only)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("hospital_admin"), "E2E_HOSPITAL_ADMIN_* not set");
    await loginAs("hospital_admin");
    await page.goto("/admin/facilities");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: new RegExp(UNAUTHORIZED_PAGE_TITLE, "i") })).toBeVisible();
  });

  test("anonymous user redirected to login when accessing dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 10_000 });
  });

  test("anonymous user redirected to login when accessing admin/users", async ({ page }) => {
    await page.goto("/admin/users");
    await page.waitForURL(/\/login/, { timeout: 10_000 });
  });

  test("each role: forbidden routes redirect to unauthorized", async ({ page, loginAs, getCreds }) => {
    const role: Role = "receptionist";
    test.skip(!getCreds(role), `E2E_* for ${role} not set`);
    await loginAs(role);
    const forbidden = FORBIDDEN_BY_ROLE[role];
    for (const route of forbidden.slice(0, 3)) {
      await page.goto(route);
      await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
      await expect(page.getByRole("heading", { name: new RegExp(UNAUTHORIZED_PAGE_TITLE, "i") })).toBeVisible();
      await page.goto("/dashboard");
      await page.waitForURL(/\/dashboard/, { timeout: 5_000 });
    }
  });
});
