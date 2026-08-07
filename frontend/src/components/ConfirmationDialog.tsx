import { useEffect, useId, useRef, type KeyboardEvent } from "react";

import { FeedbackMessage } from "./FeedbackMessage";

export type ConfirmationDialogProps = {
  title: string;
  description: string;
  confirmLabel: string;
  pendingLabel?: string;
  cancelLabel?: string;
  isPending?: boolean;
  errorMessage?: string | undefined;
  danger?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
};

export function ConfirmationDialog({
  title,
  description,
  confirmLabel,
  pendingLabel = "Working…",
  cancelLabel = "Cancel",
  isPending = false,
  errorMessage,
  danger = false,
  onCancel,
  onConfirm,
}: ConfirmationDialogProps) {
  const titleId = useId();
  const descriptionId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const returnTargetRef = useRef<HTMLElement | undefined>(undefined);

  useEffect(() => {
    returnTargetRef.current =
      document.activeElement instanceof HTMLElement
        ? document.activeElement
        : undefined;

    return () => {
      requestAnimationFrame(() => {
        const returnTarget = returnTargetRef.current;
        if (returnTarget?.isConnected) returnTarget.focus();
      });
    };
  }, []);

  useEffect(() => {
    if (isPending) {
      dialogRef.current?.focus();
    } else {
      cancelRef.current?.focus();
    }
  }, [isPending]);

  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>): void {
    if (event.key === "Escape" && !isPending) {
      event.preventDefault();
      onCancel();
      return;
    }
    if (event.key === "Tab") {
      keepFocusInDialog(event, dialogRef.current);
    }
  }

  return (
    <div className="dialog-backdrop">
      <div
        aria-describedby={descriptionId}
        aria-labelledby={titleId}
        aria-modal="true"
        className="delete-dialog"
        ref={dialogRef}
        role="alertdialog"
        tabIndex={-1}
        onKeyDown={handleKeyDown}
      >
        <h2 id={titleId}>{title}</h2>
        <p id={descriptionId}>{description}</p>
        {errorMessage === undefined ? null : (
          <FeedbackMessage message={errorMessage} tone="error" />
        )}
        <div className="delete-dialog__actions">
          <button
            ref={cancelRef}
            type="button"
            disabled={isPending}
            onClick={onCancel}
          >
            {cancelLabel}
          </button>
          <button
            className={danger ? "button--danger" : undefined}
            type="button"
            disabled={isPending}
            onClick={onConfirm}
          >
            {isPending ? pendingLabel : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

function keepFocusInDialog(
  event: KeyboardEvent<HTMLDivElement>,
  dialog: HTMLDivElement | null,
): void {
  if (dialog === null) return;

  const controls = Array.from(
    dialog.querySelectorAll<HTMLElement>(
      'button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])',
    ),
  );
  const first = controls[0];
  const last = controls.at(-1);
  if (first === undefined || last === undefined) {
    event.preventDefault();
    dialog.focus();
    return;
  }

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
