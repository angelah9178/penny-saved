import { render } from "@testing-library/react";
import type { QueryClient } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { createMemoryRouter } from "react-router-dom";

import { AppProviders } from "../app/providers";
import { createQueryClient } from "../app/queryClient";

export type RenderWithAppOptions = {
  initialEntry?: string;
  queryClient?: QueryClient;
};

export function renderWithApp(
  element: ReactElement,
  options: RenderWithAppOptions = {},
) {
  const queryClient = options.queryClient ?? createQueryClient();
  const router = createMemoryRouter(
    [
      {
        path: "*",
        element,
      },
    ],
    {
      initialEntries: [options.initialEntry ?? "/"],
    },
  );

  return {
    ...render(<AppProviders queryClient={queryClient} router={router} />),
    queryClient,
    router,
  };
}
