import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { StatsRange, StatsSummary } from "../../types/api";
import { getStatsSummary } from "./api";

const fetchMock = vi.fn<typeof fetch>();
const ranges: StatsRange[] = [
  "this_month",
  "last_3_months",
  "last_6_months",
  "last_year",
  "all_time",
];
const summary: StatsSummary = {
  range: "this_month",
  total_saved_cents: 25_000,
  avoided_purchase_count: 4,
  purchased_count: 1,
  opportunity_costs: [
    {
      example_id: "63000000-0000-4000-8000-000000000001",
      label: "hours worked",
      unit_name: "hours",
      dollar_value_cents: 1_000,
      equivalent_units: 25,
    },
  ],
};

describe("statistics API", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it.each(ranges)(
    "gets the %s summary through the credentialed API client",
    async (range) => {
      const response = { ...summary, range };
      fetchMock.mockResolvedValue(Response.json(response));

      await expect(getStatsSummary(range)).resolves.toEqual(response);

      const [url, init] = firstFetchCall();
      expect(url).toBe(`/api/stats/summary?range=${range}`);
      expect(init).toMatchObject({ credentials: "include" });
      expect(init?.method).toBeUndefined();
      if (typeof url !== "string") {
        throw new Error("Expected the statistics request URL to be a string.");
      }
      expect(new URL(url, "http://test").searchParams.getAll("range")).toEqual([
        range,
      ]);
    },
  );

  it("forwards TanStack Query cancellation to the request", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(Response.json(summary));

    await getStatsSummary("this_month", controller.signal);

    expect(firstFetchCall()[1]).toMatchObject({ signal: controller.signal });
  });
});

function firstFetchCall(): Parameters<typeof fetch> {
  const call = fetchMock.mock.calls[0];

  if (call === undefined) {
    throw new Error("Expected fetch to have been called.");
  }

  return call;
}
