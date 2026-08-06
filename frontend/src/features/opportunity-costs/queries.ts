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
  CreateOpportunityCostExampleRequest,
  UpdateOpportunityCostExampleRequest,
} from "../../types/api";
import { runProtectedRequest } from "../auth/sessionExpiry";
import {
  createOpportunityCostExample,
  deleteOpportunityCostExample,
  getOpportunityCostExamples,
  updateOpportunityCostExample,
} from "./api";
import { invalidateOpportunityCostData } from "./cache";

const OPPORTUNITY_COST_STALE_TIME_MS = 30 * 1_000;
const OPPORTUNITY_COST_RETURN_PATH = "/settings/opportunity-costs";

export type UpdateOpportunityCostExampleVariables = {
  exampleId: string;
  payload: UpdateOpportunityCostExampleRequest;
};

export function opportunityCostExamplesQueryOptions() {
  return queryOptions({
    queryKey: queryKeys.opportunityCosts.list(),
    queryFn: ({ signal }) =>
      runProtectedRequest(
        () => getOpportunityCostExamples(signal),
        OPPORTUNITY_COST_RETURN_PATH,
      ),
    staleTime: OPPORTUNITY_COST_STALE_TIME_MS,
    retry: shouldRetryQuery,
  });
}

export function useOpportunityCostExamples() {
  return useQuery(opportunityCostExamplesQueryOptions());
}

export function createOpportunityCostExampleMutationOptions(
  queryClient: QueryClient,
) {
  return mutationOptions({
    mutationFn: (payload: CreateOpportunityCostExampleRequest) =>
      runProtectedRequest(
        () => createOpportunityCostExample(payload),
        OPPORTUNITY_COST_RETURN_PATH,
      ),
    onSuccess: () => invalidateOpportunityCostData(queryClient),
    retry: false,
  });
}

export function useCreateOpportunityCostExampleMutation() {
  const queryClient = useQueryClient();
  return useMutation(createOpportunityCostExampleMutationOptions(queryClient));
}

export function updateOpportunityCostExampleMutationOptions(
  queryClient: QueryClient,
) {
  return mutationOptions({
    mutationFn: ({
      exampleId,
      payload,
    }: UpdateOpportunityCostExampleVariables) =>
      runProtectedRequest(
        () => updateOpportunityCostExample(exampleId, payload),
        OPPORTUNITY_COST_RETURN_PATH,
      ),
    onSuccess: () => invalidateOpportunityCostData(queryClient),
    retry: false,
  });
}

export function useUpdateOpportunityCostExampleMutation() {
  const queryClient = useQueryClient();
  return useMutation(updateOpportunityCostExampleMutationOptions(queryClient));
}

export function deleteOpportunityCostExampleMutationOptions(
  queryClient: QueryClient,
) {
  return mutationOptions({
    mutationFn: (exampleId: string) =>
      runProtectedRequest(
        () => deleteOpportunityCostExample(exampleId),
        OPPORTUNITY_COST_RETURN_PATH,
      ),
    onSuccess: () => invalidateOpportunityCostData(queryClient),
    retry: false,
  });
}

export function useDeleteOpportunityCostExampleMutation() {
  const queryClient = useQueryClient();
  return useMutation(deleteOpportunityCostExampleMutationOptions(queryClient));
}
