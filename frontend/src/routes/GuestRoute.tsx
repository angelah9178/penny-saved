import { Navigate, Outlet, useLocation } from "react-router-dom";

import { AuthBootstrap } from "../features/auth/AuthBootstrap";
import { useAuthSession } from "../features/auth/useAuthSession";
import { safeReturnPath } from "./returnPath";

export function GuestRoute() {
  return (
    <AuthBootstrap>
      <ResolvedGuestRoute />
    </AuthBootstrap>
  );
}

function ResolvedGuestRoute() {
  const session = useAuthSession();
  const location = useLocation();

  if (session.status === "authenticated") {
    const state: unknown = location.state;
    const returnTo =
      isRecord(state) && "returnTo" in state ? state.returnTo : undefined;

    return <Navigate to={safeReturnPath(returnTo)} replace />;
  }

  return <Outlet />;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
