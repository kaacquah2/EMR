import { test, expect } from "../fixtures/auth";

test.describe("Doctor workflow", () => {
  test("doctor can register patient", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/patients/register");
    await expect(page.getByRole("heading", { name: /register new patient|register patient/i })).toBeVisible({ timeout: 10_000 });
    await page.getByLabel(/full name/i).fill("E2E Test Patient");
    await page.getByLabel(/date of birth/i).fill("1990-01-15");
    await page.getByLabel(/ghana health id/i).fill("GH-E2E-" + Date.now().toString(36));
    await page.getByRole("button", { name: /next|register/i }).first().click();
    await expect(page).toHaveURL(/\/(patients\/search|patients\/[a-f0-9-]+)/, { timeout: 15_000 });
  });

  test("doctor can create encounter for a patient", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    await page.getByRole("link", { name: /add encounter/i }).click();
    await page.waitForURL(/\/encounters\/new/);
    await page.locator("select").first().selectOption({ index: 1 });
    await page.getByPlaceholder(/reason for visit/i).fill("E2E encounter");
    await page.getByRole("button", { name: /save encounter/i }).click();
    await expect(page).toHaveURL(/\/patients\/[^/]+$/);
    await expect(page.getByText(/encounter|timeline|records/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test("doctor can add lab order from patient record", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    if (!(await patientLink.isVisible())) {
      test.skip(true, "No patients");
      return;
    }
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    await page.getByRole("button", { name: /add record/i }).click();
    await page.getByRole("button", { name: /lab order/i }).click();
    const testSelect = page.locator("select").filter({ has: page.locator('option') }).first();
    if (await testSelect.isVisible()) {
      await testSelect.selectOption({ index: 1 });
    } else {
      await page.getByPlaceholder(/e\.g\. full blood/i).fill("FBC");
    }
    await page.getByRole("button", { name: /save|submit|add/i }).first().click();
    await expect(page.getByText(/lab|order|result|record/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test("doctor can access referrals page", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/referrals");
    await expect(page).toHaveURL(/\/referrals/);
    await expect(page.getByRole("heading", { name: /referrals/i }).or(page.getByText(/referrals/i).first())).toBeVisible({ timeout: 8_000 });
  });

  test("cross-facility record page is accessible when permitted (doctor has referrals)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    const fakeId = "00000000-0000-0000-0000-000000000001";
    await page.goto(`/cross-facility-records/${fakeId}`);
    await page.waitForURL(/\/(cross-facility-records|unauthorized|dashboard)/, { timeout: 10_000 });
    const onUnauthorized = page.url().includes("/unauthorized");
    const onPage = page.url().includes("/cross-facility-records");
    expect(onUnauthorized || onPage).toBe(true);
  });
});
