import {
  apiErrorFromResponse,
  invalidResponseApiError,
  networkApiError,
} from "./errors";

const DEFAULT_API_BASE_URL = "/api";

export type ApiFetchOptions = Omit<
  RequestInit,
  "body" | "credentials" | "headers"
> & {
  body?: unknown;
  headers?: HeadersInit;
};

export async function apiFetch<T>(
  endpoint: string,
  options: ApiFetchOptions = {},
): Promise<T> {
  const { body, headers: callerHeaders, ...requestOptions } = options;
  const headers = new Headers(callerHeaders);
  const hasBody = body !== undefined;

  headers.set("Accept", "application/json");

  if (hasBody) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;

  try {
    response = await fetch(buildApiUrl(endpoint), {
      ...requestOptions,
      credentials: "include",
      headers,
      ...(hasBody ? { body: JSON.stringify(body) } : {}),
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }

    throw networkApiError();
  }

  if (!response.ok) {
    throw await apiErrorFromResponse(response);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw invalidResponseApiError(response.status);
  }
}

function buildApiUrl(endpoint: string): string {
  const configuredBaseUrl: unknown = import.meta.env.VITE_API_BASE_URL;
  const baseUrl =
    typeof configuredBaseUrl !== "string" || configuredBaseUrl.trim() === ""
      ? DEFAULT_API_BASE_URL
      : configuredBaseUrl;

  return `${baseUrl.replace(/\/+$/, "")}/${endpoint.replace(/^\/+/, "")}`;
}

function isAbortError(error: unknown): boolean {
  return (
    (error instanceof DOMException && error.name === "AbortError") ||
    (error instanceof Error && error.name === "AbortError")
  );
}
