import { test, expect } from "../fixtures/auth";

test.describe("Super admin workflow", () => {
  test("super_admin can view facilities", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("super_admin"), "E2E_SUPER_ADMIN_* not set");
    await loginAs("super_admin");
    await page.goto("/admin/facilities");
    await expect(page).toHaveURL(/\/admin\/facilities/);
    await expect(page.getByRole("heading", { name: /facilities|hospitals/i }).or(page.getByText(/facilities|hospitals/i).first())).toBeVisible({ timeout: 10_000 });
  });

  test("super_admin can view superadmin page", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("super_admin"), "E2E_SUPER_ADMIN_* not set");
    await loginAs("super_admin");
    await page.goto("/superadmin");
    await expect(page).toHaveURL(/\/superadmin/);
    await expect(page.getByText(/super admin|system|health|hospitals/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test("super_admin can set view-as hospital and register patient", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("super_admin"), "E2E_SUPER_ADMIN_* not set");
    await loginAs("super_admin");
    await page.goto("/dashboard");
    const viewAsSelect = page.locator("select").filter({ has: page.getByRole("option", { name: /all hospitals/i }) });
    if (await viewAsSelect.isVisible()) {
      await viewAsSelect.selectOption({ index: 1 });
      await expect(page.getByText(/viewing as|operating in/i)).toBeVisible();
    }
    await page.goto("/patients/register");
    await expect(page.getByRole("heading", { name: /register new patient|register patient/i })).toBeVisible({ timeout: 10_000 });
    const facilitySelect = page.getByLabel(/register patient at facility|select facility/i);
    if (await facilitySelect.isVisible()) {
      await facilitySelect.selectOption({ index: 1 });
    }
    await page.getByLabel(/full name/i).fill("E2E SuperAdmin Patient");
    await page.getByLabel(/date of birth/i).fill("1990-01-15");
    await page.getByLabel(/ghana health id/i).fill("GH-SA-" + Date.now().toString(36));
    await page.getByRole("button", { name: /next: medical|register/i }).first().click();
    await expect(page).toHaveURL(/\/(patients\/search|patients\/[a-f0-9-]+)/, { timeout: 15_000 });
  });
});
