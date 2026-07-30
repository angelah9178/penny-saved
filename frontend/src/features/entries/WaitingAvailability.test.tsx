import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { WaitingAvailability } from "./WaitingAvailability";

describe("WaitingAvailability", () => {
  it("describes when check-in becomes available without changing entry state", () => {
    const { container } = render(
      <WaitingAvailability eligibleForCheckInAt="2026-07-30T14:30:00Z" />,
    );

    expect(screen.getByText(/Check-in available/)).toBeVisible();
    expect(container.querySelector("time")).toHaveAttribute(
      "datetime",
      "2026-07-30T14:30:00Z",
    );
  });

  it("gives a safe message when the API timestamp is invalid", () => {
    render(<WaitingAvailability eligibleForCheckInAt="invalid" />);

    expect(document.body).toHaveTextContent(
      "Check-in available when the waiting period ends",
    );
  });
});
