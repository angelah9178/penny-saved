import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { server } from "../../test/server";
import type { DashboardEntries } from "../../types/api";
import {
  resetSessionExpiry,
  subscribeToSessionExpiry,
} from "../auth/sessionExpiry";
import { dashboardEntriesQueryOptions } from "./queries";

const dashboardEntries: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};

describe("dashboardEntriesQueryOptions", () => {
  afterEach(() => {
    resetSessionExpiry();
  });

  it("uses the shared dashboard key and a 30-second freshness window", () => {
    const options = dashboardEntriesQueryOptions();

    expect(options.queryKey).toEqual(queryKeys.entries.dashboard());
    expect(options.staleTime).toBe(30 * 1_000);
  });

  it("loads the dashboard response through GET /api/entries", async () => {
    server.use(
      http.get("/api/entries", () => HttpResponse.json(dashboardEntries)),
    );
    const queryClient = new QueryClient();

    await expect(
      queryClient.fetchQuery(dashboardEntriesQueryOptions()),
    ).resolves.toEqual(dashboardEntries);
    expect(queryClient.getQueryData(queryKeys.entries.dashboard())).toEqual(
      dashboardEntries,
    );
  });

  it("reports an expired session with the dashboard return path", async () => {
    server.use(
      http.get("/api/entries", () =>
        HttpResponse.json(
          {
            error: {
              code: "unauthorized",
              message: "Authentication is required.",
            },
          },
          { status: 401 },
        ),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeToSessionExpiry(listener);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    await expect(
      queryClient.fetchQuery(dashboardEntriesQueryOptions()),
    ).rejects.toMatchObject({ status: 401, code: "unauthorized" });
    expect(listener).toHaveBeenCalledOnce();
    expect(listener).toHaveBeenCalledWith({ returnTo: "/dashboard" });

    unsubscribe();
  });

  it("uses the shared retry policy", () => {
    const retry = dashboardEntriesQueryOptions().retry;
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
