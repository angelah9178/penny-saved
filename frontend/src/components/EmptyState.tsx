import { useId } from "react";

export type EmptyStateProps = {
  title: string;
  message: string;
};

export function EmptyState({ title, message }: EmptyStateProps) {
  const titleId = useId();

  return (
    <section
      className="request-state request-state--empty"
      aria-labelledby={titleId}
    >
      <h2 id={titleId}>{title}</h2>
      <p>{message}</p>
    </section>
  );
}
