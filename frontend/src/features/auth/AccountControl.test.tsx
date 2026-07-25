import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/queryClient";
import { queryKeys } from "../../lib/queryKeys";
import { renderWithApp } from "../../test/render";
import { server } from "../../test/server";
import type { AuthResponse } from "../../types/api";
import { AccountControl } from "./AccountControl";

const authResponse: AuthResponse = {
  user: { id: "user-1", email: "person@example.com" },
};

describe("AccountControl", () => {
  it.each([
    ["success", () => new Response(null, { status: 200 })],
    [
      "already expired session",
      () =>
        HttpResponse.json(
          {
            error: {
              code: "unauthorized",
              message: "Authentication is required.",
            },
          },
          { status: 401 },
        ),
    ],
    ["network failure", () => HttpResponse.error()],
    [
      "server failure",
      () =>
        HttpResponse.json(
          { error: { code: "unavailable", message: "Unavailable." } },
          { status: 503 },
        ),
    ],
  ])("clears private data and navigates after %s", async (_name, response) => {
    const user = userEvent.setup();
    server.use(http.post("/api/auth/logout", response));
    const queryClient = authenticatedQueryClient();
    queryClient.setQueryData(queryKeys.entries.dashboard(), {
      waiting: [{ id: "private-entry" }],
    });
    const { router } = renderWithApp(<AccountControl />, { queryClient });

    expect(screen.getByText("person@example.com")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Log out" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(
      queryClient.getQueryData(queryKeys.entries.dashboard()),
    ).toBeUndefined();
    expect(queryClient.getQueryData(queryKeys.auth.me())).toBeNull();
    expect(router.state.location.state).toBeNull();
  });

  it("prevents repeated logout requests while pending", async () => {
    const user = userEvent.setup();
    const request = vi.fn();
    server.use(
      http.post("/api/auth/logout", async () => {
        request();
        await delay(100);
        return new Response(null, { status: 200 });
      }),
    );
    renderWithApp(<AccountControl />, {
      queryClient: authenticatedQueryClient(),
    });

    await user.dblClick(screen.getByRole("button", { name: "Log out" }));

    expect(screen.getByRole("button", { name: "Logging out…" })).toBeDisabled();
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
  });
});

function authenticatedQueryClient() {
  const queryClient = createQueryClient();
  queryClient.setQueryData<AuthResponse | null>(
    queryKeys.auth.me(),
    authResponse,
  );
  return queryClient;
}
