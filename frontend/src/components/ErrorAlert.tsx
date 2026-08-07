export type ErrorAlertProps = {
  message: string;
  onRetry?: () => void;
  isRetrying?: boolean;
  retryLabel?: string;
  retryingLabel?: string;
};

export function ErrorAlert({
  message,
  onRetry,
  isRetrying = false,
  retryLabel = "Try again",
  retryingLabel = "Trying again…",
}: ErrorAlertProps) {
  return (
    <div className="request-state request-state--error" role="alert">
      <p>{message}</p>
      {onRetry === undefined ? null : (
        <button type="button" disabled={isRetrying} onClick={onRetry}>
          {isRetrying ? retryingLabel : retryLabel}
        </button>
      )}
    </div>
  );
}
