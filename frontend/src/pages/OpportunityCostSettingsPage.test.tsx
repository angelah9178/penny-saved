import { act, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { queryKeys } from "../lib/queryKeys";
import { renderWithApp } from "../test/render";
import { server } from "../test/server";
import { OpportunityCostSettingsPage } from "./OpportunityCostSettingsPage";

describe("OpportunityCostSettingsPage", () => {
  it("shows the separate management page and its empty explanation", async () => {
    renderWithApp(<OpportunityCostSettingsPage />, {
      initialEntry: "/settings/opportunity-costs",
    });

    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Opportunity-cost examples",
      }),
    ).toBeVisible();
    expect(
      screen.getByRole("link", { name: "Return to dashboard" }),
    ).toHaveAttribute("href", "/dashboard");
    expect(
      screen.getByRole("button", { name: "Create example" }),
    ).toBeVisible();
    expect(
      await screen.findByRole("heading", {
        name: "No opportunity-cost examples yet",
      }),
    ).toBeVisible();
    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("shows loading without claiming the list is empty", () => {
    server.use(
      http.get("/api/opportunity-cost-examples", async () => {
        await delay("infinite");
        return HttpResponse.json({ examples: [] });
      }),
    );

    renderWithApp(<OpportunityCostSettingsPage />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading your opportunity-cost examples…",
    );
    expect(
      screen.queryByText("No opportunity-cost examples yet"),
    ).not.toBeInTheDocument();
  });

  it("shows a recoverable error without presenting a failed request as empty", async () => {
    const user = userEvent.setup();
    let requestCount = 0;
    server.use(
      http.get("/api/opportunity-cost-examples", () => {
        requestCount += 1;
        return requestCount <= 3
          ? HttpResponse.json(
              { error: { code: "unavailable", message: "Unavailable." } },
              { status: 503 },
            )
          : HttpResponse.json({ examples: [] });
      }),
    );

    renderWithApp(<OpportunityCostSettingsPage />);

    const retry = await screen.findByRole(
      "button",
      { name: "Retry examples" },
      { timeout: 4_000 },
    );
    expect(screen.queryByText("No opportunity-cost examples yet")).toBeNull();
    await user.click(retry);
    expect(
      await screen.findByText("No opportunity-cost examples yet"),
    ).toBeVisible();
    expect(requestCount).toBe(4);
  });

  it("keeps the list visible while it refreshes", async () => {
    server.use(
      http.get("/api/opportunity-cost-examples", () =>
        HttpResponse.json({
          examples: [
            {
              id: "example-id",
              label: "Hours worked",
              unit_name: "hours",
              dollar_value_cents: 1_000,
              created_at: "2026-08-06T12:00:00Z",
              updated_at: "2026-08-06T12:00:00Z",
            },
          ],
        }),
      ),
    );
    const { queryClient } = renderWithApp(<OpportunityCostSettingsPage />);
    const value = await screen.findByText("$10.00");
    expect(value.closest("p")).toHaveTextContent("$10.00 per hours");

    server.use(
      http.get("/api/opportunity-cost-examples", async () => {
        await delay("infinite");
        return HttpResponse.json({ examples: [] });
      }),
    );
    act(() => {
      void queryClient.invalidateQueries({
        queryKey: queryKeys.opportunityCosts.list(),
      });
    });

    expect(await screen.findByText("Updating examples…")).toHaveAttribute(
      "role",
      "status",
    );
    expect(screen.getByText("$10.00").closest("p")).toHaveTextContent(
      "$10.00 per hours",
    );
  });

  it("creates an example with the exact POST payload and shows server-confirmed data", async () => {
    const user = userEvent.setup();
    const created = makeExample("created-id", "Hours worked", "hours", 1_000);
    let examples: ReturnType<typeof makeExample>[] = [];
    server.use(
      http.get("/api/opportunity-cost-examples", () =>
        HttpResponse.json({ examples }),
      ),
      http.post("/api/opportunity-cost-examples", async ({ request }) => {
        expect(await request.json()).toEqual({
          label: "Hours worked",
          unit_name: "hours",
          dollar_value_cents: 1_000,
        });
        examples = [created];
        return HttpResponse.json({ example: created }, { status: 201 });
      }),
    );
    renderWithApp(<OpportunityCostSettingsPage />);

    await user.click(
      await screen.findByRole("button", { name: "Create example" }),
    );
    await user.type(screen.getByLabelText("Label"), "  Hours worked  ");
    await user.type(screen.getByLabelText("Unit name"), "  hours  ");
    await user.type(screen.getByLabelText("Dollar value"), "10.00");
    await user.click(screen.getByRole("button", { name: "Create example" }));

    expect(
      await screen.findByText("Opportunity-cost example created."),
    ).toHaveAttribute("role", "status");
    expect(
      await screen.findByRole("heading", { name: "Hours worked" }),
    ).toBeVisible();
    expect(screen.queryByLabelText("Dollar value")).toBeNull();
  });

  it("prefills and edits the selected stable ID through PATCH", async () => {
    const user = userEvent.setup();
    let example = makeExample("edit-id", "Hours worked", "hours", 1_000);
    server.use(
      http.get("/api/opportunity-cost-examples", () =>
        HttpResponse.json({ examples: [example] }),
      ),
      http.patch(
        "/api/opportunity-cost-examples/edit-id",
        async ({ request }) => {
          expect(await request.json()).toEqual({
            label: "Coffee made at home",
            unit_name: "cups",
            dollar_value_cents: 450,
          });
          example = makeExample("edit-id", "Coffee made at home", "cups", 450);
          return HttpResponse.json({ example });
        },
      ),
    );
    renderWithApp(<OpportunityCostSettingsPage />);

    await user.click(
      await screen.findByRole("button", { name: "Edit Hours worked" }),
    );
    expect(screen.getByLabelText("Dollar value")).toHaveValue("10.00");
    await user.clear(screen.getByLabelText("Label"));
    await user.type(screen.getByLabelText("Label"), "Coffee made at home");
    await user.clear(screen.getByLabelText("Unit name"));
    await user.type(screen.getByLabelText("Unit name"), "cups");
    await user.clear(screen.getByLabelText("Dollar value"));
    await user.type(screen.getByLabelText("Dollar value"), "4.50");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText("Opportunity-cost example updated."),
    ).toHaveAttribute("role", "status");
    expect(
      await screen.findByRole("heading", { name: "Coffee made at home" }),
    ).toBeVisible();
  });

  it("refreshes server truth and closes a stale edit safely", async () => {
    const user = userEvent.setup();
    let listRequests = 0;
    server.use(
      http.get("/api/opportunity-cost-examples", () => {
        listRequests += 1;
        return HttpResponse.json({
          examples:
            listRequests === 1
              ? [makeExample("stale-id", "Old example", "units", 100)]
              : [],
        });
      }),
      http.patch("/api/opportunity-cost-examples/stale-id", () =>
        HttpResponse.json(
          { error: { code: "not_found", message: "Private detail." } },
          { status: 404 },
        ),
      ),
    );
    renderWithApp(<OpportunityCostSettingsPage />);

    await user.click(
      await screen.findByRole("button", { name: "Edit Old example" }),
    );
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(
      await screen.findByText(
        "That example is no longer available. The list has been refreshed.",
      ),
    ).toHaveAttribute("role", "status");
    await waitFor(() => expect(listRequests).toBeGreaterThanOrEqual(2));
    expect(screen.queryByText("Private detail.")).toBeNull();
    expect(screen.queryByLabelText("Dollar value")).toBeNull();
  });

  it("removes an example only after a confirmed 204 and refreshes the list", async () => {
    const user = userEvent.setup();
    let examples = [makeExample("delete-id", "Hours worked", "hours", 1_000)];
    server.use(
      http.get("/api/opportunity-cost-examples", () =>
        HttpResponse.json({ examples }),
      ),
      http.delete("/api/opportunity-cost-examples/delete-id", () => {
        examples = [];
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithApp(<OpportunityCostSettingsPage />);

    await user.click(
      await screen.findByRole("button", { name: "Delete Hours worked" }),
    );
    expect(screen.getByRole("heading", { name: "Hours worked" })).toBeVisible();
    await user.click(screen.getByRole("button", { name: "Delete example" }));

    const deletionNotice = await screen.findByText("Hours worked was deleted.");
    expect(deletionNotice).toHaveAttribute("role", "status");
    expect(deletionNotice).toHaveFocus();
    expect(
      await screen.findByText("No opportunity-cost examples yet"),
    ).toBeVisible();
    expect(screen.queryByRole("heading", { name: "Hours worked" })).toBeNull();
  });
});

function makeExample(
  id: string,
  label: string,
  unit_name: string,
  dollar_value_cents: number,
) {
  return {
    id,
    label,
    unit_name,
    dollar_value_cents,
    created_at: "2026-08-06T12:00:00Z",
    updated_at: "2026-08-06T12:00:00Z",
  };
}
