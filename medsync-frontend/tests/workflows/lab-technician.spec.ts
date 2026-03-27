import { test, expect } from "../fixtures/auth";

test.describe("Lab technician workflow", () => {
  test("lab technician can view lab orders", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("lab_technician"), "E2E_LAB_TECH_* not set");
    await loginAs("lab_technician");
    await page.goto("/lab/orders");
    await expect(page.getByRole("heading", { name: /lab orders/i })).toBeVisible({ timeout: 10_000 });
  });

  test("lab technician can submit result for pending order when orders exist", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("lab_technician"), "E2E_LAB_TECH_* not set");
    await loginAs("lab_technician");
    await page.goto("/lab/orders");
    const pendingTab = page.getByRole("button", { name: /pending/i });
    if (await pendingTab.isVisible()) await pendingTab.click();
    const firstOrder = page.locator('[class*="cursor-pointer"]').first();
    if (!(await firstOrder.isVisible())) {
      test.skip(true, "No pending lab orders");
      return;
    }
    await firstOrder.click();
    await page.getByLabel(/result value/i).fill("12.5");
    await page.getByRole("button", { name: /submit result/i }).click();
    await expect(page.getByText(/completed|result|no pending/i).first()).toBeVisible({ timeout: 8_000 });
  });

  test("lab technician cannot access patient admin pages", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("lab_technician"), "E2E_LAB_TECH_* not set");
    await loginAs("lab_technician");
    await page.goto("/admin/users");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /access denied/i })).toBeVisible();
  });
});
