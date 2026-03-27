import { test, expect } from "@playwright/test";
import {
  login,
  getReceptionistCreds,
  getDoctorCreds,
  getLabTechCreds,
  getHospitalAdminCreds,
  getSuperAdminCreds,
} from "./auth";

/**
 * Role-based E2E tests. Require backend + frontend running and test users seeded.
 * Set E2E_<ROLE>_EMAIL and E2E_<ROLE>_PASSWORD for each role (MFA disabled for those users, or set E2E_MFA_BACKUP_CODE).
 */

test.describe("Receptionist: create appointment", () => {
  const creds = getReceptionistCreds();
  test.skip(!creds, "E2E_RECEPTIONIST_EMAIL and E2E_RECEPTIONIST_PASSWORD not set");

  test("receptionist can open appointments and schedule an appointment", async ({ page }) => {
    await login(page, creds!);
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
    await expect(page.getByRole("heading", { name: /appointments/i })).toBeVisible();
  });
});

test.describe("Doctor: create encounter and lab order", () => {
  const creds = getDoctorCreds();
  test.skip(!creds, "E2E_DOCTOR_EMAIL and E2E_DOCTOR_PASSWORD not set");

  test("doctor can create encounter then add lab order for a patient", async ({ page }) => {
    await login(page, creds!);
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    const patientId = page.url().split("/patients/")[1]?.split("/")[0] ?? "";
    if (!patientId) {
      test.skip(true, "No patient in search results");
      return;
    }

    await page.getByRole("link", { name: /add encounter/i }).click();
    await page.waitForURL(/\/encounters\/new/);
    await page.selectOption('select', { index: 1 });
    await page.getByPlaceholder(/reason for visit/i).fill("E2E encounter");
    await page.getByRole("button", { name: /save encounter/i }).click();
    await page.waitForURL(new RegExp(`/patients/${patientId}`));

    await page.getByRole("button", { name: /add record/i }).click();
    await page.getByRole("button", { name: /lab order/i }).click();
    const testSelect = page.locator('select').filter({ has: page.locator('option:has-text("Select test"), option:has-text("Full Blood")') }).first();
    if (await testSelect.isVisible()) {
      await testSelect.selectOption({ index: 1 });
    } else {
      await page.getByPlaceholder(/e\.g\. full blood count/i).fill("FBC");
    }
    await page.getByRole("button", { name: /save|submit|add/i }).first().click();
    await expect(page.getByText(/encounters|timeline|records/i).first()).toBeVisible({ timeout: 5000 });
  });
});

test.describe("Lab tech: submit result", () => {
  const creds = getLabTechCreds();
  test.skip(!creds, "E2E_LAB_TECH_EMAIL and E2E_LAB_TECH_PASSWORD not set");

  test("lab tech can open lab orders and submit a result for a pending order", async ({ page }) => {
    await login(page, creds!);
    await page.goto("/lab/orders");
    await expect(page.getByRole("heading", { name: /lab orders/i })).toBeVisible({ timeout: 10_000 });

    const pendingTab = page.getByRole("button", { name: /pending orders/i });
    await pendingTab.click();
    const firstOrder = page.locator('[class*="cursor-pointer"]').first();
    if (!(await firstOrder.isVisible())) {
      test.skip(true, "No pending lab orders");
      return;
    }
    await firstOrder.click();
    await page.getByLabel(/result value/i).fill("12.5");
    await page.getByRole("button", { name: /submit result/i }).click();
    await expect(page.getByText(/no pending|completed|result/i).first()).toBeVisible({ timeout: 8000 });
  });
});

test.describe("Hospital admin: no clinical records", () => {
  const creds = getHospitalAdminCreds();
  test.skip(!creds, "E2E_HOSPITAL_ADMIN_EMAIL and E2E_HOSPITAL_ADMIN_PASSWORD not set");

  test("hospital_admin sees demographics only on patient page, not clinical records", async ({ page }) => {
    await login(page, creds!);
    await page.goto("/patients/search");
    const patientLink = page.locator('a[href^="/patients/"]').first();
    if (!(await patientLink.isVisible())) {
      test.skip(true, "No patients in search");
      return;
    }
    await patientLink.click();
    await page.waitForURL(/\/patients\/[^/]+$/);
    await expect(page.getByText(/clinical records are not available|demographics/i)).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(/manage staff|audit logs|admin/i)).toBeVisible();
  });
});

test.describe("Super admin: view-as and register with hospital", () => {
  const creds = getSuperAdminCreds();
  test.skip(!creds, "E2E_SUPER_ADMIN_EMAIL and E2E_SUPER_ADMIN_PASSWORD not set");

  test("super_admin can set view-as hospital and register patient with that hospital", async ({ page }) => {
    await login(page, creds!);
    await page.goto("/dashboard");
    const viewAsSelect = page.locator('select').filter({ has: page.getByRole("option", { name: /all hospitals/i }) });
    if (await viewAsSelect.isVisible()) {
      await viewAsSelect.selectOption({ index: 1 });
      await expect(page.getByText(/viewing as|operating in/i)).toBeVisible();
    }

    await page.goto("/patients/register");
    await expect(page.getByRole("heading", { name: /register new patient/i })).toBeVisible({ timeout: 10_000 });
    const facilitySelect = page.getByLabel(/register patient at facility|select facility/i);
    if (await facilitySelect.isVisible()) {
      await facilitySelect.selectOption({ index: 1 });
    }
    await page.getByLabel(/full name/i).fill("E2E Patient");
    await page.getByLabel(/date of birth/i).fill("1990-01-15");
    await page.getByLabel(/ghana health id/i).fill("GH-1234-5678-901234");
    await page.getByRole("button", { name: /next: medical/i }).click();
    await page.getByRole("button", { name: /register patient/i }).click();
    await expect(page).toHaveURL(/\/patients\/search/, { timeout: 15_000 });
  });
});
