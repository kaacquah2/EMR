import { test, expect } from "../fixtures/auth";

test.describe("Cross-facility workflow", () => {
  test("doctor can open referrals hub", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/referrals");
    await expect(page.getByText(/referral|incoming|network/i).first()).toBeVisible({ timeout: 15_000 });
  });

  test("super admin can open interop network view", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("super_admin"), "E2E_SUPER_ADMIN_* not set");
    await loginAs("super_admin");
    await page.goto("/superadmin/network");
    await expect(page.getByText(/network|hospital|facility/i).first()).toBeVisible({ timeout: 15_000 });
  });
});
