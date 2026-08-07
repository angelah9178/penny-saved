import { act, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";

import { SessionExpiryCoordinator } from "../features/auth/SessionExpiryCoordinator";
import { resetSessionExpiry } from "../features/auth/sessionExpiry";
import { queryKeys } from "../lib/queryKeys";
import { renderWithApp } from "../test/render";
import { server } from "../test/server";
import type { DashboardBucket, DashboardEntries, Entry } from "../types/api";
import { DashboardPage } from "./DashboardPage";

describe("DashboardPage", () => {
  afterEach(() => {
    resetSessionExpiry();
  });

  it("lists every backend bucket on the real dashboard", async () => {
    const response: DashboardEntries = {
      needs_check_in: [makeEntry("needs-1", "Headphones", "needs_check_in")],
      waiting: [makeEntry("waiting-1", "Desk lamp", "waiting")],
      saved: [makeEntry("saved-1", "Running shoes", "saved")],
      purchased: [makeEntry("purchased-1", "Coffee grinder", "purchased")],
    };
    useDashboardResponse(response);

    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    expect(
      await screen.findByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("link", { name: "Add new impulse purchase" }),
    ).toHaveAttribute("href", "/entries/new");
    expect(
      screen.getByRole("link", {
        name: "Manage opportunity-cost examples",
      }),
    ).toHaveAttribute("href", "/settings/opportunity-costs");
    expect(screen.getByText("Headphones")).toBeInTheDocument();
    expect(screen.getByText("Desk lamp")).toBeInTheDocument();
    expect(screen.getByText("Running shoes")).toBeInTheDocument();
    expect(screen.getByText("Coffee grinder")).toBeInTheDocument();

    const purchased = screen.getByText("Purchased (1)").closest("details");
    expect(purchased).not.toBeNull();
    expect(purchased).not.toHaveAttribute("open");
  });

  it("shows a separate explanation for every empty backend array", async () => {
    useDashboardResponse({
      needs_check_in: [],
      waiting: [],
      saved: [],
      purchased: [],
    });

    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    expect(
      await screen.findByText("Nothing needs your attention right now."),
    ).toBeVisible();
    expect(
      screen.getByText("You have no purchases in the waiting period."),
    ).toBeVisible();
    expect(
      screen.getByText("Entries you decide not to buy will appear here."),
    ).toBeVisible();
    expect(
      screen.getByText("Entries you decide to buy will appear here."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Purchased (0)").closest("details"),
    ).not.toHaveAttribute("open");
  });

  it("preserves the order supplied by the backend", async () => {
    useDashboardResponse({
      needs_check_in: [],
      waiting: [
        makeEntry("waiting-2", "Backend first", "waiting"),
        makeEntry("waiting-1", "Backend second", "waiting"),
      ],
      saved: [],
      purchased: [],
    });

    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    const waitingHeading = await screen.findByRole("heading", {
      level: 2,
      name: /Waiting/,
    });
    const waitingSection = waitingHeading.closest("section");
    expect(waitingSection).not.toBeNull();
    const cards = within(waitingSection as HTMLElement).getAllByRole("article");
    expect(cards[0]).toHaveTextContent("Backend first");
    expect(cards[1]).toHaveTextContent("Backend second");
  });

  it("shows an honest loading state before the first response", async () => {
    server.use(
      http.get("/api/entries", async () => {
        await delay(50);
        return HttpResponse.json(emptyDashboard());
      }),
    );

    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading your entries…",
    );
    expect(
      await screen.findByRole("heading", { level: 1, name: "Dashboard" }),
    ).toBeVisible();
  });

  it("keeps dashboard content visible during a background refresh", async () => {
    useDashboardResponse({
      ...emptyDashboard(),
      waiting: [makeEntry("waiting-1", "Visible while updating", "waiting")],
    });
    const { queryClient } = renderWithApp(<DashboardPage />, {
      initialEntry: "/dashboard",
    });
    expect(await screen.findByText("Visible while updating")).toBeVisible();

    server.use(
      http.get("/api/entries", async () => {
        await delay("infinite");
        return HttpResponse.json(emptyDashboard());
      }),
    );
    act(() => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.entries.dashboard(),
      });
    });

    expect(await screen.findByText("Updating dashboard…")).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.getByText("Visible while updating")).toBeVisible();
  });

  it("shows an error after automatic network retries are exhausted", async () => {
    let requestCount = 0;
    server.use(
      http.get("/api/entries", () => {
        requestCount += 1;
        return HttpResponse.error();
      }),
    );

    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    expect(
      await screen.findByRole("alert", {}, { timeout: 4_000 }),
    ).toHaveTextContent("We could not load your dashboard. Please try again.");
    expect(requestCount).toBe(3);
    expect(
      screen.queryByText("Nothing needs your attention right now."),
    ).not.toBeInTheDocument();
  });

  it("lets the user retry a temporary server failure", async () => {
    const user = userEvent.setup();
    let requestCount = 0;
    server.use(
      http.get("/api/entries", () => {
        requestCount += 1;

        if (requestCount <= 3) {
          return HttpResponse.json(
            {
              error: {
                code: "unavailable",
                message: "Dashboard temporarily unavailable.",
              },
            },
            { status: 503 },
          );
        }

        return HttpResponse.json({
          ...emptyDashboard(),
          saved: [makeEntry("saved-1", "Loaded after retry", "saved")],
        });
      }),
    );

    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    const retryButton = await screen.findByRole(
      "button",
      { name: "Retry dashboard" },
      { timeout: 4_000 },
    );
    await user.tab();
    expect(retryButton).toHaveFocus();
    await user.keyboard("{Enter}");

    expect(await screen.findByText("Loaded after retry")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(requestCount).toBe(4);
  });

  it("sends an expired session to login with the dashboard return path", async () => {
    server.use(
      http.get("/api/entries", () =>
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

    const { router } = renderWithApp(
      <>
        <SessionExpiryCoordinator />
        <DashboardPage />
      </>,
      { initialEntry: "/dashboard" },
    );

    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
    expect(router.state.location.state).toEqual({
      returnTo: "/dashboard",
      sessionExpired: true,
    });
  });

  it("does not turn a cancelled request into an error state", async () => {
    server.use(
      http.get("/api/entries", async () => {
        await delay("infinite");
        return HttpResponse.json(emptyDashboard());
      }),
    );
    const { queryClient } = renderWithApp(<DashboardPage />, {
      initialEntry: "/dashboard",
    });
    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading your entries…",
    );

    await act(() =>
      queryClient.cancelQueries({ queryKey: queryKeys.entries.dashboard() }),
    );

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("opens the Purchased disclosure from the keyboard", async () => {
    const user = userEvent.setup();
    useDashboardResponse(emptyDashboard());
    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });
    await screen.findByRole("heading", { level: 1, name: "Dashboard" });

    await user.tab();
    expect(
      screen.getByRole("link", { name: "Add new impulse purchase" }),
    ).toHaveFocus();
    await user.tab();
    expect(
      screen.getByRole("link", { name: "Manage opportunity-cost examples" }),
    ).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("combobox", { name: "Time range" })).toHaveFocus();
    await user.tab();
    const summary = screen.getByText("Purchased (0)");
    expect(summary).toHaveFocus();

    await user.keyboard("{Enter}");
    expect(summary.closest("details")).toHaveAttribute("open");
    await user.keyboard(" ");
    expect(summary.closest("details")).not.toHaveAttribute("open");
  });

  it("requires confirmation and restores focus when deletion is cancelled", async () => {
    const user = userEvent.setup();
    useDashboardResponse({
      ...emptyDashboard(),
      waiting: [makeEntry("waiting-1", "Desk lamp", "waiting")],
    });
    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    const deleteTrigger = await screen.findByRole("button", { name: "Delete" });
    await user.click(deleteTrigger);

    const dialog = screen.getByRole("alertdialog", {
      name: "Delete Desk lamp?",
    });
    expect(dialog).toHaveTextContent("cannot be undone");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => expect(deleteTrigger).toHaveFocus());
    expect(screen.getByText("Desk lamp")).toBeVisible();
  });

  it("keeps keyboard focus inside the delete confirmation and closes on Escape", async () => {
    const user = userEvent.setup();
    useDashboardResponse({
      ...emptyDashboard(),
      waiting: [makeEntry("waiting-1", "Desk lamp", "waiting")],
    });
    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    const deleteTrigger = await screen.findByRole("button", { name: "Delete" });
    await user.click(deleteTrigger);
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Delete entry" });

    await user.tab({ shift: true });
    expect(confirm).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    await waitFor(() => expect(deleteTrigger).toHaveFocus());
  });

  it("removes an entry only after a confirmed 204 response", async () => {
    const user = userEvent.setup();
    let deleted = false;
    let deleteRequests = 0;
    server.use(
      http.get("/api/entries", () =>
        HttpResponse.json({
          ...emptyDashboard(),
          waiting: deleted
            ? []
            : [makeEntry("waiting-1", "Desk lamp", "waiting")],
        }),
      ),
      http.delete("/api/entries/waiting-1", async () => {
        deleteRequests += 1;
        await delay(50);
        deleted = true;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await user.dblClick(screen.getByRole("button", { name: "Delete entry" }));

    expect(screen.getByRole("button", { name: "Deleting…" })).toBeDisabled();
    const deletionNotice = await screen.findByText("Desk lamp was deleted.");
    expect(deletionNotice).toHaveAttribute("role", "status");
    expect(deletionNotice).toHaveFocus();
    expect(
      await screen.findByText("You have no purchases in the waiting period."),
    ).toBeVisible();
    expect(deleteRequests).toBe(1);
  });

  it("keeps the entry and confirmation available after deletion fails", async () => {
    const user = userEvent.setup();
    useDashboardResponse({
      ...emptyDashboard(),
      waiting: [makeEntry("waiting-1", "Desk lamp", "waiting")],
    });
    server.use(
      http.delete("/api/entries/waiting-1", () =>
        HttpResponse.json(
          {
            error: {
              code: "unavailable",
              message: "Deletion is temporarily unavailable.",
            },
          },
          { status: 503 },
        ),
      ),
    );
    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Delete entry" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Deletion is temporarily unavailable.",
    );
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(screen.getByText("Desk lamp")).toBeVisible();
  });

  it("refreshes the dashboard when stale deletion receives a conflict", async () => {
    const user = userEvent.setup();
    let conflictReceived = false;
    server.use(
      http.get("/api/entries", () =>
        HttpResponse.json({
          ...emptyDashboard(),
          waiting: conflictReceived
            ? []
            : [makeEntry("waiting-1", "Desk lamp", "waiting")],
          saved: conflictReceived
            ? [makeEntry("waiting-1", "Desk lamp", "saved")]
            : [],
        }),
      ),
      http.delete("/api/entries/waiting-1", () => {
        conflictReceived = true;
        return HttpResponse.json(
          {
            error: {
              code: "invalid_entry_status",
              message: "Only waiting entries may be deleted.",
            },
          },
          { status: 409 },
        );
      }),
    );
    renderWithApp(<DashboardPage />, { initialEntry: "/dashboard" });

    await user.click(await screen.findByRole("button", { name: "Delete" }));
    await user.click(screen.getByRole("button", { name: "Delete entry" }));

    expect(
      await screen.findByText(
        "Desk lamp is no longer waiting and was not deleted.",
      ),
    ).toHaveAttribute("role", "status");
    expect(await screen.findByText("Saved on")).toBeVisible();
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });
});

function useDashboardResponse(response: DashboardEntries) {
  server.use(http.get("/api/entries", () => HttpResponse.json(response)));
}

function emptyDashboard(): DashboardEntries {
  return {
    needs_check_in: [],
    waiting: [],
    saved: [],
    purchased: [],
  };
}

function makeEntry(
  id: string,
  itemName: string,
  bucket: DashboardBucket,
): Entry {
  const resolved = bucket === "saved" || bucket === "purchased";

  return {
    id,
    item_name: itemName,
    price_cents: 8_999,
    reason_wanted: "It looks useful.",
    status: resolved ? bucket : "waiting",
    dashboard_bucket: bucket,
    comment: resolved ? "Decision complete." : null,
    created_at: "2026-07-28T14:30:00Z",
    eligible_for_check_in_at: "2026-07-30T14:30:00Z",
    checked_in_at: resolved ? "2026-07-30T15:00:00Z" : null,
    updated_at: "2026-07-30T15:00:00Z",
  };
}
