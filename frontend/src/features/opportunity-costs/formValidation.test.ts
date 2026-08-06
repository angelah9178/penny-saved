import { describe, expect, it } from "vitest";

import {
  formatCentsForOpportunityCostForm,
  opportunityCostFormSchema,
} from "./formValidation";

describe("opportunity-cost form validation", () => {
  it("trims text and converts exact dollar input into an API-ready value", () => {
    expect(
      opportunityCostFormSchema.parse({
        label: "  Hours worked  ",
        unit_name: "  hours  ",
        dollar_value: " 10.00 ",
      }),
    ).toEqual({
      label: "Hours worked",
      unit_name: "hours",
      dollar_value: 1_000,
    });
  });

  it.each([
    ["0.01", 1],
    ["0.5", 50],
    ["12", 1_200],
    ["9999999999.99", 999_999_999_999],
  ])("accepts the supported dollar boundary %s", (value, cents) => {
    const result = opportunityCostFormSchema.parse({
      label: "Coffee",
      unit_name: "cups",
      dollar_value: value,
    });
    expect(result.dollar_value).toBe(cents);
  });

  it.each([
    "",
    "0",
    "0.00",
    ".50",
    "12.",
    "01.00",
    "1.999",
    "1e3",
    "+1.00",
    "-1.00",
    "$1.00",
    "1,000.00",
    "10000000000.00",
  ])("rejects unsupported dollar input %j", (dollar_value) => {
    expect(
      opportunityCostFormSchema.safeParse({
        label: "Coffee",
        unit_name: "cups",
        dollar_value,
      }).success,
    ).toBe(false);
  });

  it("rejects trimmed blanks and text beyond the backend limits", () => {
    expect(
      opportunityCostFormSchema.safeParse({
        label: "   ",
        unit_name: "   ",
        dollar_value: "1.00",
      }).success,
    ).toBe(false);
    expect(
      opportunityCostFormSchema.safeParse({
        label: "a".repeat(121),
        unit_name: "b".repeat(81),
        dollar_value: "1.00",
      }).success,
    ).toBe(false);
  });

  it("counts Unicode characters rather than UTF-16 code units", () => {
    expect(
      opportunityCostFormSchema.safeParse({
        label: "☕".repeat(120),
        unit_name: "⏱".repeat(80),
        dollar_value: "1.00",
      }).success,
    ).toBe(true);
  });

  it.each([
    [1, "0.01"],
    [50, "0.50"],
    [1_000, "10.00"],
    [999_999_999_999, "9999999999.99"],
  ])("formats %d cents for editing", (cents, dollars) => {
    expect(formatCentsForOpportunityCostForm(cents)).toBe(dollars);
  });
});
