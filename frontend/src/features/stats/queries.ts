import {
  keepPreviousData,
  queryOptions,
  useQuery,
} from "@tanstack/react-query";

import { shouldRetryQuery } from "../../app/queryClient";
import { queryKeys } from "../../lib/queryKeys";
import type { StatsRange } from "../../types/api";
import { runProtectedRequest } from "../auth/sessionExpiry";
import { getStatsSummary } from "./api";

const STATS_STALE_TIME_MS = 30 * 1_000;
const STATS_RETURN_PATH = "/dashboard";

export function statsSummaryQueryOptions(range: StatsRange) {
  return queryOptions({
    queryKey: queryKeys.stats.summary(range),
    queryFn: ({ signal }) =>
      runProtectedRequest(
        () => getStatsSummary(range, signal),
        STATS_RETURN_PATH,
      ),
    placeholderData: keepPreviousData,
    staleTime: STATS_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}

export function useStatsSummary(range: StatsRange) {
  return useQuery(statsSummaryQueryOptions(range));
}
