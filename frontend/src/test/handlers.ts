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
  http.get("/api/stats/summary", ({ request }) => {
    const range =
      new URL(request.url).searchParams.get("range") ?? "this_month";
    return HttpResponse.json({
      range,
      total_saved_cents: 0,
      avoided_purchase_count: 0,
      purchased_count: 0,
      opportunity_costs: [],
    });
  }),
  http.get("/api/opportunity-cost-examples", () => {
    return HttpResponse.json({ examples: [] });
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
