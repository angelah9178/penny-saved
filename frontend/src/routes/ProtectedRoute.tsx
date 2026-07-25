import { Navigate, Outlet, useLocation } from "react-router-dom";

import { AuthBootstrap } from "../features/auth/AuthBootstrap";
import { useAuthSession } from "../features/auth/useAuthSession";

export function ProtectedRoute() {
  return (
    <AuthBootstrap>
      <ResolvedProtectedRoute />
    </AuthBootstrap>
  );
}

function ResolvedProtectedRoute() {
  const session = useAuthSession();
  const location = useLocation();

  if (session.status === "guest") {
    return (
      <Navigate
        to="/login"
        replace
        state={{
          returnTo: `${location.pathname}${location.search}${location.hash}`,
        }}
      />
    );
  }

  // This guard controls navigation only. Backend authorization remains mandatory.
  return <Outlet />;
}
