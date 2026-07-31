import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { renderWithApp } from "../../test/render";
import { EntryForm } from "./EntryForm";

describe("EntryForm", () => {
  it("submits trimmed create fields with exact integer cents", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<EntryForm mode="create" onSubmit={submit} />);

    await user.type(screen.getByLabelText("Item name"), "  Coffee grinder  ");
    await user.type(screen.getByLabelText("Price"), "89.99");
    await user.type(
      screen.getByLabelText("Reason wanted"),
      "  Better coffee at home  ",
    );
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        item_name: "Coffee grinder",
        price_cents: 8_999,
        reason_wanted: "Better coffee at home",
      }),
    );
  });

  it("uses shared fields and initial values in edit mode", () => {
    renderWithApp(
      <EntryForm
        mode="edit"
        initialValues={{
          item_name: "Coffee grinder",
          price: "89.99",
          reason_wanted: "Better coffee at home",
        }}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Item name")).toHaveValue("Coffee grinder");
    expect(screen.getByLabelText("Price")).toHaveValue("89.99");
    expect(screen.getByLabelText("Price")).toHaveAttribute(
      "inputmode",
      "decimal",
    );
    expect(screen.getByLabelText("Reason wanted")).toHaveValue(
      "Better coffee at home",
    );
    expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  });

  it("shows accessible client errors without submitting", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<EntryForm mode="create" onSubmit={submit} />);

    await user.type(screen.getByLabelText("Price"), "19.999");
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    const alert = await screen.findByRole("alert");
    const itemName = screen.getByLabelText("Item name");
    const price = screen.getByLabelText("Price");
    const reason = screen.getByLabelText("Reason wanted");
    expect(alert).toHaveFocus();
    expect(itemName).toHaveAttribute("aria-invalid", "true");
    expect(price).toHaveAttribute("aria-invalid", "true");
    expect(reason).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter an item name.")).toHaveAttribute(
      "id",
      itemName.getAttribute("aria-describedby"),
    );
    expect(
      screen.getByText(
        "Enter a price in dollars with no more than two decimal places.",
      ),
    ).toHaveAttribute("id", price.getAttribute("aria-describedby"));
    expect(screen.getByText("Enter a reason for wanting it.")).toHaveAttribute(
      "id",
      reason.getAttribute("aria-describedby"),
    );
    expect(submit).not.toHaveBeenCalled();
  });

  it("maps backend cents errors to the visible price field", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockRejectedValue(
      new ApiError(422, "validation_error", "Invalid entry.", {
        price_cents: "That price is not allowed.",
      }),
    );
    renderWithApp(<EntryForm mode="create" onSubmit={submit} />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Add entry" }));

    const price = screen.getByLabelText("Price");
    expect(
      await screen.findByText("That price is not allowed."),
    ).toHaveAttribute("id", price.getAttribute("aria-describedby"));
    expect(price).toHaveValue("89.99");
    expect(screen.getByRole("alert")).toHaveFocus();
  });

  it("preserves input and shows a form error after a server failure", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValue(
        new ApiError(503, "unavailable", "The service is unavailable."),
      );
    renderWithApp(<EntryForm mode="edit" onSubmit={submit} />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The service is unavailable.",
    );
    expect(screen.getByLabelText("Item name")).toHaveValue("Coffee grinder");
    expect(screen.getByLabelText("Price")).toHaveValue("89.99");
  });

  it("prevents duplicate submissions while saving", async () => {
    const user = userEvent.setup();
    let finishSubmission: (() => void) | undefined;
    const submit = vi.fn(
      () =>
        new Promise<void>((resolve) => {
          finishSubmission = resolve;
        }),
    );
    renderWithApp(<EntryForm mode="create" onSubmit={submit} />);

    await fillValidForm(user);
    await user.dblClick(screen.getByRole("button", { name: "Add entry" }));

    expect(
      screen.getByRole("button", { name: "Adding entry…" }),
    ).toBeDisabled();
    expect(submit).toHaveBeenCalledOnce();
    finishSubmission?.();
  });
});

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Item name"), "Coffee grinder");
  await user.type(screen.getByLabelText("Price"), "89.99");
  await user.type(
    screen.getByLabelText("Reason wanted"),
    "Better coffee at home",
  );
}
