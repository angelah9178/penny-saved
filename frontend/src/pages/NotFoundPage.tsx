import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <>
      <h1>Page not found</h1>
      <p>We could not find the page you requested.</p>
      <Link to="/">Go to A Penny Saved</Link>
    </>
  );
}
