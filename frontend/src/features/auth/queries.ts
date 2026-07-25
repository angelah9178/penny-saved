import { queryOptions } from "@tanstack/react-query";

import { shouldRetryQuery } from "../../app/queryClient";
import { queryKeys } from "../../lib/queryKeys";
import { getCurrentUser } from "./api";

const AUTH_STALE_TIME_MS = 5 * 60 * 1_000;

export function currentUserQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.auth.me(),
    queryFn: ({ signal }) => getCurrentUser(signal),
    staleTime: AUTH_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}
