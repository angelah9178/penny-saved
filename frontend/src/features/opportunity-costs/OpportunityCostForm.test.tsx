import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiError } from "../../api/errors";
import { renderWithApp } from "../../test/render";
import { OpportunityCostForm } from "./OpportunityCostForm";
import { formatCentsForOpportunityCostForm } from "./formValidation";

describe("OpportunityCostForm", () => {
  it("submits normalized fields and exact integer cents from the keyboard", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<OpportunityCostForm mode="create" onSubmit={submit} />);

    await user.type(screen.getByLabelText("Label"), "  Hours worked  ");
    await user.type(screen.getByLabelText("Unit name"), "  hours  ");
    await user.type(screen.getByLabelText("Dollar value"), "10.00");
    await user.keyboard("{Enter}");

    await waitFor(() =>
      expect(submit).toHaveBeenCalledWith({
        label: "Hours worked",
        unit_name: "hours",
        dollar_value_cents: 1_000,
      }),
    );
  });

  it("uses server-confirmed values and edit labels in edit mode", () => {
    renderWithApp(
      <OpportunityCostForm
        mode="edit"
        initialValues={{
          label: "Hours worked",
          unit_name: "hours",
          dollar_value: formatCentsForOpportunityCostForm(1_000),
        }}
        onSubmit={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Label")).toHaveValue("Hours worked");
    expect(screen.getByLabelText("Unit name")).toHaveValue("hours");
    expect(screen.getByLabelText("Dollar value")).toHaveValue("10.00");
    expect(screen.getByLabelText("Dollar value")).toHaveAttribute(
      "inputmode",
      "decimal",
    );
    expect(screen.getByRole("button", { name: "Save changes" })).toBeEnabled();
  });

  it("shows associated field errors and focuses the error summary", async () => {
    const user = userEvent.setup();
    const submit = vi.fn();
    renderWithApp(<OpportunityCostForm mode="create" onSubmit={submit} />);

    await user.type(screen.getByLabelText("Dollar value"), "1,000.00");
    await user.click(screen.getByRole("button", { name: "Create example" }));

    const alert = await screen.findByRole("alert");
    const label = screen.getByLabelText("Label");
    const unit = screen.getByLabelText("Unit name");
    const value = screen.getByLabelText("Dollar value");
    expect(alert).toHaveFocus();
    expect(label).toHaveAttribute("aria-invalid", "true");
    expect(unit).toHaveAttribute("aria-invalid", "true");
    expect(value).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Enter a label.")).toHaveAttribute(
      "id",
      label.getAttribute("aria-describedby"),
    );
    expect(screen.getByText("Enter a unit name.")).toHaveAttribute(
      "id",
      unit.getAttribute("aria-describedby"),
    );
    const valueError = screen.getByText(
      "Enter a dollar value in dollars with no more than two decimal places.",
    );
    expect(value.getAttribute("aria-describedby")).toContain(valueError.id);
    expect(submit).not.toHaveBeenCalled();
  });

  it("disables every control when a parent mutation is pending", () => {
    renderWithApp(
      <OpportunityCostForm mode="edit" isPending onSubmit={vi.fn()} />,
    );

    expect(screen.getByLabelText("Label")).toBeDisabled();
    expect(screen.getByLabelText("Unit name")).toBeDisabled();
    expect(screen.getByLabelText("Dollar value")).toBeDisabled();
    expect(
      screen.getByRole("button", { name: "Saving changes…" }),
    ).toBeDisabled();
  });

  it("prevents another submission while an async callback is pending", async () => {
    const user = userEvent.setup();
    const submit = vi.fn(() => new Promise<void>(() => undefined));
    renderWithApp(<OpportunityCostForm mode="create" onSubmit={submit} />);

    await user.type(screen.getByLabelText("Label"), "Hours worked");
    await user.type(screen.getByLabelText("Unit name"), "hours");
    await user.type(screen.getByLabelText("Dollar value"), "10.00");
    await user.dblClick(screen.getByRole("button", { name: "Create example" }));

    expect(
      screen.getByRole("button", { name: "Creating example…" }),
    ).toBeDisabled();
    expect(submit).toHaveBeenCalledOnce();
  });

  it("maps server fields to visible controls and preserves input", async () => {
    const user = userEvent.setup();
    const submit = vi.fn().mockRejectedValue(
      new ApiError(422, "validation_error", "Invalid example.", {
        label: "Choose a shorter label.",
        dollar_value_cents: "Choose a different dollar value.",
      }),
    );
    renderWithApp(<OpportunityCostForm mode="create" onSubmit={submit} />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Create example" }));

    expect(await screen.findByRole("alert")).toHaveFocus();
    expect(screen.getByText("Choose a shorter label.")).toBeVisible();
    expect(screen.getByText("Choose a different dollar value.")).toBeVisible();
    expect(screen.getByLabelText("Label")).toHaveValue("Hours worked");
  });

  it("uses safe global feedback instead of exposing an unexpected server message", async () => {
    const user = userEvent.setup();
    const submit = vi
      .fn()
      .mockRejectedValue(
        new ApiError(503, "unavailable", "Private upstream detail."),
      );
    renderWithApp(<OpportunityCostForm mode="edit" onSubmit={submit} />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not save the example. Please try again.",
    );
    expect(screen.queryByText("Private upstream detail.")).toBeNull();
  });
});

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Label"), "Hours worked");
  await user.type(screen.getByLabelText("Unit name"), "hours");
  await user.type(screen.getByLabelText("Dollar value"), "10.00");
}
