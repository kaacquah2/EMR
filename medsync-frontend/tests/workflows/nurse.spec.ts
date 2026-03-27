import { test, expect } from "../fixtures/auth";

test.describe("Nurse workflow", () => {
  test("nurse can search patient (My Ward)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/patients/search");
    await expect(page).toHaveURL(/\/patients\/search/);
    await expect(page.getByPlaceholder(/search|name|ward/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test("nurse can view admissions", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/admissions");
    await expect(page).toHaveURL(/\/admissions/);
    await expect(page.getByRole("heading", { name: /admissions/i }).or(page.getByText(/admissions/i).first())).toBeVisible({ timeout: 10_000 });
  });

  test("nurse worklist shows ward workflow tabs", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/worklist");
    await expect(page).toHaveURL(/\/worklist/);
    await expect(page.getByRole("button", { name: /beds/i })).toBeVisible({ timeout: 10_000 });
    await expect(page.getByRole("button", { name: /dispense/i })).toBeVisible();
    await expect(page.getByRole("button", { name: /handover/i })).toBeVisible();
  });

  test("nurse cannot access admin modules", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/admin/users");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /access denied/i })).toBeVisible();
  });

  test("nurse can open patient and see vitals/records if permitted", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("nurse"), "E2E_NURSE_* not set");
    await loginAs("nurse");
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    if (!(await patientLink.isVisible())) {
      test.skip(true, "No patients in search");
      return;
    }
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    await expect(page.getByText(/demographics|vitals|records|clinical|patient/i).first()).toBeVisible({ timeout: 10_000 });
  });
});
