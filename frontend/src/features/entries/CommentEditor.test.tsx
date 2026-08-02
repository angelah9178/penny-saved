import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { renderWithApp } from "../../test/render";
import type { EntryResponse } from "../../types/api";
import { CommentEditor } from "./CommentEditor";
import { MAX_ENTRY_COMMENT_LENGTH } from "./commentFormValidation";

const response = (comment: string | null): EntryResponse => ({
  entry: {
    id: "entry-1",
    item_name: "Headphones",
    price_cents: 8_999,
    reason_wanted: "Commuting",
    status: "saved",
    dashboard_bucket: "saved",
    comment,
    created_at: "2026-07-28T14:00:00Z",
    eligible_for_check_in_at: "2026-07-30T14:00:00Z",
    checked_in_at: "2026-07-30T15:00:00Z",
    updated_at: "2026-08-01T15:00:00Z",
  },
});

describe("CommentEditor", () => {
  it("prefills, trims, submits, and confirms a server-normalized comment", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(response("Borrowed one instead."));
    renderWithApp(
      <CommentEditor comment="Original reflection" onSubmit={submit} />,
    );

    const comment = screen.getByLabelText("Comment");
    expect(comment).toHaveValue("Original reflection");
    await user.clear(comment);
    await user.type(comment, "  Borrowed one instead.  ");
    await user.click(screen.getByRole("button", { name: "Save comment" }));

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({ comment: "Borrowed one instead." }),
    );
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Comment saved.",
    );
    expect(screen.getByRole("status")).toHaveFocus();
    expect(comment).toHaveValue("Borrowed one instead.");
  });

  it("shows null as blank and submits whitespace as a clear operation", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockResolvedValue(response(null));
    renderWithApp(<CommentEditor comment="Remove this" onSubmit={submit} />);

    const comment = screen.getByLabelText("Comment");
    expect(comment).toHaveValue("Remove this");
    await user.clear(comment);
    await user.type(comment, "   ");
    await user.click(screen.getByRole("button", { name: "Save comment" }));

    await waitFor(() => expect(submit).toHaveBeenCalledWith({ comment: null }));
    expect(await screen.findByRole("status")).toHaveTextContent(
      "Comment cleared.",
    );
  });

  it("does not send an unchanged normalized comment", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<CommentEditor comment="Same comment" onSubmit={submit} />);

    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "There are no comment changes to save.",
    );
    expect(submit).not.toHaveBeenCalled();
  });

  it("preserves and reports an oversized Unicode comment", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<CommentEditor comment={null} onSubmit={submit} />);
    const comment = screen.getByLabelText("Comment");
    const oversized = "🪙".repeat(MAX_ENTRY_COMMENT_LENGTH + 1);

    await user.click(comment);
    await user.paste(oversized);
    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(
      await screen.findByText("Comment must be 4,000 characters or fewer."),
    ).toBeVisible();
    expect(comment).toHaveValue(oversized);
    expect(screen.getByRole("alert")).toHaveFocus();
    expect(submit).not.toHaveBeenCalled();
  });

  it("disables the editor and prevents duplicate pending submissions", async () => {
    const user = userEvent.setup();
    let finish: ((value: EntryResponse) => void) | undefined;
    const submit = vi.fn(
      () =>
        new Promise<EntryResponse>((resolve) => {
          finish = resolve;
        }),
    );
    renderWithApp(<CommentEditor comment="Original" onSubmit={submit} />);
    const comment = screen.getByLabelText("Comment");
    await user.clear(comment);
    await user.type(comment, "Updated");

    await user.dblClick(screen.getByRole("button", { name: "Save comment" }));

    expect(submit).toHaveBeenCalledOnce();
    expect(
      screen.getByRole("button", { name: "Saving comment…" }),
    ).toBeDisabled();
    expect(comment).toBeDisabled();
    finish?.(response("Updated"));
  });

  it("preserves edited text after a retryable failure and allows retry", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValueOnce(
        new ApiError(503, "service_unavailable", "Internal database details"),
      )
      .mockResolvedValueOnce(response("Updated after retry"));
    renderWithApp(<CommentEditor comment="Original" onSubmit={submit} />);
    const comment = screen.getByLabelText("Comment");
    await user.clear(comment);
    await user.type(comment, "Updated after retry");

    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save the comment. Please try again.",
    );
    expect(
      screen.queryByText(/Internal database details/),
    ).not.toBeInTheDocument();
    expect(comment).toHaveValue("Updated after retry");

    await user.click(screen.getByRole("button", { name: "Save comment" }));

    expect(await screen.findByRole("status")).toHaveTextContent(
      "Comment saved.",
    );
    expect(submit).toHaveBeenCalledTimes(2);
  });
});
