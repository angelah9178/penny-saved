import { useEffect, useRef } from "react";
import { Link, useRevalidator } from "react-router-dom";

import { PageShell } from "../components/PageShell";

export function RouteErrorPage() {
  const headingRef = useRef<HTMLHeadingElement>(null);
  const revalidator = useRevalidator();

  useEffect(() => {
    document.title = "Page error | A Penny Saved";
    headingRef.current?.focus();
  }, []);

  return (
    <PageShell>
      <div className="request-state request-state--error" role="alert">
        <h1 ref={headingRef} tabIndex={-1}>
          We could not open this page
        </h1>
        <p>An unexpected problem prevented this page from loading.</p>
        <div className="route-error__actions">
          <button
            type="button"
            disabled={revalidator.state !== "idle"}
            onClick={() => {
              void revalidator.revalidate();
            }}
          >
            {revalidator.state === "idle" ? "Try again" : "Trying again…"}
          </button>
          <Link to="/">Return home</Link>
        </div>
      </div>
    </PageShell>
  );
}
