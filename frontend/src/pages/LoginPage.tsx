import { Link } from "react-router-dom";

export function LoginPage() {
  return (
    <>
      <h1>Log in</h1>
      <p>The login form will be added in Commit 4.</p>
      <Link to="/signup">Create an account</Link>
    </>
  );
}
