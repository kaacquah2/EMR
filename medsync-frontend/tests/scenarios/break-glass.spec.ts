import { test, expect } from "../fixtures/auth";
import { openFirstPatientFromSearch } from "../utils/patient-search";

test.describe("Break-glass workflow", () => {
  test("doctor can open patient chart (break-glass UI when restricted)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await openFirstPatientFromSearch(page);

    const breakGlassOverlay = page.getByText(/emergency access|break.?glass|restricted/i);
    if (await breakGlassOverlay.isVisible().catch(() => false)) {
      const breakGlassBtn = page.getByRole("button", { name: /emergency access|break.?glass|override/i });
      await expect(breakGlassBtn).toBeVisible({ timeout: 5_000 });
      await breakGlassBtn.click();
      const reasonInput = page.getByPlaceholder(/reason|justify|emergency|medical need/i);
      await expect(reasonInput).toBeVisible({ timeout: 5_000 });
      await reasonInput.fill("Critical care requires immediate record access");
      await page.getByRole("button", { name: /confirm|access|override/i }).click();
      await expect(page.getByText(/access granted|emergency access active|override active/i)).toBeVisible({
        timeout: 10_000,
      });
    } else {
      await expect(page.getByText(/patient|record|encounter/i).first()).toBeVisible({ timeout: 10_000 });
    }
  });
});
