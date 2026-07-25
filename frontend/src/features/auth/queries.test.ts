import { describe, expect, it } from "vitest";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { currentUserQueryOptions } from "./queries";

describe("currentUserQueryOptions", () => {
  it("uses the shared auth key and five-minute freshness window", () => {
    const options = currentUserQueryOptions();

    expect(options.queryKey).toEqual(queryKeys.auth.me());
    expect(options.staleTime).toBe(5 * 60 * 1_000);
  });

  it("does not retry unauthorized current-session requests", () => {
    const retry = currentUserQueryOptions().retry;

    expect(retry).toBeTypeOf("function");
    expect(
      typeof retry === "function"
        ? retry(
            0,
            new ApiError(401, "unauthorized", "Authentication is required."),
          )
        : undefined,
    ).toBe(false);
  });

  it("retries network and server failures at most twice", () => {
    const retry = currentUserQueryOptions().retry;
    const retryFn = typeof retry === "function" ? retry : undefined;

    expect(retryFn?.(0, new ApiError(0, "network_error", "Offline."))).toBe(
      true,
    );
    expect(retryFn?.(1, new ApiError(503, "unavailable", "Unavailable."))).toBe(
      true,
    );
    expect(retryFn?.(2, new ApiError(503, "unavailable", "Unavailable."))).toBe(
      false,
    );
  });
});
