import { useCallback, useEffect } from "react";
import { useBeforeUnload, useBlocker } from "react-router-dom";

import { ConfirmationDialog } from "./ConfirmationDialog";

export function UnsavedChangesPrompt({
  shouldBlock,
}: {
  shouldBlock: boolean;
}) {
  const blocker = useBlocker(shouldBlock);

  useEffect(() => {
    if (!shouldBlock && blocker.state === "blocked") {
      blocker.proceed();
    }
  }, [blocker, shouldBlock]);

  useBeforeUnload(
    useCallback(
      (event) => {
        if (!shouldBlock) {
          return;
        }
        event.preventDefault();
        event.returnValue = "";
      },
      [shouldBlock],
    ),
  );

  if (blocker.state !== "blocked") {
    return null;
  }

  return (
    <ConfirmationDialog
      cancelLabel="Stay on this page"
      confirmLabel="Leave without saving"
      description="Your entry has unsaved changes. Leaving will discard them."
      title="Leave without saving?"
      onCancel={() => blocker.reset()}
      onConfirm={() => blocker.proceed()}
    />
  );
}
