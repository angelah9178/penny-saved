import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { createMemoryRouter, type InitialEntry } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { resetSessionExpiry } from "../features/auth/sessionExpiry";
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

  it("renders opportunity-cost settings for an authenticated user", async () => {
    useAuthenticatedSession();
    renderRoute("/settings/opportunity-costs");

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Opportunity-cost examples",
      }),
    ).toBeVisible();
    expect(screen.getByText("person@example.com")).toBeInTheDocument();
  });

  it("protects opportunity-cost settings and preserves its return path", async () => {
    const { router } = renderRoute("/settings/opportunity-costs");

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(router.state.location).toMatchObject({
      pathname: "/login",
      state: { returnTo: "/settings/opportunity-costs" },
    });
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

  it("protects the edit route and preserves the selected entry as the return path", async () => {
    const entryId = "70000000-0000-4000-8000-000000000001";
    const { router } = renderRoute(`/entries/${entryId}/edit`);

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(router.state.location).toMatchObject({
      pathname: "/login",
      state: { returnTo: `/entries/${entryId}/edit` },
    });
  });

  it("protects the check-in route and preserves the selected entry as the return path", async () => {
    const entryId = "70000000-0000-4000-8000-000000000001";
    const { router } = renderRoute(`/entries/${entryId}/check-in`);

    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
    expect(router.state.location).toMatchObject({
      pathname: "/login",
      state: { returnTo: `/entries/${entryId}/check-in` },
    });
  });

  it("returns an expired check-in request to login with the full return path", async () => {
    resetSessionExpiry();
    const user = userEvent.setup();
    const entryId = "70000000-0000-4000-8000-000000000001";
    const eligibleEntry = {
      ...makeWaitingEntry(entryId, {
        item_name: "Coffee grinder",
        price_cents: 8_999,
        reason_wanted: "Better coffee at home",
      }),
      dashboard_bucket: "needs_check_in",
    };
    useAuthenticatedSession();
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json({ entry: eligibleEntry }),
      ),
      http.post(`/api/entries/${entryId}/check-in`, () =>
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
    const { router } = renderRoute(`/entries/${entryId}/check-in`);

    await user.click(
      await screen.findByRole("radio", { name: "I did not buy it" }),
    );
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.state).toEqual({
      returnTo: `/entries/${entryId}/check-in`,
      sessionExpired: true,
    });
  });

  it("opens an eligible check-in from the dashboard with current server context", async () => {
    const user = userEvent.setup();
    const entryId = "70000000-0000-4000-8000-000000000001";
    const eligibleEntry = {
      ...makeWaitingEntry(entryId, {
        item_name: "Coffee grinder",
        price_cents: 8_999,
        reason_wanted: "Better coffee at home",
      }),
      dashboard_bucket: "needs_check_in",
    };
    useAuthenticatedSession();
    server.use(
      http.get("/api/entries", () =>
        HttpResponse.json({
          needs_check_in: [eligibleEntry],
          waiting: [],
          saved: [],
          purchased: [],
        }),
      ),
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json({ entry: eligibleEntry }),
      ),
    );
    const { router } = renderRoute("/dashboard");

    await user.click(await screen.findByRole("link", { name: "Check in" }));

    expect(router.state.location.pathname).toBe(`/entries/${entryId}/check-in`);
    expect(
      await screen.findByRole("heading", { name: "Check in: Coffee grinder" }),
    ).toBeVisible();
    expect(screen.getByText("Better coffee at home")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Submit check-in" }),
    ).toBeVisible();
  });

  it.each([
    ["saved", "I did not buy it", "Saved"],
    ["purchased", "I bought it", "Purchased"],
  ] as const)(
    "completes a %s check-in and returns to the matching dashboard section",
    async (status, choice, sectionHeading) => {
      const user = userEvent.setup();
      const entryId = "70000000-0000-4000-8000-000000000001";
      let resolved = false;
      const eligibleEntry = {
        ...makeWaitingEntry(entryId, {
          item_name: "Coffee grinder",
          price_cents: 8_999,
          reason_wanted: "Better coffee at home",
        }),
        dashboard_bucket: "needs_check_in",
      };
      const resolvedEntry = {
        ...eligibleEntry,
        status,
        dashboard_bucket: status,
        checked_in_at: "2026-08-02T14:05:00Z",
        updated_at: "2026-08-02T14:05:00Z",
      };
      useAuthenticatedSession();
      server.use(
        http.get("/api/entries", () =>
          HttpResponse.json({
            needs_check_in: resolved ? [] : [eligibleEntry],
            waiting: [],
            saved: resolved && status === "saved" ? [resolvedEntry] : [],
            purchased:
              resolved && status === "purchased" ? [resolvedEntry] : [],
          }),
        ),
        http.get(`/api/entries/${entryId}`, () =>
          HttpResponse.json({
            entry: resolved ? resolvedEntry : eligibleEntry,
          }),
        ),
        http.post(`/api/entries/${entryId}/check-in`, () => {
          resolved = true;
          return HttpResponse.json({ entry: resolvedEntry });
        }),
      );
      renderRoute("/dashboard");

      await user.click(await screen.findByRole("link", { name: "Check in" }));
      await user.click(await screen.findByRole("radio", { name: choice }));
      await user.click(screen.getByRole("button", { name: "Submit check-in" }));
      await screen.findByRole("heading", {
        name: status === "saved" ? "Purchase avoided" : "Purchase recorded",
      });
      await user.click(
        screen.getByRole("link", { name: "Return to dashboard" }),
      );

      if (status === "purchased") {
        await user.click(
          await screen.findByRole("button", { name: "Purchased" }),
        );
      }
      expect(
        await screen.findByRole("heading", {
          name: new RegExp(`^${sectionHeading}`),
        }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole("heading", { name: "Coffee grinder" }),
      ).toBeVisible();
      expect(
        screen.queryByRole("link", { name: "Check in" }),
      ).not.toBeInTheDocument();
    },
  );

  it("completes create, edit, and delete without a full-page reload", async () => {
    const user = userEvent.setup();
    const entryId = "70000000-0000-4000-8000-000000000001";
    let storedEntry: Record<string, unknown> | undefined;
    let dashboardRequests = 0;
    useAuthenticatedSession();
    server.use(
      http.get("/api/entries", () => {
        dashboardRequests += 1;
        return HttpResponse.json({
          needs_check_in: [],
          waiting: storedEntry === undefined ? [] : [storedEntry],
          saved: [],
          purchased: [],
        });
      }),
      http.post("/api/entries", async ({ request }) => {
        const payload = (await request.json()) as Record<string, unknown>;
        storedEntry = makeWaitingEntry(entryId, payload);
        return HttpResponse.json({ entry: storedEntry }, { status: 201 });
      }),
      http.get(`/api/entries/${entryId}`, () =>
        storedEntry === undefined
          ? HttpResponse.json(
              { error: { code: "not_found", message: "Not found." } },
              { status: 404 },
            )
          : HttpResponse.json({ entry: storedEntry }),
      ),
      http.patch(`/api/entries/${entryId}`, async ({ request }) => {
        const payload = (await request.json()) as Record<string, unknown>;
        storedEntry = { ...storedEntry, ...payload };
        return HttpResponse.json({ entry: storedEntry });
      }),
      http.delete(`/api/entries/${entryId}`, () => {
        storedEntry = undefined;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { router } = renderRoute("/dashboard");

    await user.click(
      await screen.findByRole("link", { name: "Add new impulse purchase" }),
    );
    await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
    await user.type(screen.getByLabelText("Price"), "89.99");
    await user.type(
      screen.getByLabelText("Reason wanted"),
      "Better coffee at home",
    );
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    expect(
      await screen.findByRole("heading", { name: "Coffee grinder" }),
    ).toBeVisible();
    await user.click(screen.getByRole("link", { name: "Edit" }));
    expect(router.state.location.pathname).toBe(`/entries/${entryId}/edit`);
    await screen.findByRole("heading", { name: "Edit Coffee grinder" });
    await user.clear(screen.getByLabelText("Item name"));
    await user.type(screen.getByLabelText("Item name"), "Burr grinder");
    await user.clear(screen.getByLabelText("Price"));
    await user.type(screen.getByLabelText("Price"), "99.99");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByRole("heading", { name: "Burr grinder" }),
    ).toBeVisible();
    expect(screen.getByText("$99.99")).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Delete" }));
    expect(
      screen.getByRole("alertdialog", { name: "Delete Burr grinder?" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Delete entry" }));

    expect(
      await screen.findByText("You have no purchases in the waiting period."),
    ).toBeVisible();
    expect(screen.getByText("Burr grinder was deleted.")).toHaveAttribute(
      "role",
      "status",
    );
    expect(storedEntry).toBeUndefined();
    expect(dashboardRequests).toBeGreaterThanOrEqual(4);
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
    expect(document.title).toBe("Page not found | A Penny Saved");
    expect(
      screen.getByRole("link", { name: "Go to A Penny Saved" }),
    ).toHaveAttribute("href", "/");
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

function makeWaitingEntry(
  id: string,
  payload: Record<string, unknown>,
): Record<string, unknown> {
  return {
    id,
    ...payload,
    status: "waiting",
    dashboard_bucket: "waiting",
    comment: null,
    created_at: "2026-07-31T14:00:00Z",
    eligible_for_check_in_at: "2026-08-02T14:00:00Z",
    checked_in_at: null,
    updated_at: "2026-07-31T14:00:00Z",
  };
}
