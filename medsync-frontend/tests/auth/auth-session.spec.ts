import { test, expect } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import {
  getReceptionistCreds,
  getDoctorCreds,
  getNurseCreds,
  getLabTechCreds,
  getHospitalAdminCreds,
  getSuperAdminCreds,
} from "../../e2e/auth";
import { ROLES } from "../utils/roles";
import { LOGIN_SIGN_IN_TITLE } from "../utils/constants";

const CREDS = [
  getReceptionistCreds,
  getDoctorCreds,
  getNurseCreds,
  getLabTechCreds,
  getHospitalAdminCreds,
  getSuperAdminCreds,
];

test.describe("Auth and session", () => {
  test("valid login for each role when credentials are set", async ({ page }) => {
    const loginPage = new LoginPage(page);
    let anySkipped = true;
    for (let i = 0; i < ROLES.length; i++) {
      const creds = CREDS[i]();
      if (!creds) continue;
      anySkipped = false;
      await loginPage.login(creds.email, creds.password);
      await loginPage.completeMfaIfPresent();
      await loginPage.completeMfaIfPresent();
      await expect(page).toHaveURL(/\/(dashboard|superadmin|$)/);
      // More robust logout selector
      const logoutBtn = page.getByRole("button", { name: /log out|sign out/i }).or(page.locator('button:has(svg.lucide-log-out)'));
      await logoutBtn.first().click();
      await page.waitForURL(/\/login/, { timeout: 10_000 });
    }
    if (anySkipped) test.skip(true, "No E2E_*_EMAIL/PASSWORD set for any role");
  });

  test("invalid login shows error and stays on login", async ({ page }) => {
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.fillCredentials("wrong@example.com", "wrongpassword");
    await loginPage.submitCredentials();
    await loginPage.expectErrorVisible();
    await expect(page).toHaveURL(/\/login/);
  });

  test("logout clears session and redirects to login", async ({ page }) => {
    const creds = getDoctorCreds() ?? getReceptionistCreds();
    test.skip(!creds, "No E2E credentials set");
    const loginPage = new LoginPage(page);
    await loginPage.login(creds!.email, creds!.password);
    await loginPage.completeMfaIfPresent();
    await expect(page).toHaveURL(/\/(dashboard|superadmin|$)/);
    const logoutBtn = page.getByRole("button", { name: /log out|sign out/i }).or(page.locator('button:has(svg.lucide-log-out)'));
    await logoutBtn.first().click();
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await loginPage.expectSignInTitleVisible();
  });

  test("protected route redirects anonymous user to login", async ({ page }) => {
    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: new RegExp(LOGIN_SIGN_IN_TITLE, "i") })).toBeVisible();
  });

  test("direct access to /admin/users redirects anonymous to login", async ({ page }) => {
    await page.goto("/admin/users");
    await page.waitForURL(/\/login/, { timeout: 10_000 });
  });

  test("token/session: after login, reload stays on dashboard", async ({ page }) => {
    const creds = getDoctorCreds() ?? getReceptionistCreds();
    test.skip(!creds, "No E2E credentials set");
    const loginPage = new LoginPage(page);
    await loginPage.login(creds!.email, creds!.password);
    await loginPage.completeMfaIfPresent();
    await expect(page).toHaveURL(/\/(dashboard|superadmin|$)/);
    await page.reload();
    await page.waitForLoadState("networkidle");
    await expect(page).toHaveURL(/\/(dashboard|superadmin|$)/);
    // Use a more generic dashboard indicator
    await expect(page.getByText(/dashboard|good (morning|afternoon|evening)|worklist|medsync/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("MFA flow: if backup code provided and MFA step appears, verify succeeds", async ({ page }) => {
    const creds = getDoctorCreds();
    test.skip(!creds || !process.env.E2E_MFA_BACKUP_CODE, "E2E_DOCTOR_* and E2E_MFA_BACKUP_CODE required");
    const loginPage = new LoginPage(page);
    await loginPage.goto();
    await loginPage.fillCredentials(creds!.email, creds!.password);
    await loginPage.submitCredentials();
    await loginPage.completeMfaIfPresent(process.env.E2E_MFA_BACKUP_CODE);
    await expect(page).toHaveURL(/\/(dashboard|superadmin|$)/, { timeout: 15_000 });
  });
});
