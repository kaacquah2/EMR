import type { Page } from "@playwright/test";

/**
 * Page object for auth/login. Uses getByLabel/getByRole for resilience.
 */
export class LoginPage {
  constructor(private readonly page: Page) {}

  async goto() {
    await this.page.goto("/login");
  }

  async fillCredentials(email: string, password: string) {
    await this.page.getByLabel(/email/i).fill(email);
    await this.page.getByLabel(/password/i).fill(password);
  }

  async submitCredentials() {
    await this.page.getByRole("button", { name: /continue|sign in/i }).click();
  }

  /** Submit credentials and wait for either dashboard or login (error). */
  async login(email: string, password: string): Promise<boolean> {
    await this.goto();
    await this.fillCredentials(email, password);
    await this.submitCredentials();
    await this.page.waitForURL(/\/(dashboard|login)/, { timeout: 15_000 });
    return this.page.url().includes("/dashboard");
  }

  /** If MFA step is visible, fill backup code and verify. */
  async completeMfaIfPresent(backupCode?: string): Promise<void> {
    const code = backupCode ?? process.env.E2E_MFA_BACKUP_CODE;
    const mfaInput = this.page.getByPlaceholder(/backup|code/i).first();
    if (await mfaInput.isVisible().catch(() => false) && code) {
      await mfaInput.fill(code);
      await this.page.getByRole("button", { name: /verify/i }).click();
      await this.page.waitForURL(/\/(dashboard|login)/, { timeout: 15_000 });
    }
  }

  async expectSignInTitleVisible() {
    await this.page.getByRole("heading", { name: /sign in to medsync/i }).waitFor({ state: "visible", timeout: 5_000 });
  }

  async expectErrorVisible() {
    await this.page.getByText(/invalid credentials|login failed|invalid code/i).waitFor({ state: "visible", timeout: 5_000 });
  }
}
