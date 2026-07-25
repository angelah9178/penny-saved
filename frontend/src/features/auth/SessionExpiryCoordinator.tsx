import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { queryKeys } from "../../lib/queryKeys";
import type { AuthResponse } from "../../types/api";
import { subscribeToSessionExpiry } from "./sessionExpiry";

export function SessionExpiryCoordinator() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  useEffect(
    () =>
      subscribeToSessionExpiry(({ returnTo }) => {
        queryClient.clear();
        queryClient.setQueryData<AuthResponse | null>(
          queryKeys.auth.me(),
          null,
        );
        void navigate("/login", {
          replace: true,
          state: { returnTo, sessionExpired: true },
        });
      }),
    [navigate, queryClient],
  );

  return null;
}
