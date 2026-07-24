import { QueryClient } from "@tanstack/react-query";

import { ApiError } from "../api/errors";

const MAX_QUERY_RETRIES = 2;
const INITIAL_RETRY_DELAY_MS = 500;
const MAX_RETRY_DELAY_MS = 2_000;

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 0,
        refetchOnWindowFocus: false,
        retry: shouldRetryQuery,
        retryDelay: queryRetryDelay,
      },
      mutations: {
        retry: false,
      },
    },
  });
}

export function shouldRetryQuery(failureCount: number, error: Error): boolean {
  if (failureCount >= MAX_QUERY_RETRIES) {
    return false;
  }

  if (!(error instanceof ApiError)) {
    return true;
  }

  return error.status === 0 || error.status >= 500;
}

function queryRetryDelay(attemptIndex: number): number {
  return Math.min(
    INITIAL_RETRY_DELAY_MS * 2 ** attemptIndex,
    MAX_RETRY_DELAY_MS,
  );
}
