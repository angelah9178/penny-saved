import { render, screen } from "@testing-library/react";
import { http, HttpResponse, delay } from "msw";
import { createMemoryRouter, type InitialEntry } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { server } from "../test/server";
import { appRoutes } from "./router";

const authenticatedResponse = {
  user: { id: "user-1", email: "person@example.com" },
};

describe("authentication routes", () => {
  it("redirects an authenticated index visit to the dashboard", async () => {
    useAuthenticatedSession();
    const { router } = renderRoute("/");

    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/dashboard");
  });

  it("redirects a guest index visit to login", async () => {
    const { router } = renderRoute("/");

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
  });

  it("renders guest-only routes for a guest", async () => {
    renderRoute("/signup");

    expect(
      await screen.findByRole("heading", { name: "Create your account" }),
    ).toBeInTheDocument();
  });

  it("redirects an authenticated user away from a guest-only route", async () => {
    useAuthenticatedSession();
    const { router } = renderRoute("/login");

    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/dashboard");
  });

  it("renders protected content for an authenticated user", async () => {
    useAuthenticatedSession();
    renderRoute("/dashboard");

    expect(
      await screen.findByText(
        "Review your waiting decisions and the purchases you have resolved.",
      ),
    ).toBeInTheDocument();
    expect(screen.getByText("person@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Log out" })).toBeInTheDocument();
  });

  it("redirects a guest from protected content and preserves the intended path", async () => {
    const { router } = renderRoute("/dashboard?view=recent#top");

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(router.state.location).toMatchObject({
      pathname: "/login",
      state: { returnTo: "/dashboard?view=recent#top" },
    });
  });

  it("returns an authenticated user to a validated intended path", async () => {
    useAuthenticatedSession();
    const { router } = renderRoute({
      pathname: "/login",
      state: { returnTo: "/dashboard?view=recent#top" },
    });

    await screen.findByRole("heading", { name: "Dashboard" });
    expect(router.state.location).toMatchObject({
      pathname: "/dashboard",
      search: "?view=recent",
      hash: "#top",
    });
  });

  it("falls back safely from a malicious intended path", async () => {
    useAuthenticatedSession();
    const { router } = renderRoute({
      pathname: "/login",
      state: { returnTo: "https://attacker.example/steal" },
    });

    await screen.findByRole("heading", { name: "Dashboard" });
    expect(router.state.location.pathname).toBe("/dashboard");
  });

  it("shows neither guest nor protected content while bootstrap is pending", () => {
    server.use(
      http.get("/api/auth/me", async () => {
        await delay("infinite");
        return HttpResponse.json(authenticatedResponse);
      }),
    );
    renderRoute("/dashboard");

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading the application…",
    );
    expect(screen.queryByRole("heading", { name: "Dashboard" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Log in" })).toBeNull();
  });

  it("shows the retryable bootstrap error instead of deciding a route", async () => {
    server.use(
      http.get("/api/auth/me", () =>
        HttpResponse.json(
          { error: { code: "bad_request", message: "Failed." } },
          { status: 400 },
        ),
      ),
    );
    renderRoute("/dashboard");

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not check your session. Please try again.",
    );
    expect(screen.queryByRole("heading", { name: "Dashboard" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Log in" })).toBeNull();
  });

  it("keeps the not-found route available to guests", async () => {
    renderRoute("/does-not-exist");

    expect(
      await screen.findByRole("heading", { name: "Page not found" }),
    ).toBeInTheDocument();
  });

  it("shows the session-expired message once on login", async () => {
    renderRoute({
      pathname: "/login",
      state: {
        returnTo: "/dashboard",
        sessionExpired: true,
      },
    });

    expect(
      await screen.findByText("Your session expired. Please sign in again."),
    ).toHaveAttribute("role", "status");
  });
});

function useAuthenticatedSession() {
  server.use(
    http.get("/api/auth/me", () => HttpResponse.json(authenticatedResponse)),
    http.get("/api/entries", () =>
      HttpResponse.json({
        needs_check_in: [],
        waiting: [],
        saved: [],
        purchased: [],
      }),
    ),
  );
}

function renderRoute(initialEntry: InitialEntry) {
  const queryClient = createQueryClient();
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [initialEntry],
  });

  return {
    ...render(<AppProviders queryClient={queryClient} router={router} />),
    queryClient,
    router,
  };
}
