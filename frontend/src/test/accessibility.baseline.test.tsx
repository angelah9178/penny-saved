import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, it, vi } from "vitest";

import { PageShell } from "../components/PageShell";
import { AuthForm } from "../features/auth/AuthForm";
import { DeleteOpportunityCostExampleButton } from "../features/opportunity-costs/DeleteOpportunityCostExampleButton";
import { EntryForm } from "../features/entries/EntryForm";
import { DashboardPage } from "../pages/DashboardPage";
import type { OpportunityCostExample } from "../types/api";
import { expectNoAccessibilityViolations } from "./accessibility";
import { renderWithApp } from "./render";

const example: OpportunityCostExample = {
  id: "example-id",
  label: "Hours worked",
  unit_name: "hours",
  dollar_value_cents: 1_000,
  created_at: "2026-08-06T12:00:00Z",
  updated_at: "2026-08-06T12:00:00Z",
};

describe("DEV-020 automated accessibility baseline", () => {
  it("scans the shared application shell", async () => {
    const { container } = renderWithApp(
      <PageShell
        headerActions={
          <nav aria-label="Account">
            <a href="/login">Log in</a>
          </nav>
        }
      >
        <h1>Welcome</h1>
        <p>Track the purchases you choose to avoid.</p>
      </PageShell>,
    );

    await expectNoAccessibilityViolations(container);
  });

  it("scans an authentication form", async () => {
    const { container } = renderWithApp(
      <main>
        <h1>Log in</h1>
        <AuthForm mode="login" />
      </main>,
    );

    await expectNoAccessibilityViolations(container);
  });

  it("scans the loaded dashboard structure", async () => {
    const { container } = renderWithApp(
      <main>
        <DashboardPage />
      </main>,
      { initialEntry: "/dashboard" },
    );

    await screen.findByRole("heading", { name: /^Needs check-in/u });
    await expectNoAccessibilityViolations(container);
  });

  it("scans a feature form", async () => {
    const { container } = renderWithApp(
      <main>
        <h1>Add an impulse purchase</h1>
        <EntryForm mode="create" onSubmit={vi.fn()} />
      </main>,
    );

    await expectNoAccessibilityViolations(container);
  });

  it("scans an open confirmation dialog", async () => {
    const user = userEvent.setup();
    const { container } = renderWithApp(
      <main>
        <h1>Opportunity-cost examples</h1>
        <DeleteOpportunityCostExampleButton example={example} />
      </main>,
    );

    await user.click(
      screen.getByRole("button", { name: "Delete Hours worked" }),
    );
    await screen.findByRole("alertdialog", { name: "Delete Hours worked?" });

    await expectNoAccessibilityViolations(container);
  });
});
