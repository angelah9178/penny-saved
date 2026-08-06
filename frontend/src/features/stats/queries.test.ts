import { keepPreviousData, QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { server } from "../../test/server";
import type { StatsRange, StatsSummary } from "../../types/api";
import {
  resetSessionExpiry,
  subscribeToSessionExpiry,
} from "../auth/sessionExpiry";
import { statsSummaryQueryOptions } from "./queries";

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

describe("statsSummaryQueryOptions", () => {
  afterEach(() => {
    resetSessionExpiry();
  });

  it.each(ranges)(
    "uses a separate cache key and request for %s",
    async (range) => {
      let requestedRanges: string[] = [];
      server.use(
        http.get("/api/stats/summary", ({ request }) => {
          requestedRanges = new URL(request.url).searchParams.getAll("range");
          return HttpResponse.json({ ...summary, range });
        }),
      );
      const queryClient = testQueryClient();
      const options = statsSummaryQueryOptions(range);

      await expect(queryClient.fetchQuery(options)).resolves.toEqual({
        ...summary,
        range,
      });
      expect(options.queryKey).toEqual(queryKeys.stats.summary(range));
      expect(queryClient.getQueryData(queryKeys.stats.summary(range))).toEqual({
        ...summary,
        range,
      });
      expect(requestedRanges).toEqual([range]);
    },
  );

  it("keeps previous summary data available while a different range loads", () => {
    const options = statsSummaryQueryOptions("last_3_months");

    expect(options.placeholderData).toBe(keepPreviousData);
    expect(options.staleTime).toBe(30 * 1_000);
    expect(
      typeof options.placeholderData === "function"
        ? options.placeholderData(summary, undefined)
        : undefined,
    ).toBe(summary);
  });

  it("forwards query cancellation to GET /api/stats/summary", async () => {
    let requestSignal: AbortSignal | undefined;
    server.use(
      http.get("/api/stats/summary", ({ request }) => {
        requestSignal = request.signal;
        return HttpResponse.json(summary);
      }),
    );

    await testQueryClient().fetchQuery(statsSummaryQueryOptions("this_month"));

    expect(requestSignal).toBeInstanceOf(AbortSignal);
  });

  it("reports session expiry with the dashboard return path", async () => {
    server.use(
      http.get("/api/stats/summary", () =>
        HttpResponse.json(
          { error: { code: "unauthorized", message: "Sign in." } },
          { status: 401 },
        ),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeToSessionExpiry(listener);

    await expect(
      testQueryClient().fetchQuery(statsSummaryQueryOptions("this_month")),
    ).rejects.toMatchObject({ status: 401, code: "unauthorized" });
    expect(listener).toHaveBeenCalledWith({ returnTo: "/dashboard" });
    unsubscribe();
  });

  it("uses the shared retry policy", () => {
    const retry = statsSummaryQueryOptions("this_month").retry;
    const retryFn = typeof retry === "function" ? retry : undefined;

    expect(retryFn?.(0, new ApiError(0, "network_error", "Offline."))).toBe(
      true,
    );
    expect(retryFn?.(0, new ApiError(401, "unauthorized", "Sign in."))).toBe(
      false,
    );
    expect(retryFn?.(2, new ApiError(503, "unavailable", "Unavailable."))).toBe(
      false,
    );
  });
});

function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
}
