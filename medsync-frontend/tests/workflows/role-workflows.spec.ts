import { test, expect } from "../fixtures/auth";

/**
 * Role-based workflow E2E tests.
 * Validates primary navigation and basic dashboard visibility for each role.
 */

test.describe("Role-based Workflows", () => {
  test("Doctor workflow: Dashboard and Patient Search", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/dashboard");
    await expect(page.getByText(/dashboard|good (morning|afternoon|evening)|worklist/i).first()).toBeVisible({ timeout: 15_000 });
    
    await page.goto("/patients/search");
    await expect(page.getByPlaceholder(/search|name|ghana health id/i).first()).toBeVisible();
  });

  test("Nurse workflow: Dashboard and Worklist", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/dashboard");
    await expect(page.getByText(/dashboard|ward|good/i).first()).toBeVisible({ timeout: 15_000 });
    
    await page.goto("/worklist");
    await expect(page.getByText(/worklist|tasks|pending/i).first()).toBeVisible();
  });

  test("Lab Technician workflow: Lab Orders", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("lab_technician"), "E2E_LAB_TECH_* not set");
    await loginAs("lab_technician");
    await page.goto("/lab/orders");
    await expect(page.getByText(/lab orders|pending|results/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("Receptionist workflow: Patient Search", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/patients/search");
    await expect(page.getByPlaceholder(/search|name|ghana health id/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("Super Admin workflow: Hospital Management", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("super_admin"), "E2E_SUPER_ADMIN_* not set");
    await loginAs("super_admin");
    await page.goto("/superadmin");
    await expect(page.getByText(/super admin|hospitals|facilities/i).first()).toBeVisible({ timeout: 15_000 });
    
    await page.goto("/superadmin/hospitals");
    await expect(page.getByRole("heading", { name: /hospitals/i })).toBeVisible();
  });
});
