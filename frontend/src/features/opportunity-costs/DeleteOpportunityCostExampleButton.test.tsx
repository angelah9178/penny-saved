import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { renderWithApp } from "../../test/render";
import { server } from "../../test/server";
import type { OpportunityCostExample } from "../../types/api";
import { DeleteOpportunityCostExampleButton } from "./DeleteOpportunityCostExampleButton";

const example: OpportunityCostExample = {
  id: "example-id",
  label: "Hours worked",
  unit_name: "hours",
  dollar_value_cents: 1_000,
  created_at: "2026-08-06T12:00:00Z",
  updated_at: "2026-08-06T12:00:00Z",
};

describe("DeleteOpportunityCostExampleButton", () => {
  it("names the example and cancels without sending DELETE", async () => {
    const user = userEvent.setup();
    let deleteRequests = 0;
    server.use(
      http.delete("/api/opportunity-cost-examples/example-id", () => {
        deleteRequests += 1;
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithApp(<DeleteOpportunityCostExampleButton example={example} />);

    const trigger = screen.getByRole("button", { name: "Delete Hours worked" });
    await user.click(trigger);
    expect(
      screen.getByRole("alertdialog", { name: "Delete Hours worked?" }),
    ).toHaveTextContent("cannot be undone");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.queryByRole("alertdialog")).toBeNull();
    await waitFor(() => expect(trigger).toHaveFocus());
    expect(deleteRequests).toBe(0);
  });

  it("traps keyboard focus and restores it after Escape", async () => {
    const user = userEvent.setup();
    renderWithApp(<DeleteOpportunityCostExampleButton example={example} />);
    const trigger = screen.getByRole("button", { name: "Delete Hours worked" });

    await user.click(trigger);
    const cancel = screen.getByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Delete example" });
    expect(cancel).toHaveFocus();
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(confirm).toHaveFocus();
    await user.tab();
    expect(cancel).toHaveFocus();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alertdialog")).toBeNull();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("deletes once, disables repeat confirmation, and reports success", async () => {
    const user = userEvent.setup();
    const deleted = vi.fn();
    let deleteRequests = 0;
    server.use(
      http.delete("/api/opportunity-cost-examples/example-id", async () => {
        deleteRequests += 1;
        await delay(50);
        return new HttpResponse(null, { status: 204 });
      }),
    );
    renderWithApp(
      <DeleteOpportunityCostExampleButton
        example={example}
        onDeleted={deleted}
      />,
    );

    await user.click(
      screen.getByRole("button", { name: "Delete Hours worked" }),
    );
    await user.dblClick(screen.getByRole("button", { name: "Delete example" }));
    expect(
      screen.getByRole("button", { name: "Deleting example…" }),
    ).toBeDisabled();

    await waitFor(() => expect(deleted).toHaveBeenCalledWith(example));
    expect(deleteRequests).toBe(1);
    expect(screen.queryByRole("alertdialog")).toBeNull();
  });

  it("keeps the dialog open and hides private details after failure", async () => {
    const user = userEvent.setup();
    server.use(
      http.delete("/api/opportunity-cost-examples/example-id", () =>
        HttpResponse.json(
          {
            error: { code: "unavailable", message: "Private upstream detail." },
          },
          { status: 503 },
        ),
      ),
    );
    renderWithApp(<DeleteOpportunityCostExampleButton example={example} />);

    await user.click(
      screen.getByRole("button", { name: "Delete Hours worked" }),
    );
    await user.click(screen.getByRole("button", { name: "Delete example" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not delete this example. Please try again.",
    );
    expect(screen.queryByText("Private upstream detail.")).toBeNull();
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Delete example" }),
    ).toBeEnabled();
  });

  it.each([403, 404])(
    "handles a stale %s response without exposing details",
    async (status) => {
      const user = userEvent.setup();
      const stale = vi.fn();
      server.use(
        http.delete("/api/opportunity-cost-examples/example-id", () =>
          HttpResponse.json(
            { error: { code: "not_available", message: "Private detail." } },
            { status },
          ),
        ),
      );
      renderWithApp(
        <DeleteOpportunityCostExampleButton
          example={example}
          onStale={stale}
        />,
      );

      await user.click(
        screen.getByRole("button", { name: "Delete Hours worked" }),
      );
      await user.click(screen.getByRole("button", { name: "Delete example" }));

      await waitFor(() => expect(stale).toHaveBeenCalledWith(example));
      expect(screen.queryByRole("alertdialog")).toBeNull();
      expect(screen.queryByText("Private detail.")).toBeNull();
    },
  );
});
