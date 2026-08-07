import { forwardRef } from "react";

export type FeedbackMessageProps = {
  message: string;
  tone: "error" | "success" | "status";
  className?: string;
  focusable?: boolean;
};

/** Shared semantics for application feedback; wording remains feature-specific. */
export const FeedbackMessage = forwardRef<HTMLDivElement, FeedbackMessageProps>(
  function FeedbackMessage(
    { message, tone, className, focusable = false },
    ref,
  ) {
    const classes = [
      tone === "status" ? undefined : "request-state",
      tone === "error" ? "request-state--error" : undefined,
      tone === "success" ? "request-state--success" : undefined,
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <div
        aria-atomic="true"
        aria-live={tone === "error" ? "assertive" : "polite"}
        className={classes || undefined}
        ref={ref}
        role={tone === "error" ? "alert" : "status"}
        tabIndex={focusable ? -1 : undefined}
      >
        {message}
      </div>
    );
  },
);
