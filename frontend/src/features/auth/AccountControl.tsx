import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";
import { useNavigate } from "react-router-dom";

import { queryKeys } from "../../lib/queryKeys";
import type { AuthResponse } from "../../types/api";
import { logout } from "./api";
import { resetSessionExpiry } from "./sessionExpiry";
import { useAuthSession } from "./useAuthSession";

export function AccountControl() {
  const session = useAuthSession();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const logoutInFlight = useRef(false);
  const mutation = useMutation({ mutationFn: logout });

  if (session.status !== "authenticated") {
    return null;
  }

  async function handleLogout() {
    if (logoutInFlight.current) {
      return;
    }

    logoutInFlight.current = true;
    try {
      await mutation.mutateAsync();
    } catch {
      // Local private-data cleanup is required even when server logout fails.
    } finally {
      queryClient.clear();
      queryClient.setQueryData<AuthResponse | null>(queryKeys.auth.me(), null);
      resetSessionExpiry();
      await navigate("/login", { replace: true });
      logoutInFlight.current = false;
    }
  }

  return (
    <div className="account-control">
      <span>{session.user.email}</span>
      <button
        type="button"
        disabled={mutation.isPending}
        onClick={() => {
          void handleLogout();
        }}
      >
        {mutation.isPending ? "Logging out…" : "Log out"}
      </button>
    </div>
  );
}
