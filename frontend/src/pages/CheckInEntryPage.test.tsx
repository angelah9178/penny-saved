import { render, screen } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
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

  return render(<AppProviders queryClient={queryClient} router={router} />);
}
