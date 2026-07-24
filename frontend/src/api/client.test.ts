import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./errors";
import { apiFetch } from "./client";

const fetchMock = vi.fn<typeof fetch>();

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("uses the default API base URL and credentialed JSON headers", async () => {
    fetchMock.mockResolvedValue(Response.json({ status: "ok" }));

    await apiFetch<{ status: string }>("/health");

    const [url, init] = firstFetchCall();
    const headers = new Headers(init?.headers);

    expect(url).toBe("/api/health");
    expect(init?.credentials).toBe("include");
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("joins a configured base URL and endpoint without duplicate slashes", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://api.example.test/api/");
    fetchMock.mockResolvedValue(Response.json({ status: "ok" }));

    await apiFetch<{ status: string }>("/health");

    expect(firstFetchCall()[0]).toBe("https://api.example.test/api/health");
  });

  it("falls back to /api when the configured base URL is blank", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "   ");
    fetchMock.mockResolvedValue(Response.json({ status: "ok" }));

    await apiFetch<{ status: string }>("health");

    expect(firstFetchCall()[0]).toBe("/api/health");
  });

  it("serializes a JSON body and forwards request options", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(
      Response.json({ user: { id: "user-1", email: "user@example.com" } }),
    );

    await apiFetch("/auth/login", {
      method: "POST",
      body: { email: "user@example.com", password: "password123" },
      headers: {
        Accept: "text/plain",
        "Content-Type": "text/plain",
        "X-Test-Header": "present",
      },
      signal: controller.signal,
    });

    const [, init] = firstFetchCall();
    const headers = new Headers(init?.headers);

    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
      signal: controller.signal,
      body: JSON.stringify({
        email: "user@example.com",
        password: "password123",
      }),
    });
    expect(headers.get("Accept")).toBe("application/json");
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-Test-Header")).toBe("present");
  });

  it("returns parsed JSON from a successful response", async () => {
    fetchMock.mockResolvedValue(
      Response.json({ entry: { id: "entry-1" } }, { status: 200 }),
    );

    await expect(
      apiFetch<{ entry: { id: string } }>("/entries/entry-1"),
    ).resolves.toEqual({ entry: { id: "entry-1" } });
  });

  it("returns undefined for a 204 response", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      apiFetch<void>("/entries/entry-1", { method: "DELETE" }),
    ).resolves.toBeUndefined();
  });

  it("throws the parsed standard error response", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        {
          error: {
            code: "unauthorized",
            message: "Authentication is required.",
          },
        },
        { status: 401 },
      ),
    );

    await expect(apiFetch("/auth/me")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "unauthorized",
      message: "Authentication is required.",
    });
  });

  it("throws a safe error when a successful response contains invalid JSON", async () => {
    fetchMock.mockResolvedValue(new Response("not JSON", { status: 200 }));

    await expect(apiFetch("/health")).rejects.toMatchObject({
      status: 200,
      code: "invalid_response",
      message: "The server returned an invalid response.",
    });
  });

  it("converts a network failure into a safe ApiError", async () => {
    fetchMock.mockRejectedValue(new TypeError("secret browser detail"));

    const error = await apiFetch("/health").catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 0,
      code: "network_error",
      message: "Unable to reach the server. Please try again.",
    });
    expect((error as Error).message).not.toContain("secret browser detail");
  });

  it("preserves abort errors for query cancellation", async () => {
    const abortError = new DOMException(
      "The request was aborted.",
      "AbortError",
    );
    fetchMock.mockRejectedValue(abortError);

    await expect(apiFetch("/entries")).rejects.toBe(abortError);
  });
});

function firstFetchCall(): Parameters<typeof fetch> {
  const call = fetchMock.mock.calls[0];

  if (call === undefined) {
    throw new Error("Expected fetch to have been called.");
  }

  return call;
}
