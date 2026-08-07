import { Link, useLocation } from "react-router-dom";

import { AuthForm } from "../features/auth/AuthForm";
import { FeedbackMessage } from "../components/FeedbackMessage";

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
        <FeedbackMessage
          message="Your session expired. Please sign in again."
          tone="status"
          className="request-state"
        />
      ) : null}
      <AuthForm mode="login" />
      <Link to="/signup">Create an account</Link>
    </>
  );
}
