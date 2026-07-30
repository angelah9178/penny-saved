import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DateTime } from "./DateTime";

describe("DateTime", () => {
  it("preserves the API timestamp in semantic time markup", () => {
    const value = "2026-07-30T14:30:00Z";
    const { container } = render(<DateTime value={value} />);
    const time = container.querySelector("time");

    expect(time).not.toBeNull();
    expect(time).toHaveAttribute("datetime", value);
    expect(time).toHaveTextContent("2026");
  });

  it("shows a safe fallback without invalid time markup", () => {
    const { container } = render(
      <DateTime value="invalid" fallback="Time unavailable" />,
    );

    expect(screen.getByText("Time unavailable")).toBeVisible();
    expect(container.querySelector("time")).toBeNull();
  });
});
