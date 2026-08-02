import { render, screen } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "../../app/queryClient";
import type { DashboardBucket, Entry } from "../../types/api";
import { EntryCard } from "./EntryCard";

describe("EntryCard", () => {
  it.each([
    ["needs_check_in", "The waiting period is complete."],
    ["waiting", "Check-in available"],
    ["saved", "Saved on"],
    ["purchased", "Purchased on"],
  ] satisfies [DashboardBucket, string][])(
    "renders the %s section presentation",
    (section, statusText) => {
      renderCard(section);

      expect(
        screen.getByRole("heading", { level: 3, name: "Wireless headphones" }),
      ).toBeVisible();
      expect(screen.getByText("$89.99")).toBeVisible();
      expect(screen.getByText(/Useful while commuting/)).toBeVisible();
      expect(screen.getByText(new RegExp(statusText))).toBeVisible();
      expect(screen.getByText(sectionLabel(section))).toBeVisible();
    },
  );

  it("shows check-in navigation only when the caller places it in Needs check-in", () => {
    const { rerender } = renderCard("needs_check_in");

    expect(screen.getByRole("link", { name: "Check in" })).toHaveAttribute(
      "href",
      "/entries/entry-1/check-in",
    );

    rerender(cardInRouter("waiting"));
    expect(
      screen.queryByRole("link", { name: "Check in" }),
    ).not.toBeInTheDocument();
  });

  it.each(["needs_check_in", "waiting"] satisfies DashboardBucket[])(
    "shows edit navigation for a %s entry",
    (section) => {
      renderCard(section);

      expect(screen.getByRole("link", { name: "Edit" })).toHaveAttribute(
        "href",
        "/entries/entry-1/edit",
      );
    },
  );

  it.each(["saved", "purchased"] satisfies DashboardBucket[])(
    "shows comment editing but not core editing or deletion for a %s entry",
    (section) => {
      renderCard(section);

      expect(
        screen.getByRole("link", { name: "Edit comment" }),
      ).toHaveAttribute("href", "/entries/entry-1");
      expect(
        screen.queryByRole("link", { name: "Edit" }),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByRole("button", { name: "Delete" }),
      ).not.toBeInTheDocument();
    },
  );

  it.each(["needs_check_in", "waiting"] satisfies DashboardBucket[])(
    "shows safe deletion access for a %s entry",
    (section) => {
      renderCard(section);

      expect(screen.getByRole("button", { name: "Delete" })).toBeEnabled();
    },
  );

  it("makes entry actions keyboard reachable", async () => {
    const user = userEvent.setup();
    renderCard("needs_check_in");

    await user.tab();

    expect(screen.getByRole("link", { name: "Check in" })).toHaveFocus();
    await user.tab();
    expect(screen.getByRole("link", { name: "Edit" })).toHaveFocus();
  });

  it("does not create a check-in action from a past browser timestamp", () => {
    renderCard("waiting", {
      eligible_for_check_in_at: "2000-01-01T00:00:00Z",
    });

    expect(screen.getByText(/Check-in available/)).toBeVisible();
    expect(
      screen.queryByRole("link", { name: "Check in" }),
    ).not.toBeInTheDocument();
  });

  it.each(["saved", "purchased"] satisfies DashboardBucket[])(
    "shows an API comment for a %s entry",
    (section) => {
      renderCard(section);

      expect(screen.getByText(/I waited and made a decision/)).toBeVisible();
    },
  );

  it("does not show blank or waiting comments", () => {
    const { rerender } = renderCard("waiting");
    expect(screen.queryByText(/Comment:/)).not.toBeInTheDocument();

    rerender(cardInRouter("saved", { comment: "   " }));
    expect(screen.queryByText(/Comment:/)).not.toBeInTheDocument();
  });
});

function renderCard(section: DashboardBucket, overrides: Partial<Entry> = {}) {
  return render(cardInRouter(section, overrides));
}

function sectionLabel(section: DashboardBucket): string {
  switch (section) {
    case "needs_check_in":
      return "Needs check-in";
    case "waiting":
      return "Waiting";
    case "saved":
      return "Saved";
    case "purchased":
      return "Purchased";
  }
}

function cardInRouter(
  section: DashboardBucket,
  overrides: Partial<Entry> = {},
) {
  return (
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <EntryCard entry={makeEntry(overrides)} section={section} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function makeEntry(overrides: Partial<Entry> = {}): Entry {
  return {
    id: "entry-1",
    item_name: "Wireless headphones",
    price_cents: 8_999,
    reason_wanted: "Useful while commuting",
    status: "waiting",
    dashboard_bucket: "waiting",
    comment: "I waited and made a decision.",
    created_at: "2026-07-28T14:30:00Z",
    eligible_for_check_in_at: "2026-07-30T14:30:00Z",
    checked_in_at: "2026-07-30T15:00:00Z",
    updated_at: "2026-07-30T15:00:00Z",
    ...overrides,
  };
}
