import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CheckInEntryRequest,
  CreateEntryRequest,
  DashboardEntries,
  EntryResponse,
} from "../../types/api";
import {
  checkInEntry,
  createEntry,
  deleteEntry,
  getDashboardEntries,
  getEntry,
  updateEntry,
} from "./api";

const fetchMock = vi.fn<typeof fetch>();
const dashboardEntries: DashboardEntries = {
  needs_check_in: [],
  waiting: [],
  saved: [],
  purchased: [],
};
const payload: CreateEntryRequest = {
  item_name: "Coffee grinder",
  price_cents: 8_999,
  reason_wanted: "Better coffee at home",
};
const entryResponse: EntryResponse = {
  entry: {
    id: "70000000-0000-4000-8000-000000000001",
    ...payload,
    status: "waiting",
    dashboard_bucket: "waiting",
    comment: null,
    created_at: "2026-07-31T14:00:00Z",
    eligible_for_check_in_at: "2026-08-02T14:00:00Z",
    checked_in_at: null,
    updated_at: "2026-07-31T14:00:00Z",
  },
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

  it("gets one entry and forwards request cancellation", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(Response.json(entryResponse));

    await expect(
      getEntry(entryResponse.entry.id, controller.signal),
    ).resolves.toEqual(entryResponse);

    const [url, init] = firstFetchCall();
    expect(url).toBe(`/api/entries/${entryResponse.entry.id}`);
    expect(init).toMatchObject({
      credentials: "include",
      signal: controller.signal,
    });
  });

  it("creates an entry with only the entry write fields", async () => {
    fetchMock.mockResolvedValue(Response.json(entryResponse, { status: 201 }));

    await expect(createEntry(payload)).resolves.toEqual(entryResponse);

    const [url, init] = firstFetchCall();
    expect(url).toBe("/api/entries");
    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
      body: JSON.stringify(payload),
    });
  });

  it("updates an entry with only the entry write fields", async () => {
    fetchMock.mockResolvedValue(Response.json(entryResponse));

    await expect(updateEntry(entryResponse.entry.id, payload)).resolves.toEqual(
      entryResponse,
    );

    const [url, init] = firstFetchCall();
    expect(url).toBe(`/api/entries/${entryResponse.entry.id}`);
    expect(init).toMatchObject({
      method: "PATCH",
      credentials: "include",
      body: JSON.stringify(payload),
    });
  });

  it("deletes an entry without trying to parse the 204 response", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(deleteEntry(entryResponse.entry.id)).resolves.toBeUndefined();

    const [url, init] = firstFetchCall();
    expect(url).toBe(`/api/entries/${entryResponse.entry.id}`);
    expect(init).toMatchObject({
      method: "DELETE",
      credentials: "include",
    });
    expect(init?.body).toBeUndefined();
  });

  it("checks in an entry with only the result and optional comment", async () => {
    const checkInPayload: CheckInEntryRequest = {
      result: "saved",
      comment: "I can borrow one.",
    };
    const checkedInResponse: EntryResponse = {
      entry: {
        ...entryResponse.entry,
        status: "saved",
        dashboard_bucket: "saved",
        comment: checkInPayload.comment,
        checked_in_at: "2026-08-02T14:00:00Z",
        updated_at: "2026-08-02T14:00:00Z",
      },
    };
    fetchMock.mockResolvedValue(Response.json(checkedInResponse));

    await expect(
      checkInEntry("entry/with spaces", checkInPayload),
    ).resolves.toEqual(checkedInResponse);

    const [url, init] = firstFetchCall();
    expect(url).toBe("/api/entries/entry%2Fwith%20spaces/check-in");
    expect(init).toMatchObject({
      method: "POST",
      credentials: "include",
      body: JSON.stringify(checkInPayload),
    });
  });
});

function firstFetchCall(): Parameters<typeof fetch> {
  const call = fetchMock.mock.calls[0];

  if (call === undefined) {
    throw new Error("Expected fetch to have been called.");
  }

  return call;
}
