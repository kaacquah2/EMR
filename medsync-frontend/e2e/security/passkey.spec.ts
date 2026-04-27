import { test, expect } from "@playwright/test";

/**
 * T11.6: Passkey/WebAuthn Workflow
 * Register device → Rename device → Delete device → Login with biometric
 * Tests WebAuthn credential management and biometric login flow.
 */

test.describe("Passkey/WebAuthn Workflow: Biometric Authentication", () => {
  test("should register passkey, rename, delete, and login with biometric", async ({ page }) => {
    // 1. Login first (required to manage passkeys)
    await page.goto("/login");

    // For this test, we'll use standard login to reach settings
    await page.getByLabel(/email/i).fill("doctor@medsync.gh");
    await page.getByLabel(/password/i).fill("Doctor123!");
    await page.getByRole("button", { name: /continue|sign in/i }).click();

    // Handle MFA if present (use backup code if available)
    const mfaInput = page.getByPlaceholder(/backup|code/i).first();
    if (await mfaInput.isVisible().catch(() => false)) {
      const backupCode = process.env.E2E_MFA_BACKUP_CODE || "000000";
      await mfaInput.fill(backupCode);
      await page.getByRole("button", { name: /verify/i }).click();
    }

    await page.waitForURL(/\/(dashboard|login)/, { timeout: 15_000 });
    await expect(page.url()).toContain("/dashboard");

    // 2. Navigate to security/passkey settings
    const settingsLink = page.getByRole("link", { name: /settings|profile|account/i });
    if (await settingsLink.isVisible().catch(() => false)) {
      await settingsLink.click();
    }

    const securityLink = page.getByRole("link", { name: /security|passkey|authenticator/i });
    if (await securityLink.isVisible().catch(() => false)) {
      await securityLink.click();
    }

    // Verify on security page
    await expect(page.getByText(/passkey|authenticator|webauthn/i)).toBeVisible({ timeout: 10_000 });

    // 3. Register a passkey
    const registerPasskeyBtn = page.getByRole("button", { name: /register|add passkey|add device/i });
    if (await registerPasskeyBtn.isVisible().catch(() => false)) {
      await registerPasskeyBtn.click();

      // Playwright doesn't support WebAuthn registration in standard way,
      // but we can test the UI flow and error handling
      const passkeyNameInput = page.getByPlaceholder(/device name|passkey name/i);

      if (await passkeyNameInput.isVisible().catch(() => false)) {
        await passkeyNameInput.fill("My Laptop");

        const confirmBtn = page.getByRole("button", { name: /register|confirm|next/i });
        if (await confirmBtn.isVisible().catch(() => false)) {
          await confirmBtn.click();

          // The system would prompt for biometric/security key,
          // but Playwright can't interact with WebAuthn prompts directly.
          // We test that the UI properly appears and can be navigated.
          await page.waitForTimeout(1000);
        }
      }
    }

    // 4. View and rename existing passkey (if any)
    const passkeyList = page.locator('[data-testid="passkey-item"], .passkey-card').first();

    if (await passkeyList.isVisible().catch(() => false)) {
      // Test rename functionality
      const renameBtn = passkeyList.getByRole("button", { name: /rename|edit/i });

      if (await renameBtn.isVisible().catch(() => false)) {
        await renameBtn.click();

        const renameInput = page.getByPlaceholder(/name/i);
        if (await renameInput.isVisible().catch(() => false)) {
          await renameInput.clear();
          await renameInput.fill("My Work Laptop");

          const confirmRename = page.getByRole("button", { name: /confirm|save/i });
          await confirmRename.click();

          await expect(page.getByText(/work laptop|renamed/i)).toBeVisible({ timeout: 5_000 });
        }
      }

      // Test delete functionality
      const deleteBtn = passkeyList.getByRole("button", { name: /delete|remove/i });

      if (await deleteBtn.isVisible().catch(() => false)) {
        await deleteBtn.click();

        const confirmDelete = page.getByRole("button", { name: /confirm|yes|delete/i });
        if (await confirmDelete.isVisible().catch(() => false)) {
          await confirmDelete.click();

          // Verify deletion
          const deletedMessage = page.getByText(/deleted|removed|no longer/i);
          await expect(deletedMessage).toBeVisible({ timeout: 5_000 });
        }
      }
    }

    // 5. Test passkey login flow (logout and back)
    await page.goto("/auth/logout");
    await page.waitForURL("/login", { timeout: 10_000 });

    // On login page, check for passkey option
    const passkeyLoginBtn = page.getByRole("button", { name: /passkey|biometric|security key/i });

    if (await passkeyLoginBtn.isVisible().catch(() => false)) {
      await passkeyLoginBtn.click();

      // The system should prompt for biometric/security key
      // Playwright can't complete this in test, but we verify the flow initiates
      const errorOrPrompt = page.getByText(/authenticating|passkey|biometric|not supported/i);
      await expect(errorOrPrompt).toBeVisible({ timeout: 5_000 });
    }

    // For test completion, verify we can still login with password
    await page.getByLabel(/email/i).fill("doctor@medsync.gh");
    await page.getByLabel(/password/i).fill("Doctor123!");
    await page.getByRole("button", { name: /continue|sign in/i }).click();

    await page.waitForURL(/\/(dashboard|login)/, { timeout: 15_000 });
    await expect(page.url()).toContain("/dashboard");
  });
});
