import { useState } from "react";

import { ApiError } from "../../api/errors";
import { ConfirmationDialog } from "../../components/ConfirmationDialog";
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
  const [isOpen, setIsOpen] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string>();

  function closeDialog(): void {
    setIsOpen(false);
    setErrorMessage(undefined);
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
        type="button"
        onClick={() => setIsOpen(true)}
      >
        Delete {example.label}
      </button>

      {isOpen ? (
        <ConfirmationDialog
          danger
          confirmLabel="Delete example"
          description="This permanently removes the example from your savings comparisons and cannot be undone."
          errorMessage={errorMessage}
          isPending={deletion.isPending}
          pendingLabel="Deleting example…"
          title={`Delete ${example.label}?`}
          onCancel={closeDialog}
          onConfirm={() => void confirmDeletion()}
        />
      ) : null}
    </>
  );
}
