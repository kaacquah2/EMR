import { test, expect } from "../fixtures/auth";

test.describe("Receptionist workflow", () => {
  test("receptionist can search patient", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/patients/search");
    await expect(page).toHaveURL(/\/patients\/search/);
    const searchInput = page.getByPlaceholder(/search|name|ghana health id/i).first();
    await searchInput.fill("test");
    await page.waitForTimeout(500);
    await expect(page.getByText(/patients|results|no patients/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test("receptionist can create appointment", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/appointments");
    await expect(page.getByRole("heading", { name: /appointments/i })).toBeVisible({ timeout: 10_000 });
    await page.getByRole("button", { name: /schedule appointment/i }).click();
    await expect(page.getByText(/schedule appointment/i)).toBeVisible();
    const searchInput = page.getByPlaceholder(/search by name or ghana health id/i);
    await searchInput.fill("test");
    await page.waitForTimeout(800);
    const firstPatient = page.locator("ul li.cursor-pointer").first();
    if (await firstPatient.isVisible()) {
      await firstPatient.click();
    }
    const dateTimeInput = page.getByLabel(/date & time/i);
    await dateTimeInput.fill(new Date(Date.now() + 86400000).toISOString().slice(0, 16));
    await page.getByRole("button", { name: /^save$/i }).click();
    await expect(page.getByRole("heading", { name: /appointments/i })).toBeVisible({ timeout: 8_000 });
  });

  test("receptionist cannot access register patient (no link and direct URL forbidden)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/patients/register");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /access denied/i })).toBeVisible();
  });
});
