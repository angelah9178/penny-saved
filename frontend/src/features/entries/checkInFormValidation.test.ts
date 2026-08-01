import { describe, expect, it } from "vitest";

import {
  checkInFormSchema,
  MAX_CHECK_IN_COMMENT_LENGTH,
} from "./checkInFormValidation";

describe("checkInFormSchema", () => {
  it.each(["saved", "purchased"])("accepts the %s result", (result) => {
    expect(
      checkInFormSchema.parse({ result, comment: " Reflection " }),
    ).toEqual({ result, comment: "Reflection" });
  });

  it.each(["", "   "])("normalizes the blank comment %j to null", (comment) => {
    expect(checkInFormSchema.parse({ result: "saved", comment })).toEqual({
      result: "saved",
      comment: null,
    });
  });

  it("requires an explicit result", () => {
    expect(
      checkInFormSchema.safeParse({ result: "", comment: "" }).success,
    ).toBe(false);
  });

  it("accepts the comment boundary and counts Unicode characters", () => {
    expect(
      checkInFormSchema.safeParse({
        result: "purchased",
        comment: "☕".repeat(MAX_CHECK_IN_COMMENT_LENGTH),
      }).success,
    ).toBe(true);
    expect(
      checkInFormSchema.safeParse({
        result: "purchased",
        comment: "☕".repeat(MAX_CHECK_IN_COMMENT_LENGTH + 1),
      }).success,
    ).toBe(false);
  });
});
