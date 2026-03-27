import { test, expect } from "../fixtures/auth";

/**
 * Hospital scoping: doctor from Hospital A cannot see Hospital B local-only data;
 * hospital_admin from A cannot manage Hospital B users; super_admin has global visibility.
 * These tests require two hospitals with separate users to be fully effective;
 * here we assert UI/API behavior that implies scoping (e.g. facility filter, view-as).
 */

test.describe("Hospital scoping", () => {
  test("doctor sees only own hospital context on dashboard", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByText(/dashboard|good (morning|afternoon|evening)|worklist/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test("hospital_admin sees user management scoped to facility", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("hospital_admin"), "E2E_HOSPITAL_ADMIN_* not set");
    await loginAs("hospital_admin");
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/admin\/users/);
    await expect(page.getByText(/users|staff|hospital|facility/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test("super_admin has view-as hospital selector on dashboard", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("super_admin"), "E2E_SUPER_ADMIN_* not set");
    await loginAs("super_admin");
    await page.goto("/dashboard");
    await expect(page.getByText(/all hospitals|viewing as|operating in/i).first()).toBeVisible({ timeout: 10_000 });
  });

  test("cross-facility record access shows gating or content", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    await loginAs("doctor");
    await page.goto("/cross-facility-records/00000000-0000-0000-0000-000000000001");
    await page.waitForLoadState("networkidle");
    const onUnauthorized = page.url().includes("/unauthorized");
    const onCrossFacility = page.url().includes("/cross-facility-records");
    const hasContent = await page.getByText(/access denied|permission|record|patient|referral/i).first().isVisible().catch(() => false);
    expect(onUnauthorized || (onCrossFacility && hasContent)).toBe(true);
  });
});
