import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { queryKeys } from "../../lib/queryKeys";
import { OpportunityCostSettingsPage } from "../../pages/OpportunityCostSettingsPage";
import { renderWithApp } from "../../test/render";
import { server } from "../../test/server";
import type {
  OpportunityCostExample,
  StatsRange,
  StatsSummary,
} from "../../types/api";

const statsRanges: StatsRange[] = [
  "this_month",
  "last_3_months",
  "last_6_months",
  "last_year",
  "all_time",
];

describe("opportunity-cost settings journey", () => {
  it("creates, preserves order and duplicate labels, edits, and deletes while refreshing every cache", async () => {
    const user = userEvent.setup();
    let nextId = 3;
    let examples = [
      makeExample("example-1", "Coffee", "cups", 500),
      makeExample("example-2", "Coffee", "bags", 1_500),
    ];
    useStatefulOpportunityCostApi(
      () => examples,
      (next) => {
        examples = next;
      },
      () => `example-${nextId++}`,
    );
    const { queryClient } = renderWithApp(<OpportunityCostSettingsPage />, {
      initialEntry: "/settings/opportunity-costs",
    });

    expect(await listHeadings()).toEqual(["Coffee", "Coffee"]);

    seedAllStats(queryClient);
    await user.click(screen.getByRole("button", { name: "Create example" }));
    await user.type(screen.getByLabelText("Label"), "Coffee");
    await user.type(screen.getByLabelText("Unit name"), "drinks");
    await user.type(screen.getByLabelText("Dollar value"), "4.50");
    await user.click(screen.getByRole("button", { name: "Create example" }));
    expect(
      await screen.findByText("Opportunity-cost example created."),
    ).toBeVisible();
    expect(await listHeadings()).toEqual(["Coffee", "Coffee", "Coffee"]);
    expectEveryStatsRangeInvalidated(queryClient);

    seedAllStats(queryClient);
    const list = screen.getByRole("list", {
      name: "Opportunity-cost examples",
    });
    const cards = within(list).getAllByRole("listitem");
    await user.click(
      within(cards[2] as HTMLElement).getByRole("button", {
        name: "Edit Coffee",
      }),
    );
    await user.clear(screen.getByLabelText("Label"));
    await user.type(screen.getByLabelText("Label"), "Tea");
    await user.click(screen.getByRole("button", { name: "Save changes" }));
    expect(
      await screen.findByText("Opportunity-cost example updated."),
    ).toBeVisible();
    expect(await listHeadings()).toEqual(["Coffee", "Coffee", "Tea"]);
    expectEveryStatsRangeInvalidated(queryClient);

    seedAllStats(queryClient);
    await user.click(screen.getByRole("button", { name: "Delete Tea" }));
    await user.click(screen.getByRole("button", { name: "Delete example" }));
    expect(await screen.findByText("Tea was deleted.")).toBeVisible();
    expect(await listHeadings()).toEqual(["Coffee", "Coffee"]);
    expectEveryStatsRangeInvalidated(queryClient);
  });

  it("keeps server-confirmed list data unchanged after a failed edit", async () => {
    const user = userEvent.setup();
    const original = makeExample("example-1", "Hours worked", "hours", 1_000);
    server.use(
      http.get("/api/opportunity-cost-examples", () =>
        HttpResponse.json({ examples: [original] }),
      ),
      http.patch("/api/opportunity-cost-examples/example-1", () =>
        HttpResponse.json(
          {
            error: { code: "unavailable", message: "Private database detail." },
          },
          { status: 503 },
        ),
      ),
    );
    renderWithApp(<OpportunityCostSettingsPage />);

    await user.click(
      await screen.findByRole("button", { name: "Edit Hours worked" }),
    );
    await user.clear(screen.getByLabelText("Label"));
    await user.type(screen.getByLabelText("Label"), "Unconfirmed replacement");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save the example. Please try again.",
    );
    expect(screen.queryByText("Private database detail.")).toBeNull();
    const list = screen.getByRole("list", {
      name: "Opportunity-cost examples",
    });
    expect(
      within(list).getByRole("heading", { name: "Hours worked" }),
    ).toBeVisible();
    expect(within(list).queryByText("Unconfirmed replacement")).toBeNull();
  });
});

function useStatefulOpportunityCostApi(
  getExamples: () => OpportunityCostExample[],
  setExamples: (examples: OpportunityCostExample[]) => void,
  nextId: () => string,
): void {
  server.use(
    http.get("/api/opportunity-cost-examples", () =>
      HttpResponse.json({ examples: getExamples() }),
    ),
    http.post("/api/opportunity-cost-examples", async ({ request }) => {
      const payload = await mutableFields(request);
      const example = makeExample(
        nextId(),
        payload.label,
        payload.unit_name,
        payload.dollar_value_cents,
      );
      setExamples([...getExamples(), example]);
      return HttpResponse.json({ example }, { status: 201 });
    }),
    http.patch(
      "/api/opportunity-cost-examples/:exampleId",
      async ({ params, request }) => {
        const payload = await mutableFields(request);
        const id = String(params.exampleId);
        const current = getExamples().find((example) => example.id === id);
        if (current === undefined) {
          return HttpResponse.json(
            { error: { code: "not_found", message: "Not found." } },
            { status: 404 },
          );
        }
        const updated = {
          ...current,
          ...payload,
          updated_at: "2026-08-07T12:00:00Z",
        };
        setExamples(
          getExamples().map((example) =>
            example.id === id ? updated : example,
          ),
        );
        return HttpResponse.json({ example: updated });
      },
    ),
    http.delete("/api/opportunity-cost-examples/:exampleId", ({ params }) => {
      const id = String(params.exampleId);
      setExamples(getExamples().filter((example) => example.id !== id));
      return new HttpResponse(null, { status: 204 });
    }),
  );
}

async function mutableFields(request: Request) {
  return (await request.json()) as {
    label: string;
    unit_name: string;
    dollar_value_cents: number;
  };
}

async function listHeadings(): Promise<string[]> {
  const list = await screen.findByRole("list", {
    name: "Opportunity-cost examples",
  });
  return within(list)
    .getAllByRole("heading", { level: 2 })
    .map((heading) => heading.textContent ?? "");
}

function seedAllStats(
  queryClient: ReturnType<typeof renderWithApp>["queryClient"],
) {
  for (const range of statsRanges) {
    const summary: StatsSummary = {
      range,
      total_saved_cents: 1_000,
      avoided_purchase_count: 1,
      purchased_count: 0,
      opportunity_costs: [],
    };
    queryClient.setQueryData(queryKeys.stats.summary(range), summary);
  }
}

function expectEveryStatsRangeInvalidated(
  queryClient: ReturnType<typeof renderWithApp>["queryClient"],
) {
  for (const range of statsRanges) {
    expect(
      queryClient.getQueryState(queryKeys.stats.summary(range))?.isInvalidated,
    ).toBe(true);
  }
}

function makeExample(
  id: string,
  label: string,
  unit_name: string,
  dollar_value_cents: number,
): OpportunityCostExample {
  return {
    id,
    label,
    unit_name,
    dollar_value_cents,
    created_at: "2026-08-06T12:00:00Z",
    updated_at: "2026-08-06T12:00:00Z",
  };
}
