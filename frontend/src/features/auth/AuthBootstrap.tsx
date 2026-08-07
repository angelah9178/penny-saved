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
    return (
      <AuthBootstrapError
        isRetrying={session.isRetrying}
        onRetry={session.retry}
      />
    );
  }

  return children;
}

function AuthBootstrapError({
  isRetrying,
  onRetry,
}: {
  isRetrying: boolean;
  onRetry: () => void;
}) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.focus();
  }, []);

  return (
    <div ref={containerRef} tabIndex={-1}>
      <ErrorAlert
        message="We could not check your session. Please try again."
        isRetrying={isRetrying}
        retryLabel="Retry session check"
        retryingLabel="Retrying session check…"
        onRetry={onRetry}
      />
    </div>
  );
}
