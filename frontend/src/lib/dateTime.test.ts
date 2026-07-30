import { describe, expect, it } from "vitest";

import { formatDateTime } from "./dateTime";

describe("formatDateTime", () => {
  it("formats a UTC API timestamp as a readable local date and time", () => {
    const formatted = formatDateTime("2026-07-30T14:30:00Z");

    expect(formatted).not.toBeNull();
    expect(formatted).toContain("2026");
    expect(formatted).not.toContain("T14:30:00Z");
  });

  it("returns a safe result for an invalid timestamp", () => {
    expect(formatDateTime("not-a-date")).toBeNull();
  });
});
