import { http, HttpResponse } from "msw";

export const TEST_API_ORIGIN = "http://localhost";
export const TEST_API_BASE_URL = `${TEST_API_ORIGIN}/api`;

export const handlers = [
  http.get(`${TEST_API_BASE_URL}/health`, () => {
    return HttpResponse.json({ status: "ok" });
  }),
  http.get("/api/entries", () => {
    return HttpResponse.json({
      needs_check_in: [],
      waiting: [],
      saved: [],
      purchased: [],
    });
  }),
  http.get("/api/auth/me", () => {
    return HttpResponse.json(
      {
        error: {
          code: "unauthorized",
          message: "Authentication is required.",
        },
      },
      { status: 401 },
    );
  }),
];
