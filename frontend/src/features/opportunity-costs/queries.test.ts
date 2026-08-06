import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { server } from "../../test/server";
import type {
  CreateOpportunityCostExampleRequest,
  OpportunityCostExampleResponse,
  OpportunityCostExamplesResponse,
} from "../../types/api";
import {
  resetSessionExpiry,
  subscribeToSessionExpiry,
} from "../auth/sessionExpiry";
import {
  createOpportunityCostExampleMutationOptions,
  deleteOpportunityCostExampleMutationOptions,
  opportunityCostExamplesQueryOptions,
  updateOpportunityCostExampleMutationOptions,
} from "./queries";

const exampleId = "63000000-0000-4000-8000-000000000001";
const payload: CreateOpportunityCostExampleRequest = {
  label: "Hours worked",
  unit_name: "hours",
  dollar_value_cents: 1_000,
};
const exampleResponse: OpportunityCostExampleResponse = {
  example: {
    id: exampleId,
    ...payload,
    created_at: "2026-08-06T12:00:00Z",
    updated_at: "2026-08-06T12:00:00Z",
  },
};
const examplesResponse: OpportunityCostExamplesResponse = {
  examples: [exampleResponse.example],
};

describe("opportunity-cost query and mutation options", () => {
  afterEach(() => resetSessionExpiry());

  it("loads the list with its shared key and cancellation signal", async () => {
    let requestSignal: AbortSignal | undefined;
    server.use(
      http.get("/api/opportunity-cost-examples", ({ request }) => {
        requestSignal = request.signal;
        return HttpResponse.json(examplesResponse);
      }),
    );
    const queryClient = testQueryClient();
    const options = opportunityCostExamplesQueryOptions();

    await expect(queryClient.fetchQuery(options)).resolves.toEqual(
      examplesResponse,
    );
    expect(options.queryKey).toEqual(queryKeys.opportunityCosts.list());
    expect(options.staleTime).toBe(30 * 1_000);
    expect(requestSignal).toBeInstanceOf(AbortSignal);
  });

  it("uses the shared GET retry policy", () => {
    const retry = opportunityCostExamplesQueryOptions().retry;
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

  it("reports list session expiry with the settings return path", async () => {
    server.use(
      http.get("/api/opportunity-cost-examples", () =>
        HttpResponse.json(
          { error: { code: "unauthorized", message: "Sign in." } },
          { status: 401 },
        ),
      ),
    );
    const listener = vi.fn();
    const unsubscribe = subscribeToSessionExpiry(listener);

    await expect(
      testQueryClient().fetchQuery(opportunityCostExamplesQueryOptions()),
    ).rejects.toMatchObject({ status: 401 });
    expect(listener).toHaveBeenCalledWith({
      returnTo: "/settings/opportunity-costs",
    });
    unsubscribe();
  });

  it.each(["create", "update", "delete"] as const)(
    "%s disables retries and refreshes the list and every stats range",
    async (operation) => {
      server.use(
        http.post("/api/opportunity-cost-examples", () =>
          HttpResponse.json(exampleResponse, { status: 201 }),
        ),
        http.patch(`/api/opportunity-cost-examples/${exampleId}`, () =>
          HttpResponse.json(exampleResponse),
        ),
        http.delete(
          `/api/opportunity-cost-examples/${exampleId}`,
          () => new HttpResponse(null, { status: 204 }),
        ),
      );
      const queryClient = testQueryClient();
      seedAffectedCaches(queryClient);
      await executeMutation(operation, queryClient);
      expect(
        queryClient.getQueryState(queryKeys.opportunityCosts.list())
          ?.isInvalidated,
      ).toBe(true);
      expect(
        queryClient.getQueryState(queryKeys.stats.summary("this_month"))
          ?.isInvalidated,
      ).toBe(true);
      expect(
        queryClient.getQueryState(queryKeys.stats.summary("all_time"))
          ?.isInvalidated,
      ).toBe(true);
    },
  );

  it.each(["create", "update", "delete"] as const)(
    "%s reports session expiry with the settings return path",
    async (operation) => {
      server.use(
        http.post("/api/opportunity-cost-examples", unauthorized),
        http.patch(`/api/opportunity-cost-examples/${exampleId}`, unauthorized),
        http.delete(
          `/api/opportunity-cost-examples/${exampleId}`,
          unauthorized,
        ),
      );
      const listener = vi.fn();
      const unsubscribe = subscribeToSessionExpiry(listener);
      const queryClient = testQueryClient();
      await expect(
        executeMutation(operation, queryClient),
      ).rejects.toMatchObject({ status: 401 });
      expect(listener).toHaveBeenCalledWith({
        returnTo: "/settings/opportunity-costs",
      });
      unsubscribe();
    },
  );
});

function unauthorized() {
  return HttpResponse.json(
    { error: { code: "unauthorized", message: "Sign in." } },
    { status: 401 },
  );
}

function seedAffectedCaches(queryClient: QueryClient): void {
  queryClient.setQueryData(queryKeys.opportunityCosts.list(), examplesResponse);
  queryClient.setQueryData(queryKeys.stats.summary("this_month"), "this month");
  queryClient.setQueryData(queryKeys.stats.summary("all_time"), "all time");
}

async function executeMutation(
  operation: "create" | "update" | "delete",
  queryClient: QueryClient,
): Promise<unknown> {
  if (operation === "create") {
    const options = createOpportunityCostExampleMutationOptions(queryClient);
    expect(options.retry).toBe(false);
    return queryClient
      .getMutationCache()
      .build(queryClient, options)
      .execute(payload);
  }

  if (operation === "update") {
    const options = updateOpportunityCostExampleMutationOptions(queryClient);
    expect(options.retry).toBe(false);
    return queryClient
      .getMutationCache()
      .build(queryClient, options)
      .execute({ exampleId, payload });
  }

  const options = deleteOpportunityCostExampleMutationOptions(queryClient);
  expect(options.retry).toBe(false);
  return queryClient
    .getMutationCache()
    .build(queryClient, options)
    .execute(exampleId);
}

function testQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}
