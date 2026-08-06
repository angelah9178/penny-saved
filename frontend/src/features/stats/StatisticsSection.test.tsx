import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { renderWithApp } from "../../test/render";
import { server } from "../../test/server";
import type { StatsRange, StatsSummary } from "../../types/api";
import { StatisticsSection } from "./StatisticsSection";

const summary: StatsSummary = {
  range: "this_month",
  total_saved_cents: 25_000,
  avoided_purchase_count: 4,
  purchased_count: 1,
  opportunity_costs: [
    {
      example_id: "63000000-0000-4000-8000-000000000001",
      label: "hours worked",
      unit_name: "hours",
      dollar_value_cents: 1_000,
      equivalent_units: 25,
    },
    {
      example_id: "63000000-0000-4000-8000-000000000002",
      label: "meals",
      unit_name: "meals",
      dollar_value_cents: 3_000,
      equivalent_units: 8.3,
    },
    {
      example_id: "63000000-0000-4000-8000-000000000003",
      label: "hours worked",
      unit_name: "hours",
      dollar_value_cents: 2_000,
      equivalent_units: 12.5,
    },
  ],
};

describe("StatisticsSection", () => {
  it("shows the server totals and whole and fractional equivalents in order", async () => {
    useStatsResponse(() => summary);

    renderWithApp(<StatisticsSection />, {
      initialEntry: "/dashboard?range=this_month",
    });

    expect(await screen.findByText("$250.00")).toBeVisible();
    expect(statisticValue("Purchases avoided")).toHaveTextContent("4");
    expect(statisticValue("Items purchased")).toHaveTextContent("1");
    const list = screen.getByRole("list");
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(3);
    expect(items[0]).toHaveTextContent("25 hours");
    expect(items[0]).toHaveTextContent("hours worked at $10.00 each");
    expect(items[1]).toHaveTextContent("8.3 meals");
    expect(items[2]).toHaveTextContent("12.5 hours");
  });

  it("updates the URL and requests the range selected by the user", async () => {
    const user = userEvent.setup();
    const requestedRanges: string[] = [];
    useStatsResponse((range) => {
      requestedRanges.push(range);
      return { ...summary, range };
    });
    const { router } = renderWithApp(<StatisticsSection />, {
      initialEntry: "/dashboard?range=this_month",
    });
    const select = await screen.findByRole("combobox", { name: "Time range" });

    await user.selectOptions(select, "last_3_months");

    await waitFor(() => expect(requestedRanges).toContain("last_3_months"));
    expect(router.state.location.search).toBe("?range=last_3_months");
    expect(select).toHaveValue("last_3_months");
  });

  it("falls back to this month without sending an invalid URL range", async () => {
    const requestedRanges: string[] = [];
    useStatsResponse((range) => {
      requestedRanges.push(range);
      return { ...summary, range };
    });

    renderWithApp(<StatisticsSection />, {
      initialEntry: "/dashboard?range=not_supported",
    });

    expect(await screen.findByText("$250.00")).toBeVisible();
    expect(requestedRanges).toEqual(["this_month"]);
    expect(screen.getByRole("combobox", { name: "Time range" })).toHaveValue(
      "this_month",
    );
  });

  it("restores the selected range through browser back navigation", async () => {
    const user = userEvent.setup();
    useStatsResponse((range) => ({ ...summary, range }));
    const { router } = renderWithApp(<StatisticsSection />, {
      initialEntry: "/dashboard?range=this_month",
    });
    const select = await screen.findByRole("combobox", { name: "Time range" });

    await user.selectOptions(select, "all_time");
    await waitFor(() => expect(select).toHaveValue("all_time"));
    await router.navigate(-1);

    await waitFor(() => expect(select).toHaveValue("this_month"));
  });

  it("shows honest zero values and the no-examples explanation", async () => {
    useStatsResponse(() => ({
      ...summary,
      total_saved_cents: 0,
      avoided_purchase_count: 0,
      purchased_count: 0,
      opportunity_costs: [],
    }));

    renderWithApp(<StatisticsSection />, { initialEntry: "/dashboard" });

    expect(await screen.findByText("$0.00")).toBeVisible();
    expect(statisticValue("Purchases avoided")).toHaveTextContent("0");
    expect(statisticValue("Items purchased")).toHaveTextContent("0");
    expect(
      screen.getByText(
        "Add opportunity-cost examples to see your savings in everyday terms.",
      ),
    ).toBeVisible();
  });

  it("formats large server totals and counts without recalculating equivalents", async () => {
    useStatsResponse(() => ({
      ...summary,
      total_saved_cents: 9_999_999_999,
      avoided_purchase_count: 12_345,
      purchased_count: 6_789,
      opportunity_costs: [
        {
          ...summary.opportunity_costs[0]!,
          equivalent_units: 9_876_543.2,
        },
      ],
    }));

    renderWithApp(<StatisticsSection />, { initialEntry: "/dashboard" });

    expect(await screen.findByText("$99,999,999.99")).toBeVisible();
    expect(statisticValue("Purchases avoided")).toHaveTextContent("12,345");
    expect(statisticValue("Items purchased")).toHaveTextContent("6,789");
    expect(screen.getByText(/9,876,543\.2 hours/)).toBeVisible();
  });
});

function statisticValue(label: string): HTMLElement {
  const term = screen.getByText(label);
  const card = term.closest("div");
  if (card === null) {
    throw new Error(`Expected a statistics card for ${label}.`);
  }
  return within(card).getByRole("definition");
}

function useStatsResponse(buildResponse: (range: StatsRange) => StatsSummary) {
  server.use(
    http.get("/api/stats/summary", ({ request }) => {
      const range = new URL(request.url).searchParams.get(
        "range",
      ) as StatsRange;
      return HttpResponse.json(buildResponse(range));
    }),
  );
}
