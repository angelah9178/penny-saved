import type { QueryClient } from "@tanstack/react-query";

import { queryKeys } from "../../lib/queryKeys";
import { invalidateStatsQueries } from "../stats/cache";

export async function invalidateOpportunityCostData(
  queryClient: QueryClient,
): Promise<void> {
  await Promise.all([
    queryClient.invalidateQueries({
      queryKey: queryKeys.opportunityCosts.list(),
    }),
    invalidateStatsQueries(queryClient),
  ]);
}
