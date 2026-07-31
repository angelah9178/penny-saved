import { describe, expect, it } from "vitest";

import {
  entryFormSchema,
  formatCentsForEntryForm,
  parseDollarsToCents,
} from "./entryFormValidation";

describe("entry price conversion", () => {
  it.each([
    ["0.01", 1],
    ["0.5", 50],
    ["12", 1_200],
    ["89.99", 8_999],
    ["9999999999.99", 999_999_999_999],
    [" 19.95 ", 1_995],
  ])("parses %j into exact integer cents", (dollars, cents) => {
    expect(parseDollarsToCents(dollars)).toBe(cents);
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
  ])("rejects the invalid or unsupported price %j", (price) => {
    expect(() => parseDollarsToCents(price)).toThrow();
  });

  it.each([
    [1, "0.01"],
    [50, "0.50"],
    [1_200, "12.00"],
    [8_999, "89.99"],
    [999_999_999_999, "9999999999.99"],
  ])("formats %d cents for an edit field", (cents, dollars) => {
    expect(formatCentsForEntryForm(cents)).toBe(dollars);
  });

  it.each([-1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])(
    "rejects invalid cents %s",
    (cents) => {
      expect(() => formatCentsForEntryForm(cents)).toThrow();
    },
  );
});

describe("entryFormSchema", () => {
  it("trims text and returns cents ready for the API", () => {
    expect(
      entryFormSchema.parse({
        item_name: "  Coffee grinder  ",
        price: "89.99",
        reason_wanted: "  Better coffee at home  ",
      }),
    ).toEqual({
      item_name: "Coffee grinder",
      price: 8_999,
      reason_wanted: "Better coffee at home",
    });
  });

  it("rejects blank text and text beyond backend limits", () => {
    expect(
      entryFormSchema.safeParse({
        item_name: "   ",
        price: "1.00",
        reason_wanted: "   ",
      }).success,
    ).toBe(false);
    expect(
      entryFormSchema.safeParse({
        item_name: "a".repeat(201),
        price: "1.00",
        reason_wanted: "a".repeat(2_001),
      }).success,
    ).toBe(false);
  });

  it("counts Unicode characters rather than UTF-16 code units", () => {
    expect(
      entryFormSchema.safeParse({
        item_name: "☕".repeat(200),
        price: "1.00",
        reason_wanted: "Valid reason",
      }).success,
    ).toBe(true);
  });
});
