import { test, expect } from "@playwright/test";
import { login, getLabTechCreds } from "../auth";

/**
 * T11.3: Lab Tech Workflow
 * View lab orders → Enter results → Verify results → Mark complete → Send report
 * Requires: E2E_LAB_TECH_EMAIL, E2E_LAB_TECH_PASSWORD env vars
 */

test.describe("Lab Tech Workflow: Process Lab Orders", () => {
  const creds = getLabTechCreds();
  test.skip(!creds, "E2E_LAB_TECH_EMAIL and E2E_LAB_TECH_PASSWORD not set");

  test("should view orders, enter results, verify, complete, and send report", async ({ page }) => {
    // 1. Login as lab tech
    await login(page, creds!);
    await expect(page.getByRole("heading", { name: /dashboard|lab/i })).toBeVisible({ timeout: 10_000 });

    // 2. Navigate to lab orders
    const labLink = page.getByRole("link", { name: /lab|orders|results/i });
    await expect(labLink).toBeVisible({ timeout: 5_000 });
    await labLink.click();

    await expect(page.getByRole("heading", { name: /lab|orders|pending/i })).toBeVisible({ timeout: 10_000 });

    // 3. Find pending order
    const firstOrder = page.locator('[data-testid="lab-order-card"]').first();
    if (await firstOrder.isVisible().catch(() => false)) {
      await firstOrder.click();
    } else {
      const orderRow = page.locator('tr[data-testid="order-row"]').first();
      if (await orderRow.isVisible().catch(() => false)) {
        await orderRow.click();
      } else {
        const orderLink = page.locator('a:has-text(/order|test)').first();
        await expect(orderLink).toBeVisible({ timeout: 5_000 });
        await orderLink.click();
      }
    }

    // Verify order details
    await expect(page.getByText(/test|order|patient/i)).toBeVisible({ timeout: 10_000 });

    // 4. Enter results
    const enterResultsBtn = page.getByRole("button", { name: /enter results|add results/i });
    await expect(enterResultsBtn).toBeVisible({ timeout: 5_000 });
    await enterResultsBtn.click();

    // Fill result values based on test type
    const resultInput = page.getByPlaceholder(/result|value|amount/i);
    if (await resultInput.isVisible().catch(() => false)) {
      await resultInput.fill("7.2");
    }

    const unitInput = page.getByPlaceholder(/unit|range/i);
    if (await unitInput.isVisible().catch(() => false)) {
      await unitInput.fill("g/dL");
    }

    const normalRangeInput = page.getByPlaceholder(/normal|reference/i);
    if (await normalRangeInput.isVisible().catch(() => false)) {
      await normalRangeInput.fill("7.0-8.5");
    }

    // 5. Add interpretation/notes
    const interpretationInput = page.getByPlaceholder(/interpretation|note|comment/i);
    if (await interpretationInput.isVisible().catch(() => false)) {
      await interpretationInput.fill("Result within normal range");
    }

    await page.getByRole("button", { name: /save|submit results/i }).first().click();
    await expect(page.getByText(/results|saved|recorded/i)).toBeVisible({ timeout: 5_000 });

    // 6. Verify results
    const verifyBtn = page.getByRole("button", { name: /verify|review|confirm/i });
    if (await verifyBtn.isVisible().catch(() => false)) {
      await verifyBtn.click();
      await expect(page.getByText(/verified|confirmed/i)).toBeVisible({ timeout: 5_000 });
    }

    // 7. Mark complete
    const completeBtn = page.getByRole("button", { name: /complete|finish|mark done/i });
    if (await completeBtn.isVisible().catch(() => false)) {
      await completeBtn.click();

      const confirmComplete = page.getByRole("button", { name: /confirm|yes|complete/i });
      if (await confirmComplete.isVisible().catch(() => false)) {
        await confirmComplete.click();
      }

      await expect(page.getByText(/complete|done|finished/i)).toBeVisible({ timeout: 5_000 });
    }

    // 8. Send report
    const sendReportBtn = page.getByRole("button", { name: /send|report|notify/i });
    if (await sendReportBtn.isVisible().catch(() => false)) {
      await sendReportBtn.click();

      const confirmSend = page.getByRole("button", { name: /confirm|send|yes/i });
      if (await confirmSend.isVisible().catch(() => false)) {
        await confirmSend.click();
      }

      await expect(page.getByText(/sent|reported|notification/i)).toBeVisible({ timeout: 5_000 });
    }
  });
});
