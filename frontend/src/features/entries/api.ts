import { apiFetch } from "../../api/client";
import type {
  CheckInEntryRequest,
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

export function checkInEntry(
  entryId: string,
  payload: CheckInEntryRequest,
): Promise<EntryResponse> {
  return apiFetch<EntryResponse>(`${entryPath(entryId)}/check-in`, {
    method: "POST",
    body: payload,
  });
}

function entryPath(entryId: string): string {
  return `/entries/${encodeURIComponent(entryId)}`;
}
