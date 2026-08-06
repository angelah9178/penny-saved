import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { OpportunityCostExample } from "../../types/api";
import { OpportunityCostExampleList } from "./OpportunityCostExampleList";

describe("OpportunityCostExampleList", () => {
  it("preserves server order and identifies duplicate labels by stable IDs", () => {
    const examples = [
      makeExample("first-id", "Hours worked", "hours", 1_000),
      makeExample("second-id", "Hours worked", "shifts", 999_999_999_999),
    ];

    render(<OpportunityCostExampleList examples={examples} />);

    const items = screen.getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]).toHaveTextContent("$10.00 per hours");
    expect(items[1]).toHaveTextContent("$9,999,999,999.99 per shifts");
    expect(
      within(items[0] as HTMLElement).getByRole("button", {
        name: "Edit Hours worked",
      }),
    ).toBeVisible();
    expect(
      within(items[1] as HTMLElement).getByRole("button", {
        name: "Delete Hours worked",
      }),
    ).toBeVisible();
  });

  it("renders long labels and units without truncating their accessible text", () => {
    const label = "A very long comparison label ".repeat(8).trim();
    const unit = "especially descriptive units ".repeat(6).trim();

    render(
      <OpportunityCostExampleList
        examples={[makeExample("long-id", label, unit, 1)]}
      />,
    );

    expect(screen.getByRole("heading", { name: label })).toBeVisible();
    expect(screen.getByText("$0.01").closest("p")).toHaveTextContent(
      `$0.01 per ${unit}`,
    );
  });
});

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
