import { useEffect, useId, useRef, useState } from "react";

import { ApiError } from "../../api/errors";
import type { EntryResponse, UpdateEntryCommentRequest } from "../../types/api";
import {
  entryCommentSchema,
  MAX_ENTRY_COMMENT_LENGTH,
} from "./commentFormValidation";

export type CommentEditorProps = {
  comment: string | null;
  onSubmit: (payload: UpdateEntryCommentRequest) => Promise<EntryResponse>;
};

export function CommentEditor({ comment, onSubmit }: CommentEditorProps) {
  const fieldId = useId();
  const feedbackRef = useRef<HTMLDivElement>(null);
  const submissionInFlight = useRef(false);
  const [value, setValue] = useState(comment ?? "");
  const [savedValue, setSavedValue] = useState(comment);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string>();
  const [confirmation, setConfirmation] = useState<string>();

  useEffect(() => {
    if (error !== undefined || confirmation !== undefined) {
      feedbackRef.current?.focus();
    }
  }, [confirmation, error]);

  async function submit() {
    if (submissionInFlight.current) return;
    setError(undefined);
    setConfirmation(undefined);

    const parsed = entryCommentSchema.safeParse(value);
    if (!parsed.success) {
      setError(parsed.error.issues[0]?.message ?? "Enter a valid comment.");
      return;
    }
    if (parsed.data === savedValue) {
      setConfirmation("There are no comment changes to save.");
      return;
    }

    submissionInFlight.current = true;
    setIsSubmitting(true);
    try {
      const response = await onSubmit({ comment: parsed.data });
      setValue(response.entry.comment ?? "");
      setSavedValue(response.entry.comment);
      setConfirmation(
        response.entry.comment === null ? "Comment cleared." : "Comment saved.",
      );
    } catch (caught) {
      setError(commentErrorMessage(caught));
    } finally {
      submissionInFlight.current = false;
      setIsSubmitting(false);
    }
  }

  const helpId = `${fieldId}-help`;
  const errorId = error === undefined ? undefined : `${fieldId}-error`;

  return (
    <form
      className="comment-editor"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        void submit();
      }}
    >
      {error === undefined && confirmation === undefined ? null : (
        <div
          className={`request-state ${error === undefined ? "request-state--success" : "request-state--error"}`}
          ref={feedbackRef}
          role={error === undefined ? "status" : "alert"}
          tabIndex={-1}
        >
          {error === undefined ? confirmation : "Please correct the comment."}
        </div>
      )}
      <div className="form-field">
        <label htmlFor={fieldId}>Comment</label>
        <p className="form-help" id={helpId}>
          Add up to {MAX_ENTRY_COMMENT_LENGTH.toLocaleString("en-US")}{" "}
          characters. Leave this blank to clear the comment.
        </p>
        <textarea
          id={fieldId}
          rows={6}
          value={value}
          disabled={isSubmitting}
          aria-invalid={errorId === undefined ? "false" : "true"}
          aria-describedby={[helpId, errorId].filter(Boolean).join(" ")}
          onChange={(event) => setValue(event.target.value)}
        />
        {errorId === undefined ? null : (
          <p className="field-error" id={errorId}>
            {error}
          </p>
        )}
      </div>
      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Saving comment…" : "Save comment"}
      </button>
      {isSubmitting ? (
        <p className="visually-hidden" role="status" aria-live="polite">
          Comment is being saved.
        </p>
      ) : null}
    </form>
  );
}

function commentErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.fields?.comment ?? error.message;
  }
  return "We could not save the comment. Please try again.";
}
