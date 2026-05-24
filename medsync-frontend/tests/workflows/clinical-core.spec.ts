import { test, expect } from "../fixtures/auth";
import { openFirstPatientFromSearch } from "../utils/patient-search";

/**
 * Smoke: doctor login, patient search, open chart, start encounter flow.
 * Requires E2E_DOCTOR_* credentials and a seeded patient matching the search query.
 */
test.describe("Core clinical workflow (smoke)", () => {
  test("doctor can search, open patient, and reach encounter form", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await openFirstPatientFromSearch(page);
    await page.getByRole("link", { name: /add encounter/i }).click();
    await page.waitForURL(/\/encounters\/new/);
    await expect(page.getByPlaceholder(/reason for visit|chief complaint/i).first()).toBeVisible({
      timeout: 10_000,
    });
  });
});
