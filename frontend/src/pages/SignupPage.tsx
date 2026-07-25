import { Link } from "react-router-dom";

export function SignupPage() {
  return (
    <>
      <h1>Create your account</h1>
      <p>The signup form will be added in Commit 4.</p>
      <Link to="/login">Log in to an existing account</Link>
    </>
  );
}
