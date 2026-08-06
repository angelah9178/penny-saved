import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "../../lib/queryKeys";

export function invalidateStatsQueries(
  queryClient: QueryClient,
): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: queryKeys.stats.all() });
}
