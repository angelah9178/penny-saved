import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { queryKeys } from "../lib/queryKeys";
import { server } from "../test/server";
import type { EntryResponse } from "../types/api";
import { CheckInEntryPage } from "./CheckInEntryPage";

const entryId = "70000000-0000-4000-8000-000000000001";
const eligibleResponse: EntryResponse = {
  entry: {
    id: entryId,
    item_name: "Coffee grinder",
    price_cents: 8_999,
    reason_wanted: "Better coffee at home",
    status: "waiting",
    dashboard_bucket: "needs_check_in",
    comment: null,
    created_at: "2026-07-31T14:00:00Z",
    eligible_for_check_in_at: "2026-08-02T14:00:00Z",
    checked_in_at: null,
    updated_at: "2026-07-31T14:00:00Z",
  },
};

describe("CheckInEntryPage", () => {
  it("shows the original server context and form for an eligible entry", async () => {
    respondWithEntry(eligibleResponse);
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Check in: Coffee grinder" }),
    ).toBeVisible();
    const context = screen.getByRole("region", {
      name: "Your original decision",
    });
    expect(context).toHaveTextContent("Coffee grinder");
    expect(context).toHaveTextContent("$89.99");
    expect(context).toHaveTextContent("Better coffee at home");
    expect(context.querySelectorAll("time")).toHaveLength(2);
    expect(
      screen.getByRole("group", { name: "What happened with this purchase?" }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Back to dashboard" }),
    ).toHaveAttribute("href", "/dashboard");
  });

  it("shows a loading state while current server detail is pending", () => {
    server.use(
      http.get(`/api/entries/${entryId}`, async () => {
        await delay("infinite");
        return HttpResponse.json(eligibleResponse);
      }),
    );
    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent("Loading check-in…");
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
  });

  it("keeps long decision context available without truncating its meaning", async () => {
    const longItemName =
      `Coffee grinder ${"with accessories ".repeat(12)}`.trim();
    const longReason =
      `I wanted more control over each cup because ${"consistency matters ".repeat(30)}`.trim();
    respondWithEntry({
      entry: {
        ...eligibleResponse.entry,
        item_name: longItemName,
        price_cents: 999_999_999_999,
        reason_wanted: longReason,
      },
    });
    renderPage();

    expect(
      await screen.findByRole("heading", { name: `Check in: ${longItemName}` }),
    ).toBeVisible();
    expect(screen.getByText(longReason)).toBeVisible();
    expect(screen.getByText("$9,999,999,999.99")).toBeVisible();
    expect(
      screen.getByRole("button", { name: "Submit check-in" }),
    ).toBeVisible();
  });

  it.each([
    ["saved", "I did not buy it", "Purchase avoided", "Server reflection"],
    ["purchased", "I bought it", "Purchase recorded", null],
  ] as const)(
    "shows the server-confirmed %s outcome and refreshes affected caches",
    async (status, choice, heading, returnedComment) => {
      const user = userEvent.setup();
      const checkedInAt = "2026-08-02T14:05:00Z";
      let submittedBody: unknown;
      respondWithEntry(eligibleResponse);
      server.use(
        http.post(`/api/entries/${entryId}/check-in`, async ({ request }) => {
          submittedBody = await request.json();
          return HttpResponse.json({
            entry: {
              ...eligibleResponse.entry,
              status,
              dashboard_bucket: status,
              comment: returnedComment,
              checked_in_at: checkedInAt,
              updated_at: checkedInAt,
            },
          });
        }),
      );
      const { queryClient, router } = renderPage();
      queryClient.setQueryData(queryKeys.entries.dashboard(), {
        needs_check_in: [eligibleResponse.entry],
        waiting: [],
        saved: [],
        purchased: [],
      });
      queryClient.setQueryData(
        queryKeys.stats.summary("this_month"),
        "cached statistics",
      );

      await screen.findByRole("button", { name: "Submit check-in" });
      await user.click(screen.getByRole("radio", { name: choice }));
      await user.type(
        screen.getByLabelText("Reflection (optional)"),
        "Submitted reflection",
      );
      await user.click(screen.getByRole("button", { name: "Submit check-in" }));

      const confirmation = await screen.findByRole("status");
      expect(confirmation).toHaveFocus();
      expect(screen.getByRole("heading", { name: heading })).toBeVisible();
      expect(confirmation).toHaveTextContent(
        `confirmed this entry as ${status}`,
      );
      if (returnedComment === null) {
        expect(screen.queryByText(/Reflection:/)).not.toBeInTheDocument();
      } else {
        expect(confirmation).toHaveTextContent(
          `Reflection: ${returnedComment}`,
        );
        expect(confirmation).not.toHaveTextContent("Submitted reflection");
      }
      expect(screen.queryByRole("radio")).not.toBeInTheDocument();
      expect(submittedBody).toEqual({
        result: status,
        comment: "Submitted reflection",
      });
      const cachedDetail = queryClient.getQueryData<EntryResponse>(
        queryKeys.entries.detail(entryId),
      );
      expect(cachedDetail?.entry.status).toBe(status);
      expect(cachedDetail?.entry.comment).toBe(returnedComment);
      expect(
        queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
      ).toBe(true);
      expect(
        queryClient.getQueryState(queryKeys.stats.summary("this_month"))
          ?.isInvalidated,
      ).toBe(true);

      await user.click(
        screen.getByRole("link", { name: "Return to dashboard" }),
      );
      await waitFor(() =>
        expect(router.state.location.pathname).toBe("/dashboard"),
      );
    },
  );

  it("refreshes server truth when the server rejects an early check-in", async () => {
    const user = userEvent.setup();
    let conflictReceived = false;
    let detailRequests = 0;
    server.use(
      http.get(`/api/entries/${entryId}`, () => {
        detailRequests += 1;
        return HttpResponse.json({
          entry: conflictReceived
            ? {
                ...eligibleResponse.entry,
                dashboard_bucket: "waiting",
              }
            : eligibleResponse.entry,
        });
      }),
      http.post(`/api/entries/${entryId}/check-in`, () => {
        conflictReceived = true;
        return HttpResponse.json(
          {
            error: {
              code: "early_check_in",
              message: "The entry is not eligible yet.",
            },
          },
          { status: 409 },
        );
      }),
    );
    const { queryClient } = renderPage();
    queryClient.setQueryData(queryKeys.entries.dashboard(), {
      needs_check_in: [eligibleResponse.entry],
      waiting: [],
      saved: [],
      purchased: [],
    });

    await user.click(
      await screen.findByRole("radio", { name: "I did not buy it" }),
    );
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    expect(
      await screen.findByText(/still in its waiting period/i),
    ).toBeVisible();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(detailRequests).toBeGreaterThanOrEqual(2);
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
  });

  it("shows the already-resolved server state after a stale-status conflict", async () => {
    const user = userEvent.setup();
    let conflictReceived = false;
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json({
          entry: conflictReceived
            ? {
                ...eligibleResponse.entry,
                status: "saved",
                dashboard_bucket: "saved",
                checked_in_at: "2026-08-02T14:05:00Z",
              }
            : eligibleResponse.entry,
        }),
      ),
      http.post(`/api/entries/${entryId}/check-in`, () => {
        conflictReceived = true;
        return HttpResponse.json(
          {
            error: {
              code: "invalid_entry_status",
              message: "The entry is no longer waiting.",
            },
          },
          { status: 409 },
        );
      }),
    );
    renderPage();

    await user.click(await screen.findByRole("radio", { name: "I bought it" }));
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    expect(
      await screen.findByText(/already been resolved as saved/i),
    ).toBeVisible();
    expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Check-in complete" }),
    ).toBeNull();
  });

  it.each([
    [403, "You no longer have access to this entry."],
    [404, "This entry is no longer available."],
  ])(
    "replaces the form after mutation access loss with HTTP %d",
    async (status, message) => {
      const user = userEvent.setup();
      respondWithEntry(eligibleResponse);
      server.use(
        http.post(`/api/entries/${entryId}/check-in`, () =>
          HttpResponse.json(
            {
              error: {
                code: "access_lost",
                message: "Private backend detail.",
              },
            },
            { status },
          ),
        ),
      );
      renderPage();

      await user.click(
        await screen.findByRole("radio", { name: "I did not buy it" }),
      );
      await user.click(screen.getByRole("button", { name: "Submit check-in" }));

      expect(await screen.findByRole("alert")).toHaveTextContent(message);
      expect(
        screen.queryByText("Private backend detail."),
      ).not.toBeInTheDocument();
      expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    },
  );

  it("preserves input and allows an explicit retry after a request failure", async () => {
    const user = userEvent.setup();
    let attempts = 0;
    respondWithEntry(eligibleResponse);
    server.use(
      http.post(`/api/entries/${entryId}/check-in`, () => {
        attempts += 1;
        if (attempts === 1) {
          return HttpResponse.json(
            {
              error: {
                code: "unavailable",
                message: "The service is temporarily unavailable.",
              },
            },
            { status: 503 },
          );
        }
        return HttpResponse.json({
          entry: {
            ...eligibleResponse.entry,
            status: "saved",
            dashboard_bucket: "saved",
            comment: "My reflection",
            checked_in_at: "2026-08-02T14:05:00Z",
            updated_at: "2026-08-02T14:05:00Z",
          },
        });
      }),
    );
    renderPage();

    await user.click(
      await screen.findByRole("radio", { name: "I did not buy it" }),
    );
    await user.type(
      screen.getByLabelText("Reflection (optional)"),
      "My reflection",
    );
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The service is temporarily unavailable.",
    );
    expect(
      screen.getByRole("radio", { name: "I did not buy it" }),
    ).toBeChecked();
    expect(screen.getByLabelText("Reflection (optional)")).toHaveValue(
      "My reflection",
    );
    expect(
      screen.getByRole("button", { name: "Submit check-in" }),
    ).toBeEnabled();

    await user.click(screen.getByRole("button", { name: "Submit check-in" }));
    expect(
      await screen.findByRole("heading", { name: "Purchase avoided" }),
    ).toBeVisible();
    expect(attempts).toBe(2);
  });

  it.each([
    ["waiting", "waiting", "still in its waiting period"],
    ["saved", "saved", "already been resolved as saved"],
    ["purchased", "purchased", "already been resolved as purchased"],
  ] as const)(
    "does not offer the form for a %s entry in the %s bucket",
    async (status, dashboardBucket, message) => {
      respondWithEntry({
        entry: {
          ...eligibleResponse.entry,
          status,
          dashboard_bucket: dashboardBucket,
        },
      });
      renderPage();

      expect(await screen.findByText(new RegExp(message, "i"))).toBeVisible();
      expect(screen.queryByRole("radio")).not.toBeInTheDocument();
    },
  );

  it.each([
    [403, "You do not have access to that entry."],
    [404, "We could not find that entry."],
    [422, "We could not load this entry. Please try again."],
    [503, "We could not load this entry. Please try again."],
  ])("shows a safe detail error for HTTP %d", async (status, message) => {
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json(
          {
            error: {
              code: "request_failed",
              message: "Private backend detail.",
            },
          },
          { status },
        ),
      ),
    );
    renderPage();

    expect(
      await screen.findByRole("alert", undefined, { timeout: 5_000 }),
    ).toHaveTextContent(message);
    expect(
      screen.queryByText("Private backend detail."),
    ).not.toBeInTheDocument();
  });
});

function respondWithEntry(response: EntryResponse): void {
  server.use(
    http.get(`/api/entries/${entryId}`, () => HttpResponse.json(response)),
  );
}

function renderPage() {
  const queryClient = createQueryClient();
  const router = createMemoryRouter(
    [
      { path: "entries/:entryId/check-in", element: <CheckInEntryPage /> },
      { path: "dashboard", element: <h1>Dashboard</h1> },
    ],
    { initialEntries: [`/entries/${entryId}/check-in`] },
  );

  return {
    ...render(<AppProviders queryClient={queryClient} router={router} />),
    queryClient,
    router,
  };
}
