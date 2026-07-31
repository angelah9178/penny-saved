import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

  it("creates a new entry through the protected route and shows it in Waiting", async () => {
    const user = userEvent.setup();
    const createdEntry = {
      id: "70000000-0000-4000-8000-000000000001",
      item_name: "Coffee grinder",
      price_cents: 8_999,
      reason_wanted: "Better coffee at home",
      status: "waiting",
      dashboard_bucket: "waiting",
      comment: null,
      created_at: "2026-07-31T14:00:00Z",
      eligible_for_check_in_at: "2026-08-02T14:00:00Z",
      checked_in_at: null,
      updated_at: "2026-07-31T14:00:00Z",
    };
    let created = false;
    useAuthenticatedSession();
    server.use(
      http.post("/api/entries", async ({ request }) => {
        expect(await request.json()).toEqual({
          item_name: "Coffee grinder",
          price_cents: 8_999,
          reason_wanted: "Better coffee at home",
        });
        created = true;
        return HttpResponse.json({ entry: createdEntry }, { status: 201 });
      }),
      http.get("/api/entries", () =>
        HttpResponse.json({
          needs_check_in: [],
          waiting: created ? [createdEntry] : [],
          saved: [],
          purchased: [],
        }),
      ),
    );
    const { router } = renderRoute("/dashboard");

    await user.click(
      await screen.findByRole("link", { name: "Add new impulse purchase" }),
    );
    expect(
      await screen.findByRole("heading", { name: "Add a new entry" }),
    ).toBeInTheDocument();
    await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
    await user.type(screen.getByLabelText("Price"), "89.99");
    await user.type(
      screen.getByLabelText("Reason wanted"),
      "Better coffee at home",
    );
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/dashboard"),
    );
    expect(await screen.findByText("Entry added to Waiting.")).toHaveAttribute(
      "role",
      "status",
    );
    expect(
      await screen.findByRole("heading", { name: "Coffee grinder" }),
    ).toBeVisible();
  });

  it("protects the new-entry route and preserves it as the return path", async () => {
    const { router } = renderRoute("/entries/new");

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(router.state.location).toMatchObject({
      pathname: "/login",
      state: { returnTo: "/entries/new" },
    });
  });

  it("returns an expired create request to login without an unsaved-change prompt", async () => {
    const user = userEvent.setup();
    useAuthenticatedSession();
    server.use(
      http.post("/api/entries", () =>
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
    const { router } = renderRoute("/entries/new");

    await screen.findByRole("heading", { name: "Add a new entry" });
    await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
    await user.type(screen.getByLabelText("Price"), "89.99");
    await user.type(
      screen.getByLabelText("Reason wanted"),
      "Better coffee at home",
    );
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.state).toEqual({
      returnTo: "/entries/new",
      sessionExpired: true,
    });
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
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
