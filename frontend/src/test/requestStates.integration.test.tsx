import { useQuery } from "@tanstack/react-query";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { apiFetch } from "../api/client";
import { EmptyState } from "../components/EmptyState";
import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { PageShell } from "../components/PageShell";
import { TEST_API_BASE_URL } from "./handlers";
import { renderWithApp } from "./render";
import { server } from "./server";

type TestEntriesResponse = {
  entries: string[];
};

describe("routed request states", () => {
  beforeEach(() => {
    vi.stubEnv("VITE_API_BASE_URL", TEST_API_BASE_URL);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("shows loading and then successful API data", async () => {
    server.use(
      http.get(`${TEST_API_BASE_URL}/test/entries`, async () => {
        await delay(50);
        return HttpResponse.json({ entries: ["New headphones"] });
      }),
    );

    renderProbe();

    expect(screen.getByRole("status")).toHaveTextContent("Loading entries…");
    expect(
      await screen.findByRole("heading", { name: "Your entries" }),
    ).toBeInTheDocument();
    expect(screen.getByText("New headphones")).toBeVisible();
  });

  it("shows an empty state only after a successful empty response", async () => {
    server.use(
      http.get(`${TEST_API_BASE_URL}/test/entries`, () => {
        return HttpResponse.json({ entries: [] });
      }),
    );

    renderProbe();

    expect(
      await screen.findByRole("region", { name: "No entries yet" }),
    ).toHaveTextContent("Your entries will appear here.");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows a request error and lets the user retry successfully", async () => {
    const user = userEvent.setup();
    let requestCount = 0;

    server.use(
      http.get(`${TEST_API_BASE_URL}/test/entries`, () => {
        requestCount += 1;

        if (requestCount === 1) {
          return HttpResponse.json(
            {
              error: {
                code: "unavailable",
                message: "Entries are temporarily unavailable.",
              },
            },
            { status: 503 },
          );
        }

        return HttpResponse.json({ entries: ["New headphones"] });
      }),
    );

    renderProbe();

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Entries are temporarily unavailable.",
    );

    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("New headphones")).toBeVisible();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(requestCount).toBe(2);
  });
});

function RequestStateProbe() {
  const entriesQuery = useQuery({
    queryKey: ["test", "entries"],
    queryFn: ({ signal }) =>
      apiFetch<TestEntriesResponse>("/test/entries", { signal }),
    retry: false,
  });

  if (entriesQuery.isPending) {
    return <Loading message="Loading entries…" />;
  }

  if (entriesQuery.isError) {
    return (
      <ErrorAlert
        message={entriesQuery.error.message}
        onRetry={() => {
          void entriesQuery.refetch();
        }}
      />
    );
  }

  if (entriesQuery.data.entries.length === 0) {
    return (
      <EmptyState
        title="No entries yet"
        message="Your entries will appear here."
      />
    );
  }

  return (
    <>
      <h1>Your entries</h1>
      <ul>
        {entriesQuery.data.entries.map((entry) => (
          <li key={entry}>{entry}</li>
        ))}
      </ul>
    </>
  );
}

function renderProbe() {
  return renderWithApp(
    <PageShell>
      <RequestStateProbe />
    </PageShell>,
  );
}
