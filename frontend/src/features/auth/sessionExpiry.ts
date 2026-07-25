import { ApiError } from "../../api/errors";
import { safeReturnPath } from "../../routes/returnPath";

export type SessionExpiryEvent = {
  returnTo: string;
};

type SessionExpiryListener = (event: SessionExpiryEvent) => void;

const listeners = new Set<SessionExpiryListener>();
let expiryActive = false;

export async function runProtectedRequest<T>(
  request: () => Promise<T>,
  returnTo: string,
): Promise<T> {
  try {
    return await request();
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      reportSessionExpiry(returnTo);
    }
    throw error;
  }
}

export function subscribeToSessionExpiry(
  listener: SessionExpiryListener,
): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function resetSessionExpiry(): void {
  expiryActive = false;
}

function reportSessionExpiry(returnTo: string): void {
  if (expiryActive) {
    return;
  }

  expiryActive = true;
  const event = { returnTo: safeReturnPath(returnTo) };
  for (const listener of listeners) {
    listener(event);
  }
}
