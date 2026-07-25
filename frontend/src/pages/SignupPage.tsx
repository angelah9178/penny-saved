import { Link } from "react-router-dom";

import { AuthForm } from "../features/auth/AuthForm";

export function SignupPage() {
  return (
    <>
      <h1>Create your account</h1>
      <AuthForm mode="signup" />
      <Link to="/login">Log in to an existing account</Link>
    </>
  );
}
