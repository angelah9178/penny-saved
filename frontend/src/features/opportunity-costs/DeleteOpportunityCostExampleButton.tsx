import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { ApiError } from "../../api/errors";
import type { OpportunityCostExample } from "../../types/api";
import { useDeleteOpportunityCostExampleMutation } from "./queries";

export type DeleteOpportunityCostExampleButtonProps = {
  example: OpportunityCostExample;
  onDeleted?: ((example: OpportunityCostExample) => void) | undefined;
  onStale?:
    | ((example: OpportunityCostExample) => Promise<void> | void)
    | undefined;
};

export function DeleteOpportunityCostExampleButton({
  example,
  onDeleted,
  onStale,
}: DeleteOpportunityCostExampleButtonProps) {
  const deletion = useDeleteOpportunityCostExampleMutation();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();

  useEffect(() => {
    if (isOpen) cancelRef.current?.focus();
  }, [isOpen]);

  function closeAndRestoreFocus(): void {
    setIsOpen(false);
    setErrorMessage(undefined);
    requestAnimationFrame(() => triggerRef.current?.focus());
  }

  async function confirmDeletion(): Promise<void> {
    setErrorMessage(undefined);
    try {
      await deletion.mutateAsync(example.id);
      setIsOpen(false);
      onDeleted?.(example);
    } catch (error) {
      if (
        error instanceof ApiError &&
        (error.status === 403 || error.status === 404)
      ) {
        await onStale?.(example);
        setIsOpen(false);
        return;
      }

      setErrorMessage("We could not delete this example. Please try again.");
    }
  }

  return (
    <>
      <button
        className="button--danger"
        ref={triggerRef}
        type="button"
        onClick={() => setIsOpen(true)}
      >
        Delete {example.label}
      </button>

      {isOpen ? (
        <div className="dialog-backdrop">
          <div
            aria-labelledby={`delete-example-${example.id}-title`}
            aria-modal="true"
            className="delete-dialog"
            ref={dialogRef}
            role="alertdialog"
            onKeyDown={(event) => {
              if (event.key === "Escape" && !deletion.isPending) {
                event.preventDefault();
                closeAndRestoreFocus();
              }
              if (event.key === "Tab") {
                keepFocusInDialog(event, dialogRef.current);
              }
            }}
          >
            <h2 id={`delete-example-${example.id}-title`}>
              Delete {example.label}?
            </h2>
            <p>
              This permanently removes the example from your savings comparisons
              and cannot be undone.
            </p>
            {errorMessage === undefined ? null : (
              <p className="request-state request-state--error" role="alert">
                {errorMessage}
              </p>
            )}
            <div className="delete-dialog__actions">
              <button
                ref={cancelRef}
                type="button"
                disabled={deletion.isPending}
                onClick={closeAndRestoreFocus}
              >
                Cancel
              </button>
              <button
                className="button--danger"
                type="button"
                disabled={deletion.isPending}
                onClick={() => void confirmDeletion()}
              >
                {deletion.isPending ? "Deleting example…" : "Delete example"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function keepFocusInDialog(
  event: KeyboardEvent,
  dialog: HTMLDivElement | null,
): void {
  if (dialog === null) return;

  const controls = Array.from(
    dialog.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
  );
  const first = controls[0];
  const last = controls.at(-1);
  if (first === undefined || last === undefined) return;

  if (event.shiftKey && document.activeElement === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && document.activeElement === last) {
    event.preventDefault();
    first.focus();
  }
}
