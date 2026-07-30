import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { DashboardEntries } from "../../types/api";
import { getDashboardEntries } from "./api";

const fetchMock = vi.fn<typeof fetch>();
const dashboardEntries: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};

describe("dashboard entries API", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
  });

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("gets the four dashboard entry lists through the credentialed API client", async () => {
    fetchMock.mockResolvedValue(Response.json(dashboardEntries));

    await expect(getDashboardEntries()).resolves.toEqual(dashboardEntries);

    const [url, init] = firstFetchCall();
    expect(url).toBe("/api/entries");
    expect(init).toMatchObject({
      credentials: "include",
    });
    expect(init?.method).toBeUndefined();
  });

  it("forwards TanStack Query cancellation to the request", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(Response.json(dashboardEntries));

    await getDashboardEntries(controller.signal);

    expect(firstFetchCall()[1]).toMatchObject({ signal: controller.signal });
  });
});

function firstFetchCall(): Parameters<typeof fetch> {
  const call = fetchMock.mock.calls[0];

  if (call === undefined) {
    throw new Error("Expected fetch to have been called.");
  }

  return call;
}
