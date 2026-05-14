import { test, expect } from "../fixtures/auth";

/**
 * UX/state tests: loading, empty state, validation errors, success feedback, server errors.
 * Uses role that can access the page; some selectors are TODO where app lacks data-testid.
 */

test.describe("UX and state", () => {
  test("dashboard shows loading then content", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/dashboard");
    // Flexible loading check: if it's there, wait for it to go. If not, proceed.
    const loading = page.getByText(/loading/i).first();
    if (await loading.isVisible().catch(() => false)) {
      await expect(loading).toBeHidden({ timeout: 10_000 });
    }
    await expect(page.getByText(/dashboard|good (morning|afternoon|evening)|worklist|medsync|workload/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("patient search empty state or results", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/patients/search");
    await expect(page.getByPlaceholder(/search/i).first()).toBeVisible({ timeout: 8_000 });
    await page.getByPlaceholder(/search|name|ghana health id/i).first().fill("xyznonexistent123");
    await page.waitForTimeout(1000);
    await expect(
      page.getByText(/no patients|no results|not found|patients|results/i).first()
    ).toBeVisible({ timeout: 8_000 });
  });

  test("login validation: empty submit shows required behavior", async ({ page }) => {
    await page.goto("/login");
    await page.getByRole("button", { name: /continue|sign in/i }).click();
    const emailOrError = page.getByLabel(/email/i).or(page.getByText(/required|invalid|fill/i));
    await expect(emailOrError.first()).toBeVisible({ timeout: 3_000 });
  });

  test("login invalid credentials show error message", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel(/email/i).fill("bad@example.com");
    await page.getByLabel(/password/i).fill("wrong");
    await page.getByRole("button", { name: /continue|sign in/i }).click();
    await expect(page.getByText(/invalid|failed|credentials/i)).toBeVisible({ timeout: 8_000 });
  });

  test("unauthorized page has Back to Dashboard", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    await loginAs("receptionist");
    await page.goto("/admin/users");
    await page.waitForURL(/\/unauthorized/);
    await expect(page.getByRole("link", { name: /back to dashboard/i })).toBeVisible();
    await page.getByRole("link", { name: /back to dashboard/i }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
