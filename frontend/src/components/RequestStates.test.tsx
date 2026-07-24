import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";
import { ErrorAlert } from "./ErrorAlert";
import { Loading } from "./Loading";

describe("Loading", () => {
  it("shows an accessible default loading status", () => {
    render(<Loading />);

    const status = screen.getByRole("status");

    expect(status).toHaveTextContent("Loading…");
    expect(status).toHaveAttribute("aria-live", "polite");
  });

  it("shows a specific loading message", () => {
    render(<Loading message="Loading your entries…" />);

    expect(screen.getByRole("status")).toHaveTextContent(
      "Loading your entries…",
    );
  });
});

describe("ErrorAlert", () => {
  it("shows an accessible error without inventing a retry action", () => {
    render(<ErrorAlert message="Your entries could not be loaded." />);

    expect(screen.getByRole("alert")).toHaveTextContent(
      "Your entries could not be loaded.",
    );
    expect(
      screen.queryByRole("button", { name: "Try again" }),
    ).not.toBeInTheDocument();
  });

  it("allows the user to retry when a retry action is provided", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();
    render(
      <ErrorAlert
        message="Your entries could not be loaded."
        onRetry={onRetry}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(onRetry).toHaveBeenCalledOnce();
  });
});

describe("EmptyState", () => {
  it("labels the empty section with its visible heading", () => {
    render(
      <EmptyState
        title="No saved entries"
        message="Entries you avoid purchasing will appear here."
      />,
    );

    const heading = screen.getByRole("heading", { name: "No saved entries" });
    const section = screen.getByRole("region", { name: "No saved entries" });

    expect(section).toContainElement(heading);
    expect(section).toHaveTextContent(
      "Entries you avoid purchasing will appear here.",
    );
  });
});
