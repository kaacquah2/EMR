import { describe, it, expect } from "vitest";
import { validatePassword } from "../password-policy";

describe("validatePassword", () => {
  it("rejects password shorter than 12 characters", () => {
    expect(validatePassword("Short1!").valid).toBe(false);
    expect(validatePassword("Short1!").message).toContain("12");
  });

  it("rejects password without uppercase", () => {
    expect(validatePassword("alllowercase12!").valid).toBe(false);
    expect(validatePassword("alllowercase12!").message?.toLowerCase()).toContain("uppercase");
  });

  it("rejects password without lowercase", () => {
    expect(validatePassword("ALLUPPERCASE12!").valid).toBe(false);
    expect(validatePassword("ALLUPPERCASE12!").message?.toLowerCase()).toContain("lowercase");
  });

  it("rejects password without digit", () => {
    expect(validatePassword("NoDigitsHere!").valid).toBe(false);
    expect(validatePassword("NoDigitsHere!").message?.toLowerCase()).toContain("number");
  });

  it("rejects password without symbol", () => {
    expect(validatePassword("NoSymbolHere12").valid).toBe(false);
    expect(validatePassword("NoSymbolHere12").message?.toLowerCase()).toContain("symbol");
  });

  it("accepts valid password", () => {
    expect(validatePassword("ValidPass12!").valid).toBe(true);
    expect(validatePassword("ValidPass12!").message).toBeUndefined();
  });
});
