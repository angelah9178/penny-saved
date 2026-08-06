import { QueryClient } from "@tanstack/react-query";
import { describe, expect, it } from "vitest";

import { queryKeys } from "../../lib/queryKeys";
import { invalidateOpportunityCostData } from "./cache";

describe("invalidateOpportunityCostData", () => {
  it("invalidates the example list and every statistics range", async () => {
    const queryClient = new QueryClient();
    const exampleKey = queryKeys.opportunityCosts.list();
    const thisMonthKey = queryKeys.stats.summary("this_month");
    const allTimeKey = queryKeys.stats.summary("all_time");
    queryClient.setQueryData(exampleKey, "examples");
    queryClient.setQueryData(thisMonthKey, "this month");
    queryClient.setQueryData(allTimeKey, "all time");

    await invalidateOpportunityCostData(queryClient);

    expect(queryClient.getQueryState(exampleKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(thisMonthKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(allTimeKey)?.isInvalidated).toBe(true);
  });
});
