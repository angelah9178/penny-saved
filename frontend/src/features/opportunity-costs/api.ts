import { apiFetch } from "../../api/client";
import type {
  CreateOpportunityCostExampleRequest,
  OpportunityCostExampleResponse,
  OpportunityCostExamplesResponse,
  UpdateOpportunityCostExampleRequest,
} from "../../types/api";

export function getOpportunityCostExamples(
  signal?: AbortSignal,
): Promise<OpportunityCostExamplesResponse> {
  return apiFetch<OpportunityCostExamplesResponse>(
    "/opportunity-cost-examples",
    signal === undefined ? {} : { signal },
  );
}

export function createOpportunityCostExample(
  payload: CreateOpportunityCostExampleRequest,
): Promise<OpportunityCostExampleResponse> {
  return apiFetch<OpportunityCostExampleResponse>(
    "/opportunity-cost-examples",
    { method: "POST", body: payload },
  );
}

export function updateOpportunityCostExample(
  exampleId: string,
  payload: UpdateOpportunityCostExampleRequest,
): Promise<OpportunityCostExampleResponse> {
  return apiFetch<OpportunityCostExampleResponse>(examplePath(exampleId), {
    method: "PATCH",
    body: payload,
  });
}

export function deleteOpportunityCostExample(exampleId: string): Promise<void> {
  return apiFetch<void>(examplePath(exampleId), { method: "DELETE" });
}

function examplePath(exampleId: string): string {
  return `/opportunity-cost-examples/${encodeURIComponent(exampleId)}`;
}
