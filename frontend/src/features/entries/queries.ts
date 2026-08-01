import {
  mutationOptions,
  queryOptions,
  type QueryClient,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { shouldRetryQuery } from "../../app/queryClient";
import { queryKeys } from "../../lib/queryKeys";
import type {
  CheckInEntryRequest,
  CreateEntryRequest,
  UpdateEntryRequest,
} from "../../types/api";
import { runProtectedRequest } from "../auth/sessionExpiry";
import {
  checkInEntry,
  createEntry,
  deleteEntry,
  getDashboardEntries,
  getEntry,
  updateEntry,
} from "./api";

const DASHBOARD_STALE_TIME_MS = 30 * 1_000;
const DASHBOARD_RETURN_PATH = "/dashboard";

export function dashboardEntriesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.entries.dashboard(),
    queryFn: ({ signal }) =>
      runProtectedRequest(
        () => getDashboardEntries(signal),
        DASHBOARD_RETURN_PATH,
      ),
    staleTime: DASHBOARD_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}

export function useDashboardEntries() {
  return useQuery(dashboardEntriesQueryOptions());
}

export function entryDetailQueryOptions(entryId: string) {
  return queryOptions({
    queryKey: queryKeys.entries.detail(entryId),
    queryFn: ({ signal }) =>
      runProtectedRequest(
        () => getEntry(entryId, signal),
        entryDetailReturnPath(entryId),
      ),
    staleTime: DASHBOARD_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}

export function useEntryDetail(entryId: string) {
  return useQuery(entryDetailQueryOptions(entryId));
}

export function createEntryMutationOptions(queryClient: QueryClient) {
  return mutationOptions({
    mutationFn: (payload: CreateEntryRequest) =>
      runProtectedRequest(() => createEntry(payload), "/entries/new"),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: queryKeys.entries.dashboard(),
      });
    },
    retry: false,
  });
}

export function useCreateEntryMutation() {
  const queryClient = useQueryClient();
  return useMutation(createEntryMutationOptions(queryClient));
}

export function updateEntryMutationOptions(
  queryClient: QueryClient,
  entryId: string,
) {
  return mutationOptions({
    mutationFn: (payload: UpdateEntryRequest) =>
      runProtectedRequest(
        () => updateEntry(entryId, payload),
        `${entryDetailReturnPath(entryId)}/edit`,
      ),
    onSuccess: async (response) => {
      queryClient.setQueryData(queryKeys.entries.detail(entryId), response);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.entries.detail(entryId),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.entries.dashboard(),
        }),
      ]);
    },
    retry: false,
  });
}

export function useUpdateEntryMutation(entryId: string) {
  const queryClient = useQueryClient();
  return useMutation(updateEntryMutationOptions(queryClient, entryId));
}

export function deleteEntryMutationOptions(
  queryClient: QueryClient,
  entryId: string,
) {
  return mutationOptions({
    mutationFn: () =>
      runProtectedRequest(
        () => deleteEntry(entryId),
        entryDetailReturnPath(entryId),
      ),
    onSuccess: async () => {
      queryClient.removeQueries({
        queryKey: queryKeys.entries.detail(entryId),
      });
      await queryClient.invalidateQueries({
        queryKey: queryKeys.entries.dashboard(),
      });
    },
    retry: false,
  });
}

export function useDeleteEntryMutation(entryId: string) {
  const queryClient = useQueryClient();
  return useMutation(deleteEntryMutationOptions(queryClient, entryId));
}

export function checkInEntryMutationOptions(
  queryClient: QueryClient,
  entryId: string,
) {
  return mutationOptions({
    mutationFn: (payload: CheckInEntryRequest) =>
      runProtectedRequest(
        () => checkInEntry(entryId, payload),
        `${entryDetailReturnPath(entryId)}/check-in`,
      ),
    onSuccess: async (response) => {
      queryClient.setQueryData(queryKeys.entries.detail(entryId), response);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: queryKeys.entries.dashboard(),
        }),
        queryClient.invalidateQueries({
          queryKey: queryKeys.stats.all(),
        }),
      ]);
    },
    retry: false,
  });
}

export function useCheckInEntryMutation(entryId: string) {
  const queryClient = useQueryClient();
  return useMutation(checkInEntryMutationOptions(queryClient, entryId));
}

function entryDetailReturnPath(entryId: string): string {
  return `/entries/${encodeURIComponent(entryId)}`;
}
