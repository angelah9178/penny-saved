import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { queryKeys } from "../lib/queryKeys";
import { server } from "../test/server";
import type { DashboardEntries, EntryResponse } from "../types/api";
import { EditEntryPage } from "./EditEntryPage";

const entryId = "70000000-0000-4000-8000-000000000001";
const entryResponse: EntryResponse = {
  entry: {
    id: entryId,
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
  },
};
const emptyDashboard: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};

describe("EditEntryPage", () => {
  it("loads an existing entry into the shared edit form", async () => {
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json(entryResponse),
      ),
    );
    renderPage();

    expect(
      await screen.findByRole("heading", { name: "Edit Coffee grinder" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Item name")).toHaveValue("Coffee grinder");
    expect(screen.getByLabelText("Price")).toHaveValue("89.99");
    expect(screen.getByLabelText("Reason wanted")).toHaveValue(
      "Better coffee at home",
    );
  });

  it("updates the allowed fields and returns to the dashboard", async () => {
    const user = userEvent.setup();
    let submittedBody: unknown;
    const updatedResponse: EntryResponse = {
      entry: {
        ...entryResponse.entry,
        item_name: "Burr coffee grinder",
        price_cents: 9_999,
        reason_wanted: "More consistent coffee",
      },
    };
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json(entryResponse),
      ),
      http.patch(`/api/entries/${entryId}`, async ({ request }) => {
        submittedBody = await request.json();
        return HttpResponse.json(updatedResponse);
      }),
    );
    const { queryClient, router } = renderPage();
    queryClient.setQueryData(queryKeys.entries.dashboard(), emptyDashboard);

    await screen.findByLabelText("Item name");
    await user.clear(screen.getByLabelText("Item name"));
    await user.type(screen.getByLabelText("Item name"), "Burr coffee grinder");
    await user.clear(screen.getByLabelText("Price"));
    await user.type(screen.getByLabelText("Price"), "99.99");
    await user.clear(screen.getByLabelText("Reason wanted"));
    await user.type(
      screen.getByLabelText("Reason wanted"),
      "More consistent coffee",
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/dashboard"),
    );
    expect(router.state.location.state).toEqual({ entryUpdated: true });
    expect(submittedBody).toEqual({
      item_name: "Burr coffee grinder",
      price_cents: 9_999,
      reason_wanted: "More consistent coffee",
    });
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
  });

  it("does not offer editing when server data is already resolved", async () => {
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json({
          entry: {
            ...entryResponse.entry,
            status: "saved",
            dashboard_bucket: "saved",
          },
        }),
      ),
    );
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This entry is no longer waiting and cannot be edited.",
    );
    expect(
      screen.queryByRole("button", { name: "Save changes" }),
    ).not.toBeInTheDocument();
  });

  it("refreshes server truth when a stale edit receives a lifecycle conflict", async () => {
    const user = userEvent.setup();
    let conflictReceived = false;
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json({
          entry: conflictReceived
            ? {
                ...entryResponse.entry,
                status: "saved",
                dashboard_bucket: "saved",
              }
            : entryResponse.entry,
        }),
      ),
      http.patch(`/api/entries/${entryId}`, () => {
        conflictReceived = true;
        return HttpResponse.json(
          {
            error: {
              code: "invalid_entry_status",
              message: "Only waiting entries may be updated.",
            },
          },
          { status: 409 },
        );
      }),
    );
    const { queryClient } = renderPage();
    queryClient.setQueryData(queryKeys.entries.dashboard(), emptyDashboard);

    await screen.findByLabelText("Item name");
    await user.type(screen.getByLabelText("Item name"), " updated");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "This entry is no longer waiting and cannot be edited.",
    );
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
  });

  it.each([
    [403, "You do not have access to that entry."],
    [404, "We could not find that entry."],
    [503, "We could not load this entry. Please try again."],
  ])("shows a safe detail error for HTTP %d", async (status, message) => {
    server.use(
      http.get(`/api/entries/${entryId}`, () =>
        HttpResponse.json(
          { error: { code: "request_failed", message: "Backend detail." } },
          { status },
        ),
      ),
    );
    renderPage();

    expect(
      await screen.findByRole("alert", undefined, { timeout: 5_000 }),
    ).toHaveTextContent(message);
  });
});

function renderPage() {
  const queryClient = createQueryClient();
  const router = createMemoryRouter(
    [
      { path: "entries/:entryId/edit", element: <EditEntryPage /> },
      { path: "dashboard", element: <h1>Dashboard</h1> },
    ],
    { initialEntries: [`/entries/${entryId}/edit`] },
  );

  return {
    ...render(<AppProviders queryClient={queryClient} router={router} />),
    queryClient,
    router,
  };
}
