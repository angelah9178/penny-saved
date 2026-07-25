import { describe, expect, it } from "vitest";

import { safeReturnPath } from "./returnPath";

describe("safeReturnPath", () => {
  it.each([
    "/dashboard",
    "/entries/new",
    "/entries/entry-1?tab=details#comment",
  ])("accepts the internal path %s", (path) => {
    expect(safeReturnPath(path)).toBe(path);
  });

  it.each([
    undefined,
    null,
    "",
    "dashboard",
    "https://attacker.example",
    "//attacker.example/path",
    "/\\attacker.example",
    "javascript:alert(1)",
    "/%2F%2Fattacker.example",
    "/%252F%252Fattacker.example",
    "/login",
    "/login/",
    "/signup",
    "/signup/",
    "/%6cogin",
    "/bad%ZZpath",
    "/dashboard\u0000",
  ])("falls back safely for %s", (path) => {
    expect(safeReturnPath(path)).toBe("/dashboard");
  });
});
