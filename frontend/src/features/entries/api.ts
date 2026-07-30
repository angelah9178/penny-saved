import { apiFetch } from "../../api/client";
import type { DashboardEntries } from "../../types/api";

export function getDashboardEntries(
  signal?: AbortSignal,
): Promise<DashboardEntries> {
  return apiFetch<DashboardEntries>(
    "/entries",
    signal === undefined ? {} : { signal },
  );
}
