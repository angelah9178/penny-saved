import { Navigate } from "react-router-dom";

import { useAuthSession } from "../features/auth/useAuthSession";

export function IndexRoute() {
  const session = useAuthSession();

  return (
    <Navigate
      to={session.status === "authenticated" ? "/dashboard" : "/login"}
      replace
    />
  );
}
