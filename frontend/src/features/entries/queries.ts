import { queryOptions, useQuery } from "@tanstack/react-query";

import { shouldRetryQuery } from "../../app/queryClient";
import { queryKeys } from "../../lib/queryKeys";
import { runProtectedRequest } from "../auth/sessionExpiry";
import { getDashboardEntries } from "./api";

const DASHBOARD_STALE_TIME_MS = 30 * 1_000;
const DASHBOARD_RETURN_PATH = "/dashboard";

export function dashboardEntriesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.entries.dashboard(),
    queryFn: ({ signal }) =>
      runProtectedRequest(
        () => getDashboardEntries(signal),
        DASHBOARD_RETURN_PATH,
      ),
    staleTime: DASHBOARD_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}

export function useDashboardEntries() {
  return useQuery(dashboardEntriesQueryOptions());
}
