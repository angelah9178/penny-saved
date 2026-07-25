import { describe, expect, it } from "vitest";

import { authFormSchema } from "./validation";

describe("authFormSchema", () => {
  it("trims email without changing the password", () => {
    expect(
      authFormSchema.parse({
        email: "  Person@Example.COM  ",
        password: "  password  ",
      }),
    ).toEqual({
      email: "Person@Example.COM",
      password: "  password  ",
    });
  });

  it.each([
    "",
    "invalid-email",
    "@example.com",
    "person@",
    "person@@example.com",
    "person @example.com",
  ])("rejects the invalid email %j", (email) => {
    expect(
      authFormSchema.safeParse({ email, password: "password123" }).success,
    ).toBe(false);
  });

  it("counts Unicode password characters without truncating them", () => {
    expect(
      authFormSchema.safeParse({
        email: "person@example.com",
        password: "🔒".repeat(8),
      }).success,
    ).toBe(true);
    expect(
      authFormSchema.safeParse({
        email: "person@example.com",
        password: "🔒".repeat(7),
      }).success,
    ).toBe(false);
  });
});
