import { apiFetch } from "../../api/client";
import type {
  CreateEntryRequest,
  DashboardEntries,
  EntryResponse,
  UpdateEntryRequest,
} from "../../types/api";

export function getDashboardEntries(
  signal?: AbortSignal,
): Promise<DashboardEntries> {
  return apiFetch<DashboardEntries>(
    "/entries",
    signal === undefined ? {} : { signal },
  );
}

export function getEntry(
  entryId: string,
  signal?: AbortSignal,
): Promise<EntryResponse> {
  return apiFetch<EntryResponse>(
    entryPath(entryId),
    signal === undefined ? {} : { signal },
  );
}

export function createEntry(
  payload: CreateEntryRequest,
): Promise<EntryResponse> {
  return apiFetch<EntryResponse>("/entries", {
    method: "POST",
    body: payload,
  });
}

export function updateEntry(
  entryId: string,
  payload: UpdateEntryRequest,
): Promise<EntryResponse> {
  return apiFetch<EntryResponse>(entryPath(entryId), {
    method: "PATCH",
    body: payload,
  });
}

export function deleteEntry(entryId: string): Promise<void> {
  return apiFetch<void>(entryPath(entryId), { method: "DELETE" });
}

function entryPath(entryId: string): string {
  return `/entries/${encodeURIComponent(entryId)}`;
}
