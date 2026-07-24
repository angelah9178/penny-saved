import type { ApiErrorResponse } from "../types/api";

const FALLBACK_ERROR_CODE = "request_failed";
const FALLBACK_ERROR_MESSAGE = "The request could not be completed.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields?: Record<string, string>;

  constructor(
    status: number,
    code: string,
    message: string,
    fields?: Record<string, string>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;

    if (fields !== undefined) {
      this.fields = fields;
    }
  }
}

export async function apiErrorFromResponse(
  response: Response,
): Promise<ApiError> {
  let payload: unknown;

  try {
    payload = await response.json();
  } catch {
    return fallbackApiError(response.status);
  }

  if (!isApiErrorResponse(payload)) {
    return fallbackApiError(response.status);
  }

  return new ApiError(
    response.status,
    payload.error.code,
    payload.error.message,
    payload.error.fields,
  );
}

export function networkApiError(): ApiError {
  return new ApiError(
    0,
    "network_error",
    "Unable to reach the server. Please try again.",
  );
}

export function invalidResponseApiError(status: number): ApiError {
  return new ApiError(
    status,
    "invalid_response",
    "The server returned an invalid response.",
  );
}

function fallbackApiError(status: number): ApiError {
  return new ApiError(status, FALLBACK_ERROR_CODE, FALLBACK_ERROR_MESSAGE);
}

function isApiErrorResponse(value: unknown): value is ApiErrorResponse {
  if (!isRecord(value) || !isRecord(value.error)) {
    return false;
  }

  const { code, message, fields } = value.error;

  return (
    typeof code === "string" &&
    code.length > 0 &&
    typeof message === "string" &&
    message.length > 0 &&
    (fields === undefined || isStringRecord(fields))
  );
}

function isStringRecord(value: unknown): value is Record<string, string> {
  return (
    isRecord(value) &&
    Object.values(value).every(
      (fieldMessage) => typeof fieldMessage === "string",
    )
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
