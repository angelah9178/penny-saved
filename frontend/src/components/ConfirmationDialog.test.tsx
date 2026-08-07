import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ConfirmationDialog } from "./ConfirmationDialog";

describe("ConfirmationDialog", () => {
  it("moves focus inside, traps Tab, closes on Escape, and restores focus", async () => {
    const user = userEvent.setup();
    const cancel = vi.fn();
    const trigger = document.createElement("button");
    trigger.textContent = "Open dialog";
    document.body.append(trigger);
    trigger.focus();
    const { unmount } = render(
      <ConfirmationDialog
        confirmLabel="Delete entry"
        description="This cannot be undone."
        title="Delete desk lamp?"
        onCancel={cancel}
        onConfirm={vi.fn()}
      />,
    );

    const cancelButton = screen.getByRole("button", { name: "Cancel" });
    const confirmButton = screen.getByRole("button", { name: "Delete entry" });
    expect(cancelButton).toHaveFocus();

    await user.tab({ shift: true });
    expect(confirmButton).toHaveFocus();
    await user.tab();
    expect(cancelButton).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(cancel).toHaveBeenCalledOnce();

    unmount();
    await waitFor(() => expect(trigger).toHaveFocus());
    trigger.remove();
  });

  it("keeps focus in a pending dialog and blocks dismissal and repeats", async () => {
    const user = userEvent.setup();
    const cancel = vi.fn();
    const confirm = vi.fn();
    render(
      <ConfirmationDialog
        confirmLabel="Delete entry"
        description="This cannot be undone."
        isPending
        pendingLabel="Deleting…"
        title="Delete desk lamp?"
        onCancel={cancel}
        onConfirm={confirm}
      />,
    );

    expect(screen.getByRole("button", { name: "Cancel" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Deleting…" })).toBeDisabled();
    await user.keyboard("{Escape}{Tab}{Enter}");

    expect(screen.getByRole("alertdialog")).toHaveFocus();
    expect(cancel).not.toHaveBeenCalled();
    expect(confirm).not.toHaveBeenCalled();
  });

  it("associates its visible title and description with the dialog", () => {
    render(
      <ConfirmationDialog
        confirmLabel="Continue"
        description="Your changes will be discarded."
        title="Leave this page?"
        onCancel={vi.fn()}
        onConfirm={vi.fn()}
      />,
    );

    const dialog = screen.getByRole("alertdialog", {
      name: "Leave this page?",
      description: "Your changes will be discarded.",
    });
    expect(dialog).toBeInTheDocument();
  });
});
