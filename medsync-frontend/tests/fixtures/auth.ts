/* eslint-disable react-hooks/rules-of-hooks -- Playwright fixture "use" is not React's use() hook */
import { test as base } from "@playwright/test";
import type { E2ECredentials } from "../../e2e/auth";
import {
  login,
  getReceptionistCreds,
  getDoctorCreds,
  getNurseCreds,
  getLabTechCreds,
  getHospitalAdminCreds,
  getSuperAdminCreds,
} from "../../e2e/auth";
import type { Role } from "../utils/roles";

const CREDS_GETTERS: Record<Role, () => E2ECredentials | null> = {
  receptionist: getReceptionistCreds,
  doctor: getDoctorCreds,
  nurse: getNurseCreds,
  lab_technician: getLabTechCreds,
  hospital_admin: getHospitalAdminCreds,
  super_admin: getSuperAdminCreds,
};

export interface AuthFixtures {
  /** Log in as the given role. Skips test if credentials not set. Returns true if login succeeded. */
  loginAs: (role: Role) => Promise<boolean>;
  /** Get credentials for role; null if not set. */
  getCreds: (role: Role) => E2ECredentials | null;
}

export const test = base.extend<AuthFixtures>({
  getCreds: async ({}, use) => {
    await use((role: Role) => CREDS_GETTERS[role]() ?? null);
  },
  loginAs: async ({ page, getCreds }, use) => {
    await use(async (role: Role) => {
      const creds = getCreds(role);
      if (!creds) return false;
      return login(page, creds);
    });
  },
});

export { expect } from "@playwright/test";
