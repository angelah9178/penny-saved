import { useCallback, useEffect } from "react";
import { useBeforeUnload, useBlocker } from "react-router-dom";

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
    <div className="unsaved-changes" role="alertdialog" aria-modal="true">
      <h2>Leave without saving?</h2>
      <p>Your entry has unsaved changes. Leaving will discard them.</p>
      <div className="unsaved-changes__actions">
        <button type="button" onClick={() => blocker.reset()}>
          Stay on this page
        </button>
        <button type="button" onClick={() => blocker.proceed()}>
          Leave without saving
        </button>
      </div>
    </div>
  );
}
