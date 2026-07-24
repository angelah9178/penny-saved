import { describe, expect, it } from "vitest";

import { ApiError } from "../api/errors";
import { createQueryClient, shouldRetryQuery } from "./queryClient";

describe("createQueryClient", () => {
  it("creates isolated query caches", () => {
    const firstClient = createQueryClient();
    const secondClient = createQueryClient();

    firstClient.setQueryData(["entries", "dashboard"], {
      waiting: [{ id: "entry-1" }],
    });

    expect(firstClient.getQueryData(["entries", "dashboard"])).toEqual({
      waiting: [{ id: "entry-1" }],
    });
    expect(secondClient.getQueryData(["entries", "dashboard"])).toBeUndefined();
    expect(firstClient.getQueryCache()).not.toBe(secondClient.getQueryCache());
  });

  it("uses explicit shared query defaults", () => {
    const defaults = createQueryClient().getDefaultOptions();

    expect(defaults.queries).toMatchObject({
      staleTime: 0,
      refetchOnWindowFocus: false,
      retry: shouldRetryQuery,
    });
    expect(defaults.queries?.retryDelay).toBeTypeOf("function");
  });

  it("disables automatic mutation retries", () => {
    const defaults = createQueryClient().getDefaultOptions();

    expect(defaults.mutations?.retry).toBe(false);
  });
});

describe("shouldRetryQuery", () => {
  it.each([400, 401, 403, 404, 409, 422])(
    "does not retry a %i client error",
    (status) => {
      expect(
        shouldRetryQuery(
          0,
          new ApiError(status, "client_error", "Request failed."),
        ),
      ).toBe(false);
    },
  );

  it.each([500, 502, 503])(
    "retries a %i server error within the limit",
    (status) => {
      expect(
        shouldRetryQuery(
          0,
          new ApiError(status, "server_error", "Request failed."),
        ),
      ).toBe(true);
    },
  );

  it("retries a network error within the limit", () => {
    expect(
      shouldRetryQuery(
        1,
        new ApiError(0, "network_error", "Unable to reach the server."),
      ),
    ).toBe(true);
  });

  it("retries an unknown transient error within the limit", () => {
    expect(shouldRetryQuery(0, new Error("Temporary failure."))).toBe(true);
  });

  it.each([
    new ApiError(0, "network_error", "Unable to reach the server."),
    new ApiError(503, "unavailable", "Service unavailable."),
    new Error("Temporary failure."),
  ])("stops retrying after two retries", (error) => {
    expect(shouldRetryQuery(2, error)).toBe(false);
    expect(shouldRetryQuery(3, error)).toBe(false);
  });
});
