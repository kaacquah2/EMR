import { test, expect } from "../fixtures/auth";

test.describe("Hospital admin workflow", () => {
  test("hospital_admin can view user management", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("hospital_admin"), "E2E_HOSPITAL_ADMIN_* not set");
    await loginAs("hospital_admin");
    await page.goto("/admin/users");
    await expect(page).toHaveURL(/\/admin\/users/);
    await expect(page.getByRole("heading", { name: /user|staff|management/i }).or(page.getByText(/users|staff/i).first())).toBeVisible({ timeout: 10_000 });
  });

  test("hospital_admin can view audit logs", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("hospital_admin"), "E2E_HOSPITAL_ADMIN_* not set");
    await loginAs("hospital_admin");
    await page.goto("/admin/audit-logs");
    await expect(page).toHaveURL(/\/admin\/audit-logs/);
    await expect(page.getByRole("heading", { name: /audit|logs/i }).or(page.getByText(/audit|logs/i).first())).toBeVisible({ timeout: 10_000 });
  });

  test("hospital_admin cannot use superadmin-only features (facilities)", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("hospital_admin"), "E2E_HOSPITAL_ADMIN_* not set");
    await loginAs("hospital_admin");
    await page.goto("/admin/facilities");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: /access denied/i })).toBeVisible();
  });
});
