import { render, screen } from "@testing-library/react";
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
});
