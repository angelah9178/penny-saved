import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, delay } from "msw";
import { describe, expect, it, vi } from "vitest";

import { queryKeys } from "../../lib/queryKeys";
import { renderWithApp } from "../../test/render";
import { server } from "../../test/server";
import type { AuthResponse } from "../../types/api";
import { AuthForm } from "./AuthForm";

const authResponse: AuthResponse = {
  user: { id: "user-1", email: "person@example.com" },
};

describe("AuthForm", () => {
  it("submits a trimmed email and an unchanged signup password", async () => {
    const user = userEvent.setup();
    let submittedBody: unknown;
    server.use(
      http.post("/api/auth/signup", async ({ request }) => {
        submittedBody = await request.json();
        return HttpResponse.json(authResponse, { status: 201 });
      }),
    );
    const { queryClient, router } = renderWithApp(<AuthForm mode="signup" />);

    await user.type(screen.getByLabelText("Email"), "  Person@Example.COM  ");
    await user.type(screen.getByLabelText("Password"), "  password  ");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() =>
      expect(router.state.location.pathname).toBe("/dashboard"),
    );
    expect(submittedBody).toEqual({
      email: "Person@Example.COM",
      password: "  password  ",
    });
    expect(queryClient.getQueryData(queryKeys.auth.me())).toEqual(authResponse);
  });

  it("uses the correct labels and autocomplete values for login", () => {
    renderWithApp(<AuthForm mode="login" />);

    expect(screen.getByLabelText("Email")).toHaveAttribute(
      "autocomplete",
      "email",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "autocomplete",
      "current-password",
    );
  });

  it("uses new-password autocomplete for signup", () => {
    renderWithApp(<AuthForm mode="signup" />);

    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "autocomplete",
      "new-password",
    );
  });

  it("shows client errors without making a request and focuses the summary", async () => {
    const user = userEvent.setup();
    const request = vi.fn();
    server.use(
      http.post("/api/auth/signup", () => {
        request();
        return HttpResponse.json(authResponse);
      }),
    );
    renderWithApp(<AuthForm mode="signup" />);

    await user.type(screen.getByLabelText("Email"), "invalid");
    await user.type(screen.getByLabelText("Password"), "short");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByRole("alert")).toHaveFocus();
    expect(
      screen.getByText("Enter a valid email address."),
    ).toBeInTheDocument();
    expect(
      screen.getByText("Password must be at least 8 characters."),
    ).toBeInTheDocument();
    expect(request).not.toHaveBeenCalled();
  });

  it("associates duplicate signup email with the email field", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/auth/signup", () =>
        HttpResponse.json(
          {
            error: {
              code: "duplicate_email",
              message: "An account with this email already exists.",
            },
          },
          { status: 409 },
        ),
      ),
    );
    renderWithApp(<AuthForm mode="signup" />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    const email = screen.getByLabelText("Email");
    expect(
      await screen.findByText("An account with this email already exists."),
    ).toHaveAttribute("id", email.getAttribute("aria-describedby"));
    expect(screen.getByRole("alert")).toHaveFocus();
  });

  it("shows generic invalid credentials on login", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json(
          {
            error: {
              code: "invalid_credentials",
              message: "Invalid credentials.",
            },
          },
          { status: 401 },
        ),
      ),
    );
    renderWithApp(<AuthForm mode="login" />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "The email or password is incorrect.",
    );
    expect(screen.queryByText("Invalid credentials.")).not.toBeInTheDocument();
  });

  it("maps known backend field errors and handles unknown fields globally", async () => {
    const user = userEvent.setup();
    server.use(
      http.post("/api/auth/signup", () =>
        HttpResponse.json(
          {
            error: {
              code: "validation_error",
              message: "The submitted data is invalid.",
              fields: {
                email: "Enter valid text.",
                is_admin: "Enter a valid value.",
              },
            },
          },
          { status: 422 },
        ),
      ),
    );
    renderWithApp(<AuthForm mode="signup" />);

    await fillValidForm(user);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("Enter valid text.")).toBeInTheDocument();
    expect(screen.queryByText("is_admin")).not.toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Please correct the highlighted fields.",
    );
  });

  it("prevents duplicate submission while the request is pending", async () => {
    const user = userEvent.setup();
    const request = vi.fn();
    server.use(
      http.post("/api/auth/login", async () => {
        request();
        await delay(100);
        return HttpResponse.json(authResponse);
      }),
    );
    renderWithApp(<AuthForm mode="login" />);

    await fillValidForm(user);
    const button = screen.getByRole("button", { name: "Log in" });
    await user.dblClick(button);

    expect(screen.getByRole("button", { name: "Logging in…" })).toBeDisabled();
    await waitFor(() => expect(request).toHaveBeenCalledOnce());
  });

  it("does not render a password echoed by a server error", async () => {
    const user = userEvent.setup();
    const password = "secret-password";
    server.use(
      http.post("/api/auth/login", () =>
        HttpResponse.json(
          {
            error: {
              code: "service_error",
              message: `Request failed for ${password}`,
            },
          },
          { status: 500 },
        ),
      ),
    );
    renderWithApp(<AuthForm mode="login" />);

    await user.type(screen.getByLabelText("Email"), "person@example.com");
    await user.type(screen.getByLabelText("Password"), password);
    await user.click(screen.getByRole("button", { name: "Log in" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "We could not complete your request. Please try again.",
    );
    expect(
      screen.queryByText(new RegExp(password, "u")),
    ).not.toBeInTheDocument();
  });
});

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText("Email"), "person@example.com");
  await user.type(screen.getByLabelText("Password"), "password123");
}
