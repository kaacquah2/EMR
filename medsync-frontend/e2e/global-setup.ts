import type { FullConfig } from "@playwright/test";

/**
 * Optional: log in as each role and save storage state for faster tests.
 * If E2E_* credentials are not set, role-based tests will log in per test.
 */
async function globalSetup(config: FullConfig) {
  void config;
  // No-op for now; tests perform login when credentials are provided.
  await Promise.resolve();
}

export default globalSetup;
