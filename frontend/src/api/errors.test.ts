import { describe, expect, it } from "vitest";

import { ApiError, apiErrorFromResponse } from "./errors";

describe("apiErrorFromResponse", () => {
  it("parses the standard backend error envelope", async () => {
    const response = Response.json(
      {
        error: {
          code: "validation_error",
          message: "Request validation failed.",
          fields: { email: "Enter a valid email address." },
        },
      },
      { status: 422 },
    );

    await expect(apiErrorFromResponse(response)).resolves.toMatchObject({
      name: "ApiError",
      status: 422,
      code: "validation_error",
      message: "Request validation failed.",
      fields: { email: "Enter a valid email address." },
    });
  });

  it("uses a safe fallback for invalid JSON", async () => {
    const response = new Response("not JSON", { status: 500 });

    await expect(apiErrorFromResponse(response)).resolves.toEqual(
      expect.objectContaining({
        status: 500,
        code: "request_failed",
        message: "The request could not be completed.",
      }),
    );
  });

  it.each([
    {},
    { error: null },
    { error: { code: "", message: "Failed." } },
    { error: { code: "failed", message: "" } },
    {
      error: {
        code: "validation_error",
        message: "Failed.",
        fields: { email: 42 },
      },
    },
  ])("uses a safe fallback for malformed envelope %#", async (payload) => {
    const response = Response.json(payload, { status: 400 });

    const error = await apiErrorFromResponse(response);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      status: 400,
      code: "request_failed",
      message: "The request could not be completed.",
    });
  });
});
