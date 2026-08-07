import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { ApiError } from "../../api/errors";
import { ConfirmationDialog } from "../../components/ConfirmationDialog";
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
  const [isOpen, setIsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();

  function closeDialog(): void {
    setIsOpen(false);
    setErrorMessage(undefined);
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
        type="button"
        onClick={() => setIsOpen(true)}
      >
        Delete
      </button>

      {isOpen ? (
        <ConfirmationDialog
          danger
          confirmLabel="Delete entry"
          description="This permanently removes the entry and cannot be undone."
          errorMessage={errorMessage}
          isPending={deletion.isPending}
          pendingLabel="Deleting…"
          title={`Delete ${entry.item_name}?`}
          onCancel={closeDialog}
          onConfirm={() => void confirmDeletion()}
        />
      ) : null}
    </>
  );
}
