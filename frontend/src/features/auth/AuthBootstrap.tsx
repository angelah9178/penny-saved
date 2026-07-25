import { useEffect, useRef, type ReactNode } from "react";

import { ErrorAlert } from "../../components/ErrorAlert";
import { Loading } from "../../components/Loading";
import { useAuthSession } from "./useAuthSession";

export type AuthBootstrapProps = {
  children: ReactNode;
};

export function AuthBootstrap({ children }: AuthBootstrapProps) {
  const session = useAuthSession();

  if (session.status === "pending") {
    return <Loading message="Checking your session…" />;
  }

  if (session.status === "error") {
    return <AuthBootstrapError onRetry={session.retry} />;
  }

  return children;
}

function AuthBootstrapError({ onRetry }: { onRetry: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  return (
    <div ref={containerRef} tabIndex={-1}>
      <ErrorAlert
        message="We could not check your session. Please try again."
        onRetry={onRetry}
      />
    </div>
  );
}
