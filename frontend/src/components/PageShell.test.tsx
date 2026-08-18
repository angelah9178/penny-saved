import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PageShell } from "./PageShell";

describe("PageShell", () => {
  it("provides shared page landmarks around its content", () => {
    render(
      <PageShell>
        <h1>Dashboard</h1>
        <p>Dashboard content</p>
      </PageShell>,
    );

    expect(screen.getByRole("banner")).toHaveTextContent("A Penny Saved");
    expect(screen.getByRole("main")).toContainElement(
      screen.getByRole("heading", { level: 1, name: "Dashboard" }),
    );
    expect(screen.getByText("Dashboard content")).toBeVisible();
  });

  it("shows when the application is healthy", async () => {
    render(
      <PageShell>
        <h1>Dashboard</h1>
      </PageShell>,
    );

    await waitFor(() => {
      expect(screen.getByRole("img", { name: "App is healthy" })).toHaveClass(
        "service-health--ready",
      );
    });
  });

  it("provides a skip link to the main content", () => {
    render(
      <PageShell>
        <h1>Dashboard</h1>
      </PageShell>,
    );

    expect(
      screen.getByRole("link", { name: "Skip to main content" }),
    ).toHaveAttribute("href", "#main-content");
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
  });

  it("moves focus to main content when the skip link is activated", async () => {
    const user = userEvent.setup();
    render(
      <PageShell>
        <h1>Dashboard</h1>
      </PageShell>,
    );

    await user.click(
      screen.getByRole("link", { name: "Skip to main content" }),
    );

    expect(screen.getByRole("main")).toHaveFocus();
  });

  it("places shared header actions in a named navigation landmark", () => {
    render(
      <PageShell
        headerActions={
          <nav aria-label="Account">
            <button type="button">Log out</button>
          </nav>
        }
      >
        <h1>Dashboard</h1>
      </PageShell>,
    );

    expect(
      screen.getByRole("navigation", { name: "Account" }),
    ).toContainElement(screen.getByRole("button", { name: "Log out" }));
  });
});
