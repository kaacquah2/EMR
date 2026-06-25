import { describe, expect, it } from "vitest";

import { canResolveAlerts } from "../permissions";
import { isPathnameAccessible } from "../navigation";

describe("alerts resolve permissions", () => {
  it("allows doctor and nurse", () => {
    expect(canResolveAlerts("doctor")).toBe(true);
    expect(canResolveAlerts("nurse")).toBe(true);
  });

  it("blocks non-resolve roles", () => {
    expect(canResolveAlerts("hospital_admin")).toBe(false);
    expect(canResolveAlerts("super_admin")).toBe(false);
    expect(canResolveAlerts("receptionist")).toBe(false);
  });
});

describe("doctor route scope", () => {
  it("blocks doctor from patient registration route", () => {
    expect(isPathnameAccessible("doctor", "/patients/register")).toBe(false);
  });

  it("blocks doctor from admissions route", () => {
    expect(isPathnameAccessible("doctor", "/admissions")).toBe(false);
  });

  it("blocks doctor from patient admissions sub-route", () => {
    expect(
      isPathnameAccessible("doctor", "/patients/123e4567-e89b-12d3-a456-426614174000/admissions")
    ).toBe(false);
  });

  it("allows doctor to appointments route", () => {
    expect(isPathnameAccessible("doctor", "/appointments")).toBe(true);
  });

  it("allows doctor to referrals route", () => {
    expect(isPathnameAccessible("doctor", "/referrals")).toBe(true);
  });
});

describe("nurse route scope", () => {
  it("allows nurse worklist and admissions", () => {
    expect(isPathnameAccessible("nurse", "/worklist")).toBe(true);
    expect(isPathnameAccessible("nurse", "/admissions")).toBe(true);
  });

  it("allows nurse patient chart and vitals new route", () => {
    expect(isPathnameAccessible("nurse", "/patients/123e4567-e89b-12d3-a456-426614174000")).toBe(true);
    expect(isPathnameAccessible("nurse", "/patients/123e4567-e89b-12d3-a456-426614174000/vitals/new")).toBe(true);
  });

  it("blocks nurse from register and referrals", () => {
    expect(isPathnameAccessible("nurse", "/patients/register")).toBe(false);
    expect(isPathnameAccessible("nurse", "/referrals")).toBe(false);
  });
});

describe("lab technician route scope", () => {
  it("allows lab orders list and detail route", () => {
    expect(isPathnameAccessible("lab_technician", "/lab/orders")).toBe(true);
    expect(isPathnameAccessible("lab_technician", "/lab/orders/123e4567-e89b-12d3-a456-426614174000")).toBe(true);
  });

  it("blocks lab technician from patient and appointment routes", () => {
    expect(isPathnameAccessible("lab_technician", "/patients/search")).toBe(false);
    expect(isPathnameAccessible("lab_technician", "/appointments")).toBe(false);
  });
});

describe("receptionist route scope", () => {
  it("allows receptionist core routes", () => {
    expect(isPathnameAccessible("receptionist", "/patients/search")).toBe(true);
    expect(isPathnameAccessible("receptionist", "/appointments")).toBe(true);
  });

  it("blocks receptionist from patient chart and referrals", () => {
    expect(isPathnameAccessible("receptionist", "/patients/123e4567-e89b-12d3-a456-426614174000")).toBe(false);
    expect(isPathnameAccessible("receptionist", "/referrals")).toBe(false);
  });
});

describe("newly wired routes", () => {
  it("allows lab_technician to access lab results page", () => {
    expect(isPathnameAccessible("lab_technician", "/lab/results")).toBe(true);
  });

  it("blocks lab_technician from admin batch operations", () => {
    expect(isPathnameAccessible("lab_technician", "/admin/batch-operations")).toBe(false);
  });

  it("allows hospital_admin on all three new admin pages", () => {
    expect(isPathnameAccessible("hospital_admin", "/admin/batch-operations")).toBe(true);
    expect(isPathnameAccessible("hospital_admin", "/admin/overtime-tracking")).toBe(true);
    expect(isPathnameAccessible("hospital_admin", "/admin/shift-management")).toBe(true);
  });

  it("allows super_admin on all three new admin pages", () => {
    expect(isPathnameAccessible("super_admin", "/admin/batch-operations")).toBe(true);
    expect(isPathnameAccessible("super_admin", "/admin/overtime-tracking")).toBe(true);
    expect(isPathnameAccessible("super_admin", "/admin/shift-management")).toBe(true);
  });

  it("blocks doctor from new admin pages", () => {
    expect(isPathnameAccessible("doctor", "/admin/batch-operations")).toBe(false);
    expect(isPathnameAccessible("doctor", "/admin/shift-management")).toBe(false);
  });

  it("allows all roles to access security settings page", () => {
    for (const role of ["doctor", "nurse", "lab_technician", "receptionist", "hospital_admin", "super_admin", "pharmacy_technician", "ward_clerk"]) {
      expect(isPathnameAccessible(role, "/settings/security/passkeys")).toBe(true);
    }
  });
});
