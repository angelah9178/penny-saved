import { queryOptions } from "@tanstack/react-query";

import { ApiError } from "../../api/errors";
import { shouldRetryQuery } from "../../app/queryClient";
import { queryKeys } from "../../lib/queryKeys";
import { getCurrentUser } from "./api";

const AUTH_STALE_TIME_MS = 5 * 60 * 1_000;

export function currentUserQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.auth.me(),
    queryFn: ({ signal }) => getCurrentSession(signal),
    staleTime: AUTH_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}

async function getCurrentSession(signal: AbortSignal) {
  try {
    return await getCurrentUser(signal);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }

    throw error;
  }
}
