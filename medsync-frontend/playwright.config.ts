import { defineConfig } from "@playwright/test";

/**
 * MedSync E2E: role-based, workflow-driven tests.
 * Requires backend + frontend running. Set E2E_* env for credentials.
 */
export default defineConfig({
  testDir: ".",
  testMatch: ["tests/**/*.spec.ts", "e2e/**/*.spec.ts"],
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 4 : undefined,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : [["html", { open: "on-failure" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: process.env.E2E_BASE_URL
    ? undefined
    : {
        command: "npm run dev",
        url: "http://localhost:3000",
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
  projects: [
    { name: "auth", testMatch: "**/auth/**/*.spec.ts" },
    { name: "roles", testMatch: "**/roles/**/*.spec.ts" },
    { name: "security", testMatch: "**/security/**/*.spec.ts" },
    { name: "workflows", testMatch: "**/workflows/**/*.spec.ts" },
    { name: "scoping", testMatch: "**/scoping/**/*.spec.ts" },
    { name: "ux", testMatch: "**/ux/**/*.spec.ts" },
    { name: "network", testMatch: "**/network/**/*.spec.ts" },
    { name: "all", testMatch: "**/*.spec.ts" },
  ],
  timeout: 30_000,
  expect: { timeout: 10_000 },
});
