import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { AppProviders } from "../../app/providers";
import { createQueryClient } from "../../app/queryClient";
import { appRoutes } from "../../routes/router";
import { server } from "../../test/server";
import type { AuthResponse } from "../../types/api";

const authResponse: AuthResponse = {
  user: { id: "user-1", email: "person@example.com" },
};

describe("complete authentication router flow", () => {
  it("signs up, restores on refresh, logs out, and guards protected content", async () => {
    const user = userEvent.setup();
    let sessionValid = false;
    server.use(
      http.get("/api/auth/me", () =>
        sessionValid ? HttpResponse.json(authResponse) : unauthorizedResponse(),
      ),
      http.post("/api/auth/signup", () => {
        sessionValid = true;
        return HttpResponse.json(authResponse, { status: 201 });
      }),
      http.post("/api/auth/logout", () => {
        sessionValid = false;
        return new Response(null, { status: 200 });
      }),
    );

    const firstApp = renderApplication("/signup");
    await user.type(
      await screen.findByLabelText("Email"),
      "person@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Create account" }));
    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();

    firstApp.unmount();
    const refreshedApp = renderApplication("/dashboard");
    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Log in" }),
    ).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Log out" }));
    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();

    await refreshedApp.router.navigate("/dashboard");
    await waitFor(() =>
      expect(refreshedApp.router.state.location.pathname).toBe("/login"),
    );
    expect(
      await screen.findByRole("heading", { name: "Log in" }),
    ).toBeInTheDocument();
  });

  it("logs in and returns to the originally requested protected route", async () => {
    const user = userEvent.setup();
    let sessionValid = false;
    server.use(
      http.get("/api/auth/me", () =>
        sessionValid ? HttpResponse.json(authResponse) : unauthorizedResponse(),
      ),
      http.post("/api/auth/login", () => {
        sessionValid = true;
        return HttpResponse.json(authResponse);
      }),
    );
    const app = renderApplication("/dashboard?view=recent#top");

    await user.type(
      await screen.findByLabelText("Email"),
      "person@example.com",
    );
    await user.type(screen.getByLabelText("Password"), "password123");
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(
      await screen.findByRole("heading", { name: "Dashboard" }),
    ).toBeInTheDocument();
    expect(app.router.state.location).toMatchObject({
      pathname: "/dashboard",
      search: "?view=recent",
      hash: "#top",
    });
  });
});

function unauthorizedResponse() {
  return HttpResponse.json(
    {
      error: {
        code: "unauthorized",
        message: "Authentication is required.",
      },
    },
    { status: 401 },
  );
}

function renderApplication(initialEntry: string) {
  const queryClient = createQueryClient();
  const router = createMemoryRouter(appRoutes, {
    initialEntries: [initialEntry],
  });

  return {
    ...render(<AppProviders queryClient={queryClient} router={router} />),
    router,
  };
}
