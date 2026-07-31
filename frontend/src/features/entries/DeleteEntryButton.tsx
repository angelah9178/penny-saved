import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import type { Entry } from "../../types/api";
import { useDeleteEntryMutation } from "./queries";

export function DeleteEntryButton({
  entry,
  onNotice,
}: {
  entry: Entry;
  onNotice?: ((message: string) => void) | undefined;
}) {
  const queryClient = useQueryClient();
  const deletion = useDeleteEntryMutation(entry.id);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();

  useEffect(() => {
    if (isOpen) {
      cancelRef.current?.focus();
    }
  }, [isOpen]);

  function closeAndRestoreFocus(): void {
    setIsOpen(false);
    setErrorMessage(undefined);
    requestAnimationFrame(() => triggerRef.current?.focus());
  }

  async function confirmDeletion(): Promise<void> {
    setErrorMessage(undefined);
    try {
      await deletion.mutateAsync();
      setIsOpen(false);
      onNotice?.(`${entry.item_name} was deleted.`);
    } catch (error) {
      if (error instanceof ApiError && error.code === "invalid_entry_status") {
        onNotice?.(
          `${entry.item_name} is no longer waiting and was not deleted.`,
        );
        setIsOpen(false);
        await Promise.all([
          queryClient.invalidateQueries({
            queryKey: queryKeys.entries.detail(entry.id),
          }),
          queryClient.invalidateQueries({
            queryKey: queryKeys.entries.dashboard(),
          }),
        ]);
        return;
      }

      setErrorMessage(
        error instanceof ApiError
          ? error.message
          : "We could not delete this entry. Please try again.",
      );
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
        Delete
      </button>

      {isOpen ? (
        <div className="dialog-backdrop">
          <div
            aria-labelledby={`delete-${entry.id}-title`}
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
            <h2 id={`delete-${entry.id}-title`}>Delete {entry.item_name}?</h2>
            <p>This permanently removes the entry and cannot be undone.</p>
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
                {deletion.isPending ? "Deleting…" : "Delete entry"}
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
  if (dialog === null) {
    return;
  }
  const controls = Array.from(
    dialog.querySelectorAll<HTMLButtonElement>("button:not(:disabled)"),
  );
  const first = controls[0];
  const last = controls.at(-1);
  if (first === undefined || last === undefined) {
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
