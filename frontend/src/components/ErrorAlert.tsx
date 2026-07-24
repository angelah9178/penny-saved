export type ErrorAlertProps = {
  message: string;
  onRetry?: () => void;
};

export function ErrorAlert({ message, onRetry }: ErrorAlertProps) {
  return (
    <div className="request-state request-state--error" role="alert">
      <p>{message}</p>
      {onRetry === undefined ? null : (
        <button type="button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
