import { render, screen } from "@testing-library/react";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import type { EntryResponse, EntryStatus } from "../types/api";
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
});

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
