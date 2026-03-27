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

describe("AI insights route access", () => {
  const route = "/patients/123e4567-e89b-12d3-a456-426614174000/ai-insights";

  it("allows doctor role", () => {
    expect(isPathnameAccessible("doctor", route)).toBe(true);
  });

  it("blocks nurse role", () => {
    expect(isPathnameAccessible("nurse", route)).toBe(false);
  });

  it("blocks receptionist role", () => {
    expect(isPathnameAccessible("receptionist", route)).toBe(false);
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
