import { describe, expect, it } from "vitest";

import type { StatsRange } from "../types/api";
import { queryKeys } from "./queryKeys";

describe("queryKeys", () => {
  it("creates the current-user key", () => {
    expect(queryKeys.auth.me()).toEqual(["auth", "me"]);
  });

  it("creates the dashboard key", () => {
    expect(queryKeys.entries.dashboard()).toEqual(["entries", "dashboard"]);
  });

  it("includes the entry identifier in a detail key", () => {
    expect(queryKeys.entries.detail("entry-123")).toEqual([
      "entries",
      "detail",
      "entry-123",
    ]);
  });

  it.each<StatsRange>([
    "this_month",
    "last_3_months",
    "last_6_months",
    "last_year",
    "all_time",
  ])("includes the %s range in a statistics key", (range) => {
    expect(queryKeys.stats.all()).toEqual(["stats"]);
    expect(queryKeys.stats.summary(range)).toEqual(["stats", "summary", range]);
  });

  it("creates the opportunity-cost list key", () => {
    expect(queryKeys.opportunityCosts.list()).toEqual([
      "opportunity-costs",
      "list",
    ]);
  });

  it("returns new keys so consumers cannot share mutable array state", () => {
    expect(queryKeys.auth.me()).not.toBe(queryKeys.auth.me());
    expect(queryKeys.entries.dashboard()).not.toBe(
      queryKeys.entries.dashboard(),
    );
  });
});
