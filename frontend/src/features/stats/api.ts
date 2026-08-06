import { apiFetch } from "../../api/client";
import type { StatsRange, StatsSummary } from "../../types/api";

export function getStatsSummary(
  range: StatsRange,
  signal?: AbortSignal,
): Promise<StatsSummary> {
  const query = new URLSearchParams({ range });
  return apiFetch<StatsSummary>(
    `/stats/summary?${query.toString()}`,
    signal === undefined ? {} : { signal },
  );
}
