import { Page } from "@playwright/test";

export interface E2ECredentials {
  email: string;
  password: string;
}

/**
 * Log in via the login page. Expects test users to have MFA disabled,
 * or set E2E_MFA_BACKUP_CODE for backup-code verification.
 */
export async function login(page: Page, creds: E2ECredentials): Promise<boolean> {
  await page.goto("/login");
  await page.getByLabel(/email/i).fill(creds.email);
  await page.getByLabel(/password/i).fill(creds.password);
  await page.getByRole("button", { name: /continue|sign in/i }).click();

  // If MFA step appears, try backup code if provided
  const mfaInput = page.getByPlaceholder(/backup|code/i).first();
  const mfaVisible = await mfaInput.isVisible().catch(() => false);
  if (mfaVisible) {
    const backup = process.env.E2E_MFA_BACKUP_CODE;
    if (backup) {
      await mfaInput.fill(backup);
      await page.getByRole("button", { name: /verify/i }).click();
    } else {
      // MFA required but no backup code – fail so CI/docs are clear
      throw new Error("Login requires MFA. Set E2E_MFA_BACKUP_CODE or use a test user with MFA disabled.");
    }
  }

  await page.waitForURL(/\/(dashboard|login)/, { timeout: 15_000 });
  return page.url().includes("/dashboard");
}

export function getReceptionistCreds(): E2ECredentials | null {
  const email = process.env.E2E_RECEPTIONIST_EMAIL;
  const password = process.env.E2E_RECEPTIONIST_PASSWORD;
  if (!email || !password) return null;
  return { email, password };
}

export function getDoctorCreds(): E2ECredentials | null {
  const email = process.env.E2E_DOCTOR_EMAIL;
  const password = process.env.E2E_DOCTOR_PASSWORD;
  if (!email || !password) return null;
  return { email, password };
}

export function getLabTechCreds(): E2ECredentials | null {
  const email = process.env.E2E_LAB_TECH_EMAIL;
  const password = process.env.E2E_LAB_TECH_PASSWORD;
  if (!email || !password) return null;
  return { email, password };
}

export function getNurseCreds(): E2ECredentials | null {
  const email = process.env.E2E_NURSE_EMAIL;
  const password = process.env.E2E_NURSE_PASSWORD;
  if (!email || !password) return null;
  return { email, password };
}

export function getHospitalAdminCreds(): E2ECredentials | null {
  const email = process.env.E2E_HOSPITAL_ADMIN_EMAIL;
  const password = process.env.E2E_HOSPITAL_ADMIN_PASSWORD;
  if (!email || !password) return null;
  return { email, password };
}

export function getSuperAdminCreds(): E2ECredentials | null {
  const email = process.env.E2E_SUPER_ADMIN_EMAIL;
  const password = process.env.E2E_SUPER_ADMIN_PASSWORD;
  if (!email || !password) return null;
  return { email, password };
}
