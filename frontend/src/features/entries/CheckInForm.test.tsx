import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { renderWithApp } from "../../test/render";
import { CheckInForm } from "./CheckInForm";
import { MAX_CHECK_IN_COMMENT_LENGTH } from "./checkInFormValidation";

describe("CheckInForm", () => {
  it.each([
    ["I did not buy it", "saved"],
    ["I bought it", "purchased"],
  ] as const)(
    "submits %s as %s with a trimmed comment",
    async (label, result) => {
      const user = userEvent.setup();
      const submit = vi.fn();
      renderWithApp(<CheckInForm onSubmit={submit} />);

      await user.click(screen.getByRole("radio", { name: label }));
      await user.type(
        screen.getByLabelText("Reflection (optional)"),
        "  I made a deliberate decision.  ",
      );
      await user.click(screen.getByRole("button", { name: "Submit check-in" }));

      await waitFor(() =>
        expect(submit).toHaveBeenCalledWith({
          result,
          comment: "I made a deliberate decision.",
        }),
      );
    },
  );

  it("requires an explicit outcome and focuses the error summary", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<CheckInForm onSubmit={submit} />);

    expect(
      screen.getByRole("radio", { name: "I did not buy it" }),
    ).not.toBeChecked();
    expect(
      screen.getByRole("radio", { name: "I bought it" }),
    ).not.toBeChecked();
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    const alert = await screen.findByRole("alert");
    const group = screen.getByRole("group", {
      name: "What happened with this purchase?",
    });
    const error = screen.getByText("Choose what happened with this purchase.");
    expect(alert).toHaveFocus();
    expect(group).toHaveAttribute("aria-invalid", "true");
    expect(error).toHaveAttribute("id", group.getAttribute("aria-describedby"));
    expect(submit).not.toHaveBeenCalled();
  });

  it("normalizes a whitespace-only optional comment to null", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<CheckInForm onSubmit={submit} />);

    await user.click(screen.getByRole("radio", { name: "I did not buy it" }));
    await user.type(screen.getByLabelText("Reflection (optional)"), "   ");
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({ result: "saved", comment: null }),
    );
  });

  it("reports an oversized Unicode comment and preserves it", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<CheckInForm onSubmit={submit} />);
    const comment = screen.getByLabelText("Reflection (optional)");
    const oversized = "☕".repeat(MAX_CHECK_IN_COMMENT_LENGTH + 1);

    await user.click(screen.getByRole("radio", { name: "I bought it" }));
    await user.click(comment);
    await user.paste(oversized);
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    expect(
      await screen.findByText("Comment must be 4,000 characters or fewer."),
    ).toBeVisible();
    expect(comment).toHaveValue(oversized);
    expect(submit).not.toHaveBeenCalled();
  });

  it("supports keyboard selection within the outcome group", async () => {
    const user = userEvent.setup();
    renderWithApp(<CheckInForm onSubmit={vi.fn()} />);
    const saved = screen.getByRole("radio", { name: "I did not buy it" });
    const purchased = screen.getByRole("radio", { name: "I bought it" });

    await user.tab();
    expect(saved).toHaveFocus();
    await user.keyboard(" ");
    expect(saved).toBeChecked();
    await user.keyboard("{ArrowDown}");
    expect(purchased).toBeChecked();
  });

  it("preserves input and maps a backend comment error", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockRejectedValue(
      new ApiError(422, "validation_error", "Invalid check-in.", {
        comment: "That reflection is not allowed.",
      }),
    );
    renderWithApp(<CheckInForm onSubmit={submit} />);

    await user.click(screen.getByRole("radio", { name: "I bought it" }));
    await user.type(
      screen.getByLabelText("Reflection (optional)"),
      "My reflection",
    );
    await user.click(screen.getByRole("button", { name: "Submit check-in" }));

    expect(
      await screen.findByText("That reflection is not allowed."),
    ).toBeVisible();
    expect(screen.getByRole("radio", { name: "I bought it" })).toBeChecked();
    expect(screen.getByLabelText("Reflection (optional)")).toHaveValue(
      "My reflection",
    );
    expect(screen.getByRole("alert")).toHaveFocus();
  });

  it("disables every control and prevents duplicate pending submissions", async () => {
    const user = userEvent.setup();
    let finishSubmission: (() => void) | undefined;
    const submit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishSubmission = resolve;
        }),
    );
    renderWithApp(<CheckInForm onSubmit={submit} />);

    await user.click(screen.getByRole("radio", { name: "I did not buy it" }));
    await user.dblClick(
      screen.getByRole("button", { name: "Submit check-in" }),
    );

    expect(
      screen.getByRole("button", { name: "Submitting check-in…" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("radio", { name: "I did not buy it" }),
    ).toBeDisabled();
    expect(screen.getByLabelText("Reflection (optional)")).toBeDisabled();
    expect(screen.getByRole("status")).toHaveTextContent(
      "Check-in is being submitted.",
    );
    expect(submit).toHaveBeenCalledOnce();
    finishSubmission?.();
  });
});
