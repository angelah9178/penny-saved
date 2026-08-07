import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { expectNoAccessibilityViolations } from "../test/accessibility";
import { RouteErrorPage } from "./RouteErrorPage";

describe("RouteErrorPage", () => {
  beforeEach(() => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("shows a safe focused recovery view for unexpected render failures", async () => {
    const router = createMemoryRouter(
      [
        {
          path: "/broken",
          element: <BrokenPage />,
          errorElement: <RouteErrorPage />,
        },
        { path: "/", element: <h1>Home</h1> },
      ],
      { initialEntries: ["/broken"] },
    );

    const { container } = render(
      <AppProviders queryClient={createQueryClient()} router={router} />,
    );

    const heading = await screen.findByRole("heading", {
      name: "We could not open this page",
    });
    expect(heading).toHaveFocus();
    expect(document.title).toBe("Page error | A Penny Saved");
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute(
      "href",
      "/",
    );
    expect(screen.queryByText("private stack detail")).toBeNull();
    await expectNoAccessibilityViolations(container);
  });

  it("can navigate safely home from the error view", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter(
      [
        {
          path: "/broken",
          element: <BrokenPage />,
          errorElement: <RouteErrorPage />,
        },
        { path: "/", element: <h1>Home</h1> },
      ],
      { initialEntries: ["/broken"] },
    );

    render(<AppProviders queryClient={createQueryClient()} router={router} />);
    await user.click(await screen.findByRole("link", { name: "Return home" }));

    expect(await screen.findByRole("heading", { name: "Home" })).toBeVisible();
  });

  it("explains a lazy-route loading failure without exposing details", async () => {
    const router = createMemoryRouter(
      [
        {
          path: "/broken-lazy",
          lazy: () => Promise.reject(new Error("private lazy import detail")),
          errorElement: <RouteErrorPage />,
        },
      ],
      { initialEntries: ["/broken-lazy"] },
    );

    render(<AppProviders queryClient={createQueryClient()} router={router} />);

    expect(
      await screen.findByRole("heading", {
        name: "We could not open this page",
      }),
    ).toHaveFocus();
    expect(screen.queryByText("private lazy import detail")).toBeNull();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });
});

function BrokenPage(): never {
  throw new Error("private stack detail");
}
