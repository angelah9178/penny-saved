import type { StatsRange } from "../types/api";

export const queryKeys = {
  auth: {
    me: () => ["auth", "me"] as const,
  },
  entries: {
    dashboard: () => ["entries", "dashboard"] as const,
    detail: (entryId: string) => ["entries", "detail", entryId] as const,
  },
  stats: {
    summary: (range: StatsRange) => ["stats", "summary", range] as const,
  },
  opportunityCosts: {
    list: () => ["opportunity-costs", "list"] as const,
  },
} as const;
