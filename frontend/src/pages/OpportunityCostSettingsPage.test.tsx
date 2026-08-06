import { act, screen } from "@testing-library/react";
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
      { name: "Try again" },
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
});
