import { test, expect } from "../fixtures/auth";

test.describe("AI Insights workflow", () => {
  test("doctor can open AI insights for a patient", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    if (!(await patientLink.isVisible())) {
      test.skip(true, "No patients for AI insights test");
      return;
    }
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    const patientId = page.url().split("/patients/")[1]?.split("/")[0] ?? "";
    if (!patientId) {
      test.skip(true, "Could not get patient id");
      return;
    }
    await page.goto(`/patients/${patientId}/ai-insights`);
    await expect(
      page.getByRole("heading", { name: /AI Clinical Insights|AI insights/i })
    ).toBeVisible({ timeout: 15_000 });
  });

  test("AI insights page shows analysis or loading state", async ({ page, loginAs, getCreds }) => {
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
    const patientId = page.url().split("/patients/")[1]?.split("/")[0] ?? "";
    if (!patientId) {
      test.skip(true, "Could not get patient id");
      return;
    }
    await page.goto(`/patients/${patientId}/ai-insights`);
    await expect(
      page.getByText(/AI Clinical Insights|Running comprehensive|Refresh Analysis|Risk|Triage|Clinical Summary/i)
    ).toBeVisible({ timeout: 20_000 });
  });
});
