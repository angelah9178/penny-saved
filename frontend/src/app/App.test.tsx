import { render, screen } from "@testing-library/react";
import { useQueryClient } from "@tanstack/react-query";
import { createMemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { createQueryClient } from "./queryClient";
import { AppProviders } from "./providers";

describe("AppProviders", () => {
  it("makes the supplied query client available to routed content", () => {
    const queryClient = createQueryClient();
    const router = createMemoryRouter([
      {
        path: "/",
        element: <QueryClientProbe expectedClient={queryClient} />,
      },
    ]);

    render(<AppProviders queryClient={queryClient} router={router} />);

    expect(
      screen.getByText("The shared query client is available."),
    ).toBeInTheDocument();
  });
});

function QueryClientProbe({
  expectedClient,
}: {
  expectedClient: ReturnType<typeof createQueryClient>;
}) {
  const queryClient = useQueryClient();

  return (
    <p>
      {queryClient === expectedClient
        ? "The shared query client is available."
        : "The query client is not available."}
    </p>
  );
}
