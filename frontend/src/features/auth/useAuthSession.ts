import { useQuery } from "@tanstack/react-query";

import { ApiError } from "../../api/errors";
import type { User } from "../../types/api";
import { currentUserQueryOptions } from "./queries";

export type AuthSessionState =
  | { status: "pending" }
  | { status: "authenticated"; user: User }
  | { status: "guest" }
  | { status: "error"; error: Error; retry: () => void };

export function useAuthSession(): AuthSessionState {
  const query = useQuery(currentUserQueryOptions());

  if (query.isPending) {
    return { status: "pending" };
  }

  if (query.isError) {
    if (query.error instanceof ApiError && query.error.status === 401) {
      return { status: "guest" };
    }

    return {
      status: "error",
      error: query.error,
      retry: () => {
        void query.refetch();
      },
    };
  }

  return { status: "authenticated", user: query.data.user };
}
