export type LoadingProps = {
  message?: string;
};

export function Loading({ message = "Loading…" }: LoadingProps) {
  return (
    <div
      className="request-state request-state--loading"
      role="status"
      aria-live="polite"
      aria-atomic="true"
    >
      <span className="loading-indicator" aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}
