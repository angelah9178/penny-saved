import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { renderWithApp } from "../../test/render";
import { SessionExpiryCoordinator } from "./SessionExpiryCoordinator";
import { resetSessionExpiry, runProtectedRequest } from "./sessionExpiry";

describe("protected request session expiry", () => {
  afterEach(() => resetSessionExpiry());

  it("clears private data and preserves a safe return path for a protected 401", async () => {
    const user = userEvent.setup();
    const { queryClient, router } = renderWithApp(
      <>
        <SessionExpiryCoordinator />
        <ExpiryTrigger returnTo="/entries/new?from=dashboard" />
      </>,
    );
    queryClient.setQueryData(queryKeys.entries.dashboard(), {
      waiting: [{ id: "private-entry" }],
    });

    await user.click(
      screen.getByRole("button", { name: "Load protected data" }),
    );

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.state).toEqual({
      returnTo: "/entries/new?from=dashboard",
      sessionExpired: true,
    });
    expect(
      queryClient.getQueryData(queryKeys.entries.dashboard()),
    ).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.auth.me())).toBeNull();
  });

  it("coalesces concurrent protected 401 responses into one expiry event", async () => {
    const user = userEvent.setup();
    const { queryClient } = renderWithApp(
      <>
        <SessionExpiryCoordinator />
        <ConcurrentExpiryTrigger />
      </>,
    );
    const clear = vi.spyOn(queryClient, "clear");

    await user.click(
      screen.getByRole("button", { name: "Load protected data" }),
    );

    await waitFor(() => expect(clear).toHaveBeenCalledOnce());
  });

  it("does not treat a non-401 protected failure as session expiry", async () => {
    const user = userEvent.setup();
    const { router } = renderWithApp(
      <>
        <SessionExpiryCoordinator />
        <NonAuthFailureTrigger />
      </>,
      { initialEntry: "/dashboard" },
    );

    await user.click(
      screen.getByRole("button", { name: "Load protected data" }),
    );

    await waitFor(() =>
      expect(screen.getByText("Request failed normally.")).toBeInTheDocument(),
    );
    expect(router.state.location.pathname).toBe("/dashboard");
  });
});

function ExpiryTrigger({ returnTo }: { returnTo: string }) {
  return (
    <button
      type="button"
      onClick={() => {
        void runProtectedRequest(
          () =>
            Promise.reject(
              new ApiError(401, "unauthorized", "Authentication is required."),
            ),
          returnTo,
        ).catch(() => undefined);
      }}
    >
      Load protected data
    </button>
  );
}

function ConcurrentExpiryTrigger() {
  return (
    <button
      type="button"
      onClick={() => {
        const unauthorized = () =>
          Promise.reject(
            new ApiError(401, "unauthorized", "Authentication is required."),
          );
        void Promise.allSettled([
          runProtectedRequest(unauthorized, "/entries/new"),
          runProtectedRequest(unauthorized, "/dashboard"),
        ]);
      }}
    >
      Load protected data
    </button>
  );
}

function NonAuthFailureTrigger() {
  const [failed, setFailed] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => {
          void runProtectedRequest(
            () =>
              Promise.reject(
                new ApiError(503, "unavailable", "Service unavailable."),
              ),
            "/dashboard",
          ).catch(() => {
            setFailed(true);
          });
        }}
      >
        Load protected data
      </button>
      {failed ? <p>Request failed normally.</p> : null}
    </>
  );
}
