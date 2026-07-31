import { render, screen, within } from "@testing-library/react";
import { QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "../../app/queryClient";
import type { Entry } from "../../types/api";
import { EntrySection } from "./EntrySection";

describe("EntrySection", () => {
  it("renders a semantic list in the order supplied by the backend", () => {
    renderSection([
      makeEntry("entry-2", "Backend first"),
      makeEntry("entry-1", "Backend second"),
    ]);

    const list = screen.getByRole("list");
    const items = within(list).getAllByRole("listitem");

    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("Backend first");
    expect(items[1]).toHaveTextContent("Backend second");
    expect(screen.getByLabelText("2 entries")).toBeVisible();
  });

  it("shows the section-specific empty message without an empty list", () => {
    renderSection([]);

    expect(
      screen.getByRole("heading", { level: 2, name: /Waiting/ }),
    ).toBeVisible();
    expect(screen.getByText("Nothing is currently waiting.")).toBeVisible();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders long user text as text content", () => {
    const longName = "A very useful item ".repeat(20);
    const longReason = "This is why I want it. ".repeat(40);
    renderSection([
      makeEntry("long-entry", longName, { reason_wanted: longReason }),
    ]);

    expect(screen.getByRole("heading", { level: 3 })).toHaveTextContent(
      longName.trim(),
    );
    expect(document.body).toHaveTextContent(longReason.trim());
  });
});

function renderSection(entries: Entry[]) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter>
        <EntrySection
          title="Waiting"
          emptyMessage="Nothing is currently waiting."
          entries={entries}
          section="waiting"
        />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeEntry(
  id: string,
  itemName: string,
  overrides: Partial<Entry> = {},
): Entry {
  return {
    id,
    item_name: itemName,
    price_cents: 1_299,
    reason_wanted: "It looks useful.",
    status: "waiting",
    dashboard_bucket: "waiting",
    comment: null,
    created_at: "2026-07-28T14:30:00Z",
    eligible_for_check_in_at: "2026-07-30T14:30:00Z",
    checked_in_at: null,
    updated_at: "2026-07-28T14:30:00Z",
    ...overrides,
  };
}
