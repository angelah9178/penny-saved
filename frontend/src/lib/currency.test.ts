import { describe, expect, it } from "vitest";

import { formatUsd } from "./currency";

describe("formatUsd", () => {
  it.each([
    [0, "$0.00"],
    [1, "$0.01"],
    [1_299, "$12.99"],
    [10_000, "$100.00"],
    [999_999_999_999, "$9,999,999,999.99"],
  ])("formats %i integer cents as %s", (priceCents, expected) => {
    expect(formatUsd(priceCents)).toBe(expected);
  });
});
