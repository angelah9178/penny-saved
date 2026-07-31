import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { server } from "../../test/server";
import type {
  CreateEntryRequest,
  DashboardEntries,
  EntryResponse,
} from "../../types/api";
import {
  resetSessionExpiry,
  subscribeToSessionExpiry,
} from "../auth/sessionExpiry";
import {
  createEntryMutationOptions,
  dashboardEntriesQueryOptions,
  deleteEntryMutationOptions,
  entryDetailQueryOptions,
  updateEntryMutationOptions,
} from "./queries";

const dashboardEntries: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};
const entryId = "70000000-0000-4000-8000-000000000001";
const payload: CreateEntryRequest = {
  item_name: "Coffee grinder",
  price_cents: 8_999,
  reason_wanted: "Better coffee at home",
};
const entryResponse: EntryResponse = {
  entry: {
    id: entryId,
    ...payload,
    status: "waiting",
    dashboard_bucket: "waiting",
    comment: null,
    created_at: "2026-07-31T14:00:00Z",
    eligible_for_check_in_at: "2026-08-02T14:00:00Z",
    checked_in_at: null,
    updated_at: "2026-07-31T14:00:00Z",
  },
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

describe("entry management query and mutation options", () => {
  afterEach(() => {
    resetSessionExpiry();
  });

  it("loads entry detail with its shared key and cancellation signal", async () => {
    let requestSignal: AbortSignal | undefined;
    server.use(
      http.get(`/api/entries/${entryId}`, ({ request }) => {
        requestSignal = request.signal;
        return HttpResponse.json(entryResponse);
      }),
    );
    const queryClient = testQueryClient();
    const options = entryDetailQueryOptions(entryId);

    await expect(queryClient.fetchQuery(options)).resolves.toEqual(
      entryResponse,
    );
    expect(options.queryKey).toEqual(queryKeys.entries.detail(entryId));
    expect(options.staleTime).toBe(30 * 1_000);
    expect(requestSignal).toBeInstanceOf(AbortSignal);
  });

  it("reports detail session expiry with the entry return path", async () => {
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json(
          { error: { code: "unauthorized", message: "Sign in." } },
          { status: 401 },
        ),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeToSessionExpiry(listener);

    await expect(
      testQueryClient().fetchQuery(entryDetailQueryOptions(entryId)),
    ).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledWith({ returnTo: `/entries/${entryId}` });
    unsubscribe();
  });

  it("creates without retrying and invalidates the dashboard", async () => {
    server.use(
      http.post("/api/entries", async ({ request }) => {
        expect(await request.json()).toEqual(payload);
        return HttpResponse.json(entryResponse, { status: 201 });
      }),
    );
    const queryClient = testQueryClient();
    seedDashboard(queryClient);
    const options = createEntryMutationOptions(queryClient);

    await expect(
      queryClient
        .getMutationCache()
        .build(queryClient, options)
        .execute(payload),
    ).resolves.toEqual(entryResponse);
    expect(options.retry).toBe(false);
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
  });

  it("updates detail cache and invalidates detail and dashboard", async () => {
    const updatedResponse: EntryResponse = {
      entry: { ...entryResponse.entry, item_name: "Updated grinder" },
    };
    server.use(
      http.patch(`/api/entries/${entryId}`, () =>
        HttpResponse.json(updatedResponse),
      ),
    );
    const queryClient = testQueryClient();
    seedDashboard(queryClient);
    queryClient.setQueryData(queryKeys.entries.detail(entryId), entryResponse);

    const options = updateEntryMutationOptions(queryClient, entryId);
    await queryClient
      .getMutationCache()
      .build(queryClient, options)
      .execute(payload);

    expect(queryClient.getQueryData(queryKeys.entries.detail(entryId))).toEqual(
      updatedResponse,
    );
    expect(
      queryClient.getQueryState(queryKeys.entries.detail(entryId))
        ?.isInvalidated,
    ).toBe(true);
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
  });

  it("deletes without retrying, removes detail, and invalidates dashboard", async () => {
    server.use(
      http.delete(
        `/api/entries/${entryId}`,
        () => new HttpResponse(null, { status: 204 }),
      ),
    );
    const queryClient = testQueryClient();
    seedDashboard(queryClient);
    queryClient.setQueryData(queryKeys.entries.detail(entryId), entryResponse);
    const options = deleteEntryMutationOptions(queryClient, entryId);

    await queryClient.getMutationCache().build(queryClient, options).execute();

    expect(options.retry).toBe(false);
    expect(
      queryClient.getQueryState(queryKeys.entries.detail(entryId)),
    ).toBeUndefined();
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
  });

  it("reports create session expiry with the create-page return path", async () => {
    server.use(
      http.post("/api/entries", () =>
        HttpResponse.json(
          { error: { code: "unauthorized", message: "Sign in." } },
          { status: 401 },
        ),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeToSessionExpiry(listener);
    const queryClient = testQueryClient();
    const options = createEntryMutationOptions(queryClient);

    await expect(
      queryClient
        .getMutationCache()
        .build(queryClient, options)
        .execute(payload),
    ).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledWith({ returnTo: "/entries/new" });
    unsubscribe();
  });
});

function testQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
}

function seedDashboard(queryClient: QueryClient): void {
  queryClient.setQueryData(queryKeys.entries.dashboard(), dashboardEntries);
}
