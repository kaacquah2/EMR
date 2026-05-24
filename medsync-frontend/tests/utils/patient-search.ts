import { expect, type Page } from "@playwright/test";

/** Run a local patient search and open the first result chart. */
export async function openFirstPatientFromSearch(page: Page, query = "test"): Promise<void> {
  await page.goto("/patients/search");
  await page.getByTestId("patient-search-input").fill(query);
  await page.getByTestId("patient-search-submit").click();
  const viewLink = page.getByRole("link", { name: /^view$/i }).first();
  await expect(viewLink).toBeVisible({ timeout: 15_000 });
  await viewLink.click();
  await page.waitForURL(/\/patients\/[^/]+$/);
}
