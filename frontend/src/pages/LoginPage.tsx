import { Link } from "react-router-dom";

import { AuthForm } from "../features/auth/AuthForm";

export function LoginPage() {
  return (
    <>
      <h1>Log in</h1>
      <AuthForm mode="login" />
      <Link to="/signup">Create an account</Link>
    </>
  );
}
