import { useQuery } from "@tanstack/react-query";

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
    return {
      status: "error",
      error: query.error,
      retry: () => {
        void query.refetch();
      },
    };
  }

  if (query.data === null) {
    return { status: "guest" };
  }

  return { status: "authenticated", user: query.data.user };
}
