import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getCurrentUser, login, logout, signup } from "./api";

const fetchMock = vi.fn<typeof fetch>();
const credentials = {
  email: "person@example.com",
  password: "correct horse battery staple",
};
const authResponse = {
  user: { id: "user-1", email: "person@example.com" },
};

describe("authentication API", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it.each([
    ["signup", signup, "/api/auth/signup"],
    ["login", login, "/api/auth/login"],
  ] as const)(
    "sends the %s request through the credentialed API client",
    async (_operation, request, expectedUrl) => {
      fetchMock.mockResolvedValue(Response.json(authResponse));

      await expect(request(credentials)).resolves.toEqual(authResponse);

      const [url, init] = firstFetchCall();
      expect(url).toBe(expectedUrl);
      expect(init).toMatchObject({
        method: "POST",
        credentials: "include",
        body: JSON.stringify(credentials),
      });
    },
  );

  it("gets the current public user and forwards cancellation", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(Response.json(authResponse));

    await expect(getCurrentUser(controller.signal)).resolves.toEqual(
      authResponse,
    );

    const [url, init] = firstFetchCall();
    expect(url).toBe("/api/auth/me");
    expect(init).toMatchObject({
      credentials: "include",
      signal: controller.signal,
    });
  });

  it("logs out with an empty successful response", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 200 }));

    await expect(logout()).resolves.toBeUndefined();

    expect(firstFetchCall()).toMatchObject([
      "/api/auth/logout",
      { method: "POST", credentials: "include" },
    ]);
  });

  it("preserves standard API errors", async () => {
    fetchMock.mockResolvedValue(
      Response.json(
        {
          error: {
            code: "invalid_credentials",
            message: "Invalid email or password.",
          },
        },
        { status: 401 },
      ),
    );

    await expect(login(credentials)).rejects.toMatchObject({
      status: 401,
      code: "invalid_credentials",
      message: "Invalid email or password.",
    });
  });

  it("does not access browser storage, cookies, or logging", async () => {
    const localStorageGet = vi.spyOn(Storage.prototype, "getItem");
    const localStorageSet = vi.spyOn(Storage.prototype, "setItem");
    const consoleLog = vi
      .spyOn(console, "log")
      .mockImplementation(() => undefined);
    const cookieGetter = vi.spyOn(Document.prototype, "cookie", "get");
    const cookieSetter = vi.spyOn(Document.prototype, "cookie", "set");
    fetchMock.mockResolvedValue(Response.json(authResponse));

    await login(credentials);

    expect(localStorageGet).not.toHaveBeenCalled();
    expect(localStorageSet).not.toHaveBeenCalled();
    expect(consoleLog).not.toHaveBeenCalled();
    expect(cookieGetter).not.toHaveBeenCalled();
    expect(cookieSetter).not.toHaveBeenCalled();
  });
});

function firstFetchCall(): Parameters<typeof fetch> {
  const call = fetchMock.mock.calls[0];

  if (call === undefined) {
    throw new Error("Expected fetch to have been called.");
  }

  return call;
}
