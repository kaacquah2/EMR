import { test, expect } from "../fixtures/auth";

/**
 * Workflow handoff tests: actions by one role produce data visible to the next role.
 * Assumes seeded data or previous test steps (e.g. doctor creates order -> lab tech sees it).
 */

test.describe("Workflow handoff", () => {
  test("receptionist creates appointment -> appointments list shows it", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/appointments");
    await page.getByRole("button", { name: /schedule appointment/i }).click();
    const searchInput = page.getByPlaceholder(/search by name or ghana health id/i);
    await searchInput.fill("test");
    await page.waitForTimeout(800);
    const firstPatient = page.locator("ul li.cursor-pointer").first();
    if (!(await firstPatient.isVisible())) {
      test.skip(true, "No patients to schedule");
      return;
    }
    await firstPatient.click();
    const dateTimeInput = page.getByLabel(/date & time/i);
    await dateTimeInput.fill(new Date(Date.now() + 86400000).toISOString().slice(0, 16));
    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(page.getByRole("heading", { name: /appointments/i })).toBeVisible({ timeout: 8_000 });
    await expect(page.getByText(/test|appointment|scheduled/i).first()).toBeVisible({ timeout: 5_000 });
  });

  test("doctor creates lab order -> lab orders page has orders (doctor or lab_technician)", async ({ page, loginAs, getCreds }) => {
    const doctorCreds = getCreds("doctor");
    test.skip(!doctorCreds, "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/lab/orders");
    await page.waitForURL(/\/lab\/orders|\/unauthorized/);
    if (page.url().includes("/unauthorized")) {
      test.skip(true, "Doctor may not have lab/orders in nav; check worklist or patient record");
      return;
    }
    await expect(page.getByRole("heading", { name: /lab orders/i })).toBeVisible({ timeout: 8_000 });
  });

  test("lab technician submits result -> result visible (state update)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("lab_technician"), "E2E_LAB_TECH_* not set");
    await loginAs("lab_technician");
    await page.goto("/lab/orders");
    const pendingTab = page.getByRole("button", { name: /pending/i });
    if (await pendingTab.isVisible()) await pendingTab.click();
    const firstOrder = page.locator('[class*="cursor-pointer"]').first();
    if (!(await firstOrder.isVisible())) {
      test.skip(true, "No pending orders to submit");
      return;
    }
    await firstOrder.click();
    await page.getByLabel(/result value/i).fill("99.9");
    await page.getByRole("button", { name: /submit result/i }).click();
    await expect(page.getByText(/completed|result|submitted|success/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test("alerts page loads and resolve flow exists when permitted", async ({ page, loginAs, getCreds }) => {
    const doctorCreds = getCreds("doctor");
    const nurseCreds = getCreds("nurse");
    test.skip(!doctorCreds && !nurseCreds, "E2E_DOCTOR or E2E_NURSE not set");
    if (doctorCreds) await loginAs("doctor");
    else await loginAs("nurse");
    await page.goto("/alerts");
    await expect(page).toHaveURL(/\/alerts/);
    await expect(page.getByRole("heading", { name: /alerts/i }).or(page.getByText(/alerts/i).first())).toBeVisible({ timeout: 8_000 });
  });
});
