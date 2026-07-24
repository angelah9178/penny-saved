import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ComponentProps } from "react";
import { RouterProvider } from "react-router-dom";

export type AppProvidersProps = {
  queryClient: QueryClient;
  router: ComponentProps<typeof RouterProvider>["router"];
};

export function AppProviders({ queryClient, router }: AppProvidersProps) {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
