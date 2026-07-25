import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { appRoutes } from "./router";

describe("application router", () => {
  it("renders the home route inside the shared page shell", async () => {
    renderRoute("/");

    expect(screen.getByRole("banner")).toHaveTextContent("A Penny Saved");
    expect(
      await screen.findByRole("heading", { level: 1, name: "A Penny Saved" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveTextContent(
      "Application setup is in progress.",
    );
    expect(
      screen.getByRole("link", { name: "Skip to main content" }),
    ).toHaveAttribute("href", "#main-content");
  });

  it("renders an unknown route inside the same page shell", async () => {
    renderRoute("/does-not-exist");

    expect(screen.getByRole("banner")).toHaveTextContent("A Penny Saved");
    expect(
      await screen.findByRole("heading", {
        level: 1,
        name: "Page not found",
      }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Return home" }),
    ).toBeInTheDocument();
  });

  it("navigates home without replacing the application shell", async () => {
    const user = userEvent.setup();
    const { router } = renderRoute("/does-not-exist");
    const banner = screen.getByRole("banner");

    await user.click(await screen.findByRole("link", { name: "Return home" }));

    expect(router.state.location.pathname).toBe("/");
    expect(screen.getByRole("banner")).toBe(banner);
    expect(
      screen.getByRole("heading", { level: 1, name: "A Penny Saved" }),
    ).toBeInTheDocument();
  });
});

function renderRoute(initialEntry: string) {
  const queryClient = createQueryClient();
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [initialEntry],
  });

  return {
    ...render(<AppProviders queryClient={queryClient} router={router} />),
    queryClient,
    router,
  };
}
