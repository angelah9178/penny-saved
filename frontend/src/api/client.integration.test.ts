import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TEST_API_BASE_URL } from "../test/handlers";
import { server } from "../test/server";
import { apiFetch } from "./client";

describe("apiFetch request boundary", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", TEST_API_BASE_URL);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("sends credentials, required headers, and JSON through a real request", async () => {
    let observedRequest:
      | {
          credentials: RequestCredentials;
          accept: string | null;
          contentType: string | null;
          testHeader: string | null;
          body: unknown;
        }
      | undefined;

    server.use(
      http.post(`${TEST_API_BASE_URL}/auth/login`, async ({ request }) => {
        observedRequest = {
          credentials: request.credentials,
          accept: request.headers.get("Accept"),
          contentType: request.headers.get("Content-Type"),
          testHeader: request.headers.get("X-Test-Header"),
          body: await request.json(),
        };

        return HttpResponse.json({
          user: { id: "user-1", email: "user@example.com" },
        });
      }),
    );

    const response = await apiFetch<{ user: { id: string; email: string } }>(
      "/auth/login",
      {
        method: "POST",
        headers: { "X-Test-Header": "present" },
        body: { email: "user@example.com", password: "password123" },
      },
    );

    expect(observedRequest).toEqual({
      credentials: "include",
      accept: "application/json",
      contentType: "application/json",
      testHeader: "present",
      body: { email: "user@example.com", password: "password123" },
    });
    expect(response.user).toEqual({
      id: "user-1",
      email: "user@example.com",
    });
  });

  it("turns the backend error envelope into an ApiError", async () => {
    server.use(
      http.post(`${TEST_API_BASE_URL}/auth/login`, () => {
        return HttpResponse.json(
          {
            error: {
              code: "invalid_credentials",
              message: "The email or password is incorrect.",
              fields: { email: "Check your email address." },
            },
          },
          { status: 401 },
        );
      }),
    );

    await expect(
      apiFetch("/auth/login", {
        method: "POST",
        body: { email: "user@example.com", password: "incorrect" },
      }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "invalid_credentials",
      message: "The email or password is incorrect.",
      fields: { email: "Check your email address." },
    });
  });

  it("handles a real 204 response without parsing a body", async () => {
    server.use(
      http.delete(`${TEST_API_BASE_URL}/entries/entry-1`, () => {
        return new HttpResponse(null, { status: 204 });
      }),
    );

    await expect(
      apiFetch<void>("/entries/entry-1", { method: "DELETE" }),
    ).resolves.toBeUndefined();
  });
});
