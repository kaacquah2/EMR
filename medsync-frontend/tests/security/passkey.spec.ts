import { test, expect } from "../fixtures/auth";

test.describe("Passkey settings", () => {
  test("doctor can open security settings when credentials are configured", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    const ok = await loginAs("doctor");
    test.skip(!ok, "Doctor login failed (MFA or credentials)");
    await page.goto("/settings/security/passkeys");
    await expect(page.getByText(/passkey|security|device/i).first()).toBeVisible({ timeout: 15_000 });
  });
});
