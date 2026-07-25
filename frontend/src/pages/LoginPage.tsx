import { Link, useLocation } from "react-router-dom";

import { AuthForm } from "../features/auth/AuthForm";

export function LoginPage() {
  const location = useLocation();
  const locationState: unknown = location.state;
  const sessionExpired =
    typeof locationState === "object" &&
    locationState !== null &&
    "sessionExpired" in locationState &&
    locationState.sessionExpired === true;

  return (
    <>
      <h1>Log in</h1>
      {sessionExpired ? (
        <div className="request-state" role="status">
          Your session expired. Please sign in again.
        </div>
      ) : null}
      <AuthForm mode="login" />
      <Link to="/signup">Create an account</Link>
    </>
  );
}
