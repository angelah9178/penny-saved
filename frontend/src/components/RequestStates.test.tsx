import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { EmptyState } from "./EmptyState";
import { ErrorAlert } from "./ErrorAlert";
import { FeedbackMessage } from "./FeedbackMessage";
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

  it("uses operation-specific labels and disables a pending retry", () => {
    render(
      <ErrorAlert
        isRetrying
        message="Your entries could not be loaded."
        onRetry={vi.fn()}
        retryLabel="Retry entries"
        retryingLabel="Retrying entries…"
      />,
    );

    expect(
      screen.getByRole("button", { name: "Retrying entries…" }),
    ).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Retry entries" })).toBeNull();
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

describe("FeedbackMessage", () => {
  it("uses consistent live-region semantics for success and updating feedback", () => {
    const { rerender } = render(
      <FeedbackMessage message="Entry changes saved." tone="success" />,
    );

    expect(screen.getByRole("status")).toHaveTextContent(
      "Entry changes saved.",
    );
    expect(screen.getByRole("status")).toHaveAttribute("aria-atomic", "true");

    rerender(<FeedbackMessage message="Updating dashboard…" tone="status" />);
    expect(screen.getByRole("status")).toHaveTextContent("Updating dashboard…");
  });

  it("provides a reusable focusable error summary", () => {
    render(
      <FeedbackMessage
        focusable
        message="Please correct the highlighted fields."
        tone="error"
      />,
    );

    const alert = screen.getByRole("alert");
    expect(alert).toHaveAttribute("tabindex", "-1");
    expect(alert).toHaveClass("request-state--error");
  });
});
