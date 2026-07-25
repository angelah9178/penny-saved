import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { describe, expect, it, vi } from "vitest";

import { createQueryClient } from "../../app/queryClient";
import { renderWithApp } from "../../test/render";
import { server } from "../../test/server";
import { AuthBootstrap } from "./AuthBootstrap";
import { useAuthSession } from "./useAuthSession";

describe("authentication bootstrap", () => {
  it("shares one authenticated bootstrap result across consumers", async () => {
    let requestCount = 0;
    server.use(
      http.get("/api/auth/me", () => {
        requestCount += 1;
        return HttpResponse.json({
          user: { id: "user-1", email: "person@example.com" },
        });
      }),
    );

    renderWithApp(
      <AuthBootstrap>
        <SessionProbe />
        <SessionProbe />
      </AuthBootstrap>,
    );

    expect(
      await screen.findAllByText("Signed in as person@example.com"),
    ).toHaveLength(2);
    expect(requestCount).toBe(1);
  });

  it("treats an unauthorized current-session response as a guest", async () => {
    renderWithApp(<SessionProbe />);

    expect(await screen.findByText("Browsing as a guest")).toBeInTheDocument();
  });

  it("shows only a neutral loading state while session restoration is pending", async () => {
    server.use(
      http.get("/api/auth/me", async () => {
        await delay(100);
        return HttpResponse.json({
          user: { id: "user-1", email: "person@example.com" },
        });
      }),
    );

    renderWithApp(
      <AuthBootstrap>
        <p>Protected content</p>
        <p>Login content</p>
      </AuthBootstrap>,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Checking your session…",
    );
    expect(screen.queryByText("Protected content")).not.toBeInTheDocument();
    expect(screen.queryByText("Login content")).not.toBeInTheDocument();

    expect(await screen.findByText("Protected content")).toBeInTheDocument();
  });

  it.each([
    ["network failure", () => HttpResponse.error()],
    [
      "server failure",
      () =>
        HttpResponse.json(
          { error: { code: "unavailable", message: "Unavailable." } },
          { status: 503 },
        ),
    ],
  ])(
    "shows a retryable bootstrap error after a %s",
    async (_name, response) => {
      const queryClient = createQueryClient();
      queryClient.setDefaultOptions({
        queries: { retryDelay: 0 },
        mutations: { retry: false },
      });
      server.use(http.get("/api/auth/me", response));

      renderWithApp(
        <AuthBootstrap>
          <p>Application content</p>
        </AuthBootstrap>,
        { queryClient },
      );

      const alert = await screen.findByRole("alert");
      expect(alert).toHaveTextContent(
        "We could not check your session. Please try again.",
      );
      expect(alert.parentElement).toHaveFocus();
      expect(screen.queryByText("Application content")).not.toBeInTheDocument();
    },
  );

  it("retries bootstrap successfully without reloading the application", async () => {
    const user = userEvent.setup();
    let requestCount = 0;
    const queryClient = createQueryClient();
    queryClient.setDefaultOptions({
      queries: { retry: false },
      mutations: { retry: false },
    });
    server.use(
      http.get("/api/auth/me", () => {
        requestCount += 1;
        if (requestCount === 1) {
          return HttpResponse.json(
            {
              error: {
                code: "bad_request",
                message: "The request could not be completed.",
              },
            },
            { status: 400 },
          );
        }
        return HttpResponse.json({
          user: { id: "user-1", email: "person@example.com" },
        });
      }),
    );

    renderWithApp(
      <AuthBootstrap>
        <SessionProbe />
      </AuthBootstrap>,
      { queryClient },
    );

    await user.click(await screen.findByRole("button", { name: "Try again" }));

    expect(
      await screen.findByText("Signed in as person@example.com"),
    ).toBeInTheDocument();
    expect(requestCount).toBe(2);
  });

  it("cancels the bootstrap request when its final consumer unmounts", async () => {
    const aborted = vi.fn();
    const started = vi.fn();
    server.use(
      http.get("/api/auth/me", async ({ request }) => {
        started();
        request.signal.addEventListener("abort", aborted);
        await delay("infinite");
        return HttpResponse.json(authResponse);
      }),
    );

    const view = renderWithApp(
      <AuthBootstrap>
        <p>Application content</p>
      </AuthBootstrap>,
    );
    expect(screen.getByRole("status")).toBeInTheDocument();
    await waitFor(() => expect(started).toHaveBeenCalledOnce());

    view.unmount();

    await waitFor(() => {
      expect(aborted).toHaveBeenCalledOnce();
    });
  });
});

const authResponse = {
  user: { id: "user-1", email: "person@example.com" },
};

function SessionProbe() {
  const session = useAuthSession();

  if (session.status === "authenticated") {
    return <p>Signed in as {session.user.email}</p>;
  }

  if (session.status === "guest") {
    return <p>Browsing as a guest</p>;
  }

  return <p>{session.status}</p>;
}
