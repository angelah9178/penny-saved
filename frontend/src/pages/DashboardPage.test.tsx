import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderWithApp } from "../test/render";
import { server } from "../test/server";
import type { DashboardBucket, DashboardEntries, Entry } from "../types/api";
import { DashboardPage } from "./DashboardPage";

describe("DashboardPage", () => {
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
      screen.getByRole("link", { name: "Add new impulse purchase" }),
    ).toHaveAttribute("href", "/entries/new");
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
});

function useDashboardResponse(response: DashboardEntries) {
  server.use(http.get("/api/entries", () => HttpResponse.json(response)));
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
