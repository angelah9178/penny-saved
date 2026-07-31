import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { queryKeys } from "../lib/queryKeys";
import { renderWithApp } from "../test/render";
import { server } from "../test/server";
import type { DashboardEntries, EntryResponse } from "../types/api";
import { NewEntryPage } from "./NewEntryPage";

const entryResponse: EntryResponse = {
  entry: {
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
  },
};
const emptyDashboard: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};

describe("NewEntryPage", () => {
  it("creates an entry, refreshes the dashboard, and navigates back", async () => {
    const user = userEvent.setup();
    let submittedBody: unknown;
    server.use(
      http.post("/api/entries", async ({ request }) => {
        submittedBody = await request.json();
        return HttpResponse.json(entryResponse, { status: 201 });
      }),
    );
    const { queryClient, router } = renderWithApp(<NewEntryPage />, {
      initialEntry: "/entries/new",
    });
    queryClient.setQueryData(queryKeys.entries.dashboard(), emptyDashboard);

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/dashboard"),
    );
    expect(router.state.location.state).toEqual({ entryCreated: true });
    expect(submittedBody).toEqual({
      item_name: "Coffee grinder",
      price_cents: 8_999,
      reason_wanted: "Better coffee at home",
    });
    expect(
      queryClient.getQueryState(queryKeys.entries.dashboard())?.isInvalidated,
    ).toBe(true);
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("keeps entered values after a backend failure", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/entries", () =>
        HttpResponse.json(
          {
            error: {
              code: "unavailable",
              message: "Entry service is temporarily unavailable.",
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderWithApp(<NewEntryPage />, { initialEntry: "/entries/new" });

    await fillForm(user);
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Entry service is temporarily unavailable.",
    );
    expect(screen.getByLabelText("Item name")).toHaveValue("Coffee grinder");
    expect(screen.getByLabelText("Price")).toHaveValue("89.99");
  });

  it("warns before discarding an unfinished entry", async () => {
    const user = userEvent.setup();
    const { router } = renderWithApp(<NewEntryPage />, {
      initialEntry: "/entries/new",
    });

    await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
    await user.click(screen.getByRole("link", { name: "Back to dashboard" }));

    expect(screen.getByRole("alertdialog")).toHaveTextContent(
      "Your entry has unsaved changes.",
    );
    expect(router.state.location.pathname).toBe("/entries/new");

    await user.click(screen.getByRole("button", { name: "Stay on this page" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/entries/new");

    await user.click(screen.getByRole("link", { name: "Back to dashboard" }));
    await user.click(
      screen.getByRole("button", { name: "Leave without saving" }),
    );
    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/dashboard"),
    );
  });

  it("registers a browser unload warning only after the form changes", async () => {
    const user = userEvent.setup();
    renderWithApp(<NewEntryPage />, { initialEntry: "/entries/new" });
    const unchangedEvent = new Event("beforeunload", { cancelable: true });

    window.dispatchEvent(unchangedEvent);
    expect(unchangedEvent.defaultPrevented).toBe(false);

    await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
    const changedEvent = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(changedEvent);
    expect(changedEvent.defaultPrevented).toBe(true);
  });
});

async function fillForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
  await user.type(screen.getByLabelText("Price"), "89.99");
  await user.type(
    screen.getByLabelText("Reason wanted"),
    "Better coffee at home",
  );
}
