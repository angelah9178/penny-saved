import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  CreateOpportunityCostExampleRequest,
  OpportunityCostExampleResponse,
  OpportunityCostExamplesResponse,
} from "../../types/api";
import {
  createOpportunityCostExample,
  deleteOpportunityCostExample,
  getOpportunityCostExamples,
  updateOpportunityCostExample,
} from "./api";

const fetchMock = vi.fn<typeof fetch>();
const payload: CreateOpportunityCostExampleRequest = {
  label: "Hours worked",
  unit_name: "hours",
  dollar_value_cents: 1_000,
};
const exampleResponse: OpportunityCostExampleResponse = {
  example: {
    id: "63000000-0000-4000-8000-000000000001",
    ...payload,
    created_at: "2026-08-06T12:00:00Z",
    updated_at: "2026-08-06T12:00:00Z",
  },
};
const examplesResponse: OpportunityCostExamplesResponse = {
  examples: [exampleResponse.example],
};

describe("opportunity-cost examples API", () => {
  beforeEach(() => vi.stubGlobal("fetch", fetchMock));

  afterEach(() => {
    fetchMock.mockReset();
    vi.unstubAllGlobals();
  });

  it("lists examples and forwards query cancellation", async () => {
    const controller = new AbortController();
    fetchMock.mockResolvedValue(Response.json(examplesResponse));

    await expect(
      getOpportunityCostExamples(controller.signal),
    ).resolves.toEqual(examplesResponse);

    expect(firstFetchCall()).toEqual([
      "/api/opportunity-cost-examples",
      expect.objectContaining({
        credentials: "include",
        signal: controller.signal,
      }),
    ]);
    expect(firstFetchCall()[1]?.method).toBeUndefined();
  });

  it("creates an example with only the mutable fields", async () => {
    fetchMock.mockResolvedValue(
      Response.json(exampleResponse, { status: 201 }),
    );

    await expect(createOpportunityCostExample(payload)).resolves.toEqual(
      exampleResponse,
    );

    expect(firstFetchCall()).toEqual([
      "/api/opportunity-cost-examples",
      expect.objectContaining({
        method: "POST",
        credentials: "include",
        body: JSON.stringify(payload),
      }),
    ]);
  });

  it("updates an encoded example ID with only the mutable fields", async () => {
    fetchMock.mockResolvedValue(Response.json(exampleResponse));

    await expect(
      updateOpportunityCostExample("example/with spaces", payload),
    ).resolves.toEqual(exampleResponse);

    expect(firstFetchCall()).toEqual([
      "/api/opportunity-cost-examples/example%2Fwith%20spaces",
      expect.objectContaining({
        method: "PATCH",
        credentials: "include",
        body: JSON.stringify(payload),
      }),
    ]);
  });

  it("deletes an encoded ID without parsing the empty 204 response", async () => {
    fetchMock.mockResolvedValue(new Response(null, { status: 204 }));

    await expect(
      deleteOpportunityCostExample("example/with spaces"),
    ).resolves.toBeUndefined();

    expect(firstFetchCall()).toEqual([
      "/api/opportunity-cost-examples/example%2Fwith%20spaces",
      expect.objectContaining({ method: "DELETE", credentials: "include" }),
    ]);
    expect(firstFetchCall()[1]?.body).toBeUndefined();
  });
});

function firstFetchCall(): Parameters<typeof fetch> {
  const call = fetchMock.mock.calls[0];
  if (call === undefined)
    throw new Error("Expected fetch to have been called.");
  return call;
}
