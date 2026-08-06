import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { queryKeys } from "../lib/queryKeys";
import { server } from "../test/server";
import type {
  DashboardEntries,
  EntryResponse,
  EntryStatus,
  StatsSummary,
} from "../types/api";
import { DashboardPage } from "./DashboardPage";
import { EntryDetailPage } from "./EntryDetailPage";

const entryId = "70000000-0000-4000-8000-000000000001";

describe("EntryDetailPage", () => {
  it.each(["saved", "purchased"] satisfies EntryStatus[])(
    "shows the comment editor for a %s entry",
    async (status) => {
      renderPage(entryResponse(status));

      expect(
        await screen.findByRole("heading", { name: "Edit comment" }),
      ).toBeVisible();
      expect(screen.getByLabelText("Comment")).toHaveValue(
        "Original reflection",
      );
      expect(
        screen.getByRole("button", { name: "Save comment" }),
      ).toBeEnabled();
      expect(screen.getByText(status)).toBeVisible();
    },
  );

  it("shows waiting context without exposing the resolved comment editor", async () => {
    renderPage(entryResponse("waiting"));

    expect(
      await screen.findByText(/Comments can be edited after/),
    ).toBeVisible();
    expect(screen.queryByLabelText("Comment")).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Save comment" }),
    ).not.toBeInTheDocument();
  });

  it("replaces the editor with one safe unavailable state after access loss", async () => {
    const user = userEvent.setup();
    server.use(
      http.patch(`/api/entries/${entryId}/comment`, () =>
        HttpResponse.json(
          { error: { code: "forbidden", message: "Private owner details" } },
          { status: 403 },
        ),
      ),
    );
    renderPage(entryResponse("saved"));
    const comment = await screen.findByLabelText("Comment");
    await user.clear(comment);
    await user.type(comment, "Updated reflection");
    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(
      await screen.findByText("This entry is no longer available."),
    ).toBeVisible();
    expect(screen.queryByLabelText("Comment")).not.toBeInTheDocument();
    expect(screen.queryByText("Private owner details")).not.toBeInTheDocument();
  });

  it("refreshes server truth after a lifecycle conflict", async () => {
    const user = userEvent.setup();
    const waitingResponse = entryResponse("waiting");
    server.use(
      http.patch(`/api/entries/${entryId}/comment`, () =>
        HttpResponse.json(
          {
            error: {
              code: "invalid_entry_status",
              message: "Stored status changed.",
            },
          },
          { status: 409 },
        ),
      ),
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json(waitingResponse),
      ),
      http.get("/api/entries", () => HttpResponse.json(emptyDashboard)),
    );
    renderPage(entryResponse("saved"));
    const comment = await screen.findByLabelText("Comment");
    await user.clear(comment);
    await user.type(comment, "Stale edit");
    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(
      await screen.findByText(
        /Only saved or purchased entries support comment editing/,
      ),
    ).toBeVisible();
    expect(
      await screen.findByText(/Comments can be edited after/),
    ).toBeVisible();
    expect(screen.queryByLabelText("Comment")).not.toBeInTheDocument();
  });

  it("integrates dashboard navigation, saving, and exact cache refresh behavior", async () => {
    const user = userEvent.setup();
    const initial = entryResponse("saved");
    const updated: EntryResponse = {
      entry: {
        ...initial.entry,
        comment: "Borrowed one instead.",
        updated_at: "2026-08-01T16:00:00Z",
      },
    };
    let submittedBody: unknown;
    server.use(
      http.patch(`/api/entries/${entryId}/comment`, async ({ request }) => {
        submittedBody = await request.json();
        return HttpResponse.json(updated);
      }),
    );
    const queryClient = createQueryClient();
    queryClient.setQueryData(queryKeys.entries.dashboard(), {
      ...emptyDashboard,
      saved: [initial.entry],
    } satisfies DashboardEntries);
    queryClient.setQueryData(queryKeys.entries.detail(entryId), initial);
    queryClient.setQueryData(queryKeys.stats.summary("this_month"), {
      range: "this_month",
      total_saved_cents: 25_000,
      avoided_purchase_count: 4,
      purchased_count: 1,
      opportunity_costs: [],
    } satisfies StatsSummary);
    const router = createMemoryRouter(
      [
        { path: "/dashboard", element: <DashboardPage /> },
        { path: "/entries/:entryId", element: <EntryDetailPage /> },
      ],
      { initialEntries: ["/dashboard"] },
    );
    render(<AppProviders queryClient={queryClient} router={router} />);

    await user.click(await screen.findByRole("link", { name: "Edit comment" }));
    const comment = await screen.findByLabelText("Comment");
    await user.clear(comment);
    await user.type(comment, "  Borrowed one instead.  ");
    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Comment saved.",
    );
    expect(submittedBody).toEqual({ comment: "Borrowed one instead." });
    expect(queryClient.getQueryData(queryKeys.entries.detail(entryId))).toEqual(
      updated,
    );
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
    expect(
      queryClient.getQueryState(queryKeys.stats.summary("this_month"))
        ?.isInvalidated,
    ).toBe(false);
  });
});

const emptyDashboard: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};

function renderPage(response: EntryResponse) {
  const queryClient = createQueryClient();
  queryClient.setQueryData(["entries", "detail", entryId], response);
  const router = createMemoryRouter(
    [{ path: "/entries/:entryId", element: <EntryDetailPage /> }],
    { initialEntries: [`/entries/${entryId}`] },
  );
  return render(<AppProviders queryClient={queryClient} router={router} />);
}

function entryResponse(status: EntryStatus): EntryResponse {
  const resolved = status !== "waiting";
  return {
    entry: {
      id: entryId,
      item_name: "Coffee grinder",
      price_cents: 8_999,
      reason_wanted: "Better coffee at home",
      status,
      dashboard_bucket: status,
      comment: "Original reflection",
      created_at: "2026-07-28T14:00:00Z",
      eligible_for_check_in_at: "2026-07-30T14:00:00Z",
      checked_in_at: resolved ? "2026-07-30T15:00:00Z" : null,
      updated_at: "2026-07-30T15:00:00Z",
    },
  };
}
