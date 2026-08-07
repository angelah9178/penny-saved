import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, Link, Outlet } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";
import { RouteExperience } from "./RouteExperience";
import { titleForPath } from "./routeTitles";

describe("RouteExperience", () => {
  it.each([
    ["/dashboard", "Dashboard | A Penny Saved"],
    ["/login", "Log in | A Penny Saved"],
    ["/signup", "Create your account | A Penny Saved"],
    ["/entries/new", "Add an entry | A Penny Saved"],
    [
      "/settings/opportunity-costs",
      "Opportunity-cost examples | A Penny Saved",
    ],
    ["/entries/entry-id", "Entry details | A Penny Saved"],
    ["/entries/entry-id/edit", "Edit entry | A Penny Saved"],
    ["/entries/entry-id/check-in", "Check in | A Penny Saved"],
    ["/unknown", "Page not found | A Penny Saved"],
  ])("maps %s to a useful document title", (pathname, title) => {
    expect(titleForPath(pathname)).toBe(title);
  });

  it("updates the title and moves focus to main after page navigation", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter(
      [
        {
          path: "/",
          element: (
            <>
              <RouteExperience />
              <main id="main-content" tabIndex={-1}>
                <Outlet />
              </main>
            </>
          ),
          children: [
            {
              path: "dashboard",
              element: <Link to="/entries/new">Add an entry</Link>,
            },
            { path: "entries/new", element: <h1>Add an entry</h1> },
          ],
        },
      ],
      { initialEntries: ["/dashboard"] },
    );

    render(<AppProviders queryClient={createQueryClient()} router={router} />);
    expect(document.title).toBe("Dashboard | A Penny Saved");

    await user.click(screen.getByRole("link", { name: "Add an entry" }));

    await waitFor(() => expect(screen.getByRole("main")).toHaveFocus());
    expect(document.title).toBe("Add an entry | A Penny Saved");
  });

  it("does not steal focus when only the search string changes", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter(
      [
        {
          path: "/dashboard",
          element: (
            <>
              <RouteExperience />
              <main id="main-content" tabIndex={-1}>
                <Link to="/dashboard?range=all_time">All time</Link>
              </main>
            </>
          ),
        },
      ],
      { initialEntries: ["/dashboard"] },
    );

    render(<AppProviders queryClient={createQueryClient()} router={router} />);
    const link = screen.getByRole("link", { name: "All time" });
    await user.click(link);

    expect(link).toHaveFocus();
    expect(screen.getByRole("main")).not.toHaveFocus();
  });
});
