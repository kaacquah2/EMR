import { test, expect } from "../fixtures/auth";

/**
 * Network/API-aware tests: verify correct endpoint, method, status on key UI actions.
 * Uses page.route or request/response observation where helpful.
 */

test.describe("Network and API", () => {
  test("login triggers POST /auth/login and returns 200 on success", async ({ page, getCreds }) => {
    const creds = getCreds("doctor") ?? getCreds("receptionist");
    test.skip(!creds, "E2E_DOCTOR or E2E_RECEPTIONIST credentials not set");
    let loginRequestUrl = "";
    let loginStatus = 0;
    page.on("request", (req) => {
      if (req.url().includes("/auth/login") && req.method() === "POST") loginRequestUrl = req.url();
    });
    page.on("response", (res) => {
      if (res.url().includes("/auth/login") && res.request().method() === "POST") loginStatus = res.status();
    });
    await page.goto("/login");
    await page.getByLabel(/email/i).fill(creds!.email);
    await page.getByLabel(/password/i).fill(creds!.password);
    await page.getByRole("button", { name: /continue|sign in/i }).click();
    await page.waitForURL(/\/(dashboard|login)/, { timeout: 15_000 });
    expect(loginRequestUrl).toContain("/auth/login");
    expect(loginStatus).toBe(200);
  });

  test("unauthorized route does not call admin API with valid token of wrong role", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("receptionist"), "E2E_RECEPTIONIST_* not set");
    let adminUsersCalled = false;
    page.on("response", (res) => {
      if (res.url().includes("/admin/users")) adminUsersCalled = true;
    });
    await loginAs("receptionist");
    await page.goto("/admin/users");
    await page.waitForURL(/\/unauthorized/, { timeout: 10_000 });
    expect(adminUsersCalled).toBe(false);
  });

  test("dashboard loads and requests metrics or analytics for allowed role", async ({ page, loginAs, getCreds }) => {
    test.skip(!getCreds("doctor"), "E2E_DOCTOR_* not set");
    let dashboardOrMetrics = false;
    page.on("response", (res) => {
      if (res.url().includes("/dashboard") || res.url().includes("/metrics")) dashboardOrMetrics = true;
    });
    await loginAs("doctor");
    await page.goto("/dashboard");
    await expect(page.getByText(/dashboard|good (morning|afternoon|evening)/i).first()).toBeVisible({ timeout: 12_000 });
    expect(dashboardOrMetrics).toBe(true);
  });
});
