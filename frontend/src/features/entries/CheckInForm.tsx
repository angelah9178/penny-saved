import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "../../api/errors";
import { FeedbackMessage } from "../../components/FeedbackMessage";
import type { CheckInEntryRequest } from "../../types/api";
import {
  checkInFormSchema,
  type CheckInFormValues,
  MAX_CHECK_IN_COMMENT_LENGTH,
} from "./checkInFormValidation";

export type CheckInFormProps = {
  onSubmit: (payload: CheckInEntryRequest) => Promise<void> | void;
};

const GENERIC_ERROR = "We could not complete check-in. Please try again.";

export function CheckInForm({ onSubmit }: CheckInFormProps) {
  const formId = useId();
  const summaryRef = useRef<HTMLDivElement>(null);
  const submissionInFlight = useRef(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [globalError, setGlobalError] = useState<string>();
  const {
    clearErrors,
    handleSubmit,
    register,
    setError,
    formState: { errors },
  } = useForm<CheckInFormValues>({
    defaultValues: { result: "", comment: "" },
  });

  useEffect(() => {
    if (globalError !== undefined) {
      summaryRef.current?.focus();
    }
  }, [globalError]);

  const submit = handleSubmit(async (values) => {
    if (submissionInFlight.current) return;

    clearErrors();
    setGlobalError(undefined);
    const parsed = checkInFormSchema.safeParse(values);
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        const field = issue.path[0];
        if (field === "result" || field === "comment") {
          setError(field, { type: "client", message: issue.message });
        }
      }
      setGlobalError("Please correct the highlighted fields.");
      return;
    }

    submissionInFlight.current = true;
    setIsSubmitting(true);
    try {
      await onSubmit(parsed.data);
    } catch (error) {
      applySubmissionError(error, setError, setGlobalError);
    } finally {
      submissionInFlight.current = false;
      setIsSubmitting(false);
    }
  });

  const resultErrorId = errors.result ? `${formId}-result-error` : undefined;
  const commentHelpId = `${formId}-comment-help`;
  const commentErrorId = errors.comment ? `${formId}-comment-error` : undefined;

  return (
    <form
      className="check-in-form"
      noValidate
      onSubmit={(event) => void submit(event)}
    >
      {globalError === undefined ? null : (
        <FeedbackMessage
          focusable
          message={globalError}
          ref={summaryRef}
          tone="error"
        />
      )}

      <fieldset
        className="check-in-form__choices"
        aria-invalid={errors.result ? "true" : "false"}
        aria-describedby={resultErrorId}
        disabled={isSubmitting}
      >
        <legend>What happened with this purchase?</legend>
        <label>
          <input type="radio" value="saved" required {...register("result")} />
          <span>I did not buy it</span>
        </label>
        <label>
          <input
            type="radio"
            value="purchased"
            required
            {...register("result")}
          />
          <span>I bought it</span>
        </label>
      </fieldset>
      <FieldError id={resultErrorId} message={errors.result?.message} />

      <div className="form-field">
        <label htmlFor={`${formId}-comment`}>Reflection (optional)</label>
        <p id={commentHelpId} className="form-help">
          Add up to {MAX_CHECK_IN_COMMENT_LENGTH.toLocaleString("en-US")}{" "}
          characters about what influenced your decision.
        </p>
        <textarea
          id={`${formId}-comment`}
          rows={6}
          disabled={isSubmitting}
          aria-invalid={errors.comment ? "true" : "false"}
          aria-describedby={[commentHelpId, commentErrorId]
            .filter(Boolean)
            .join(" ")}
          {...register("comment")}
        />
        <FieldError id={commentErrorId} message={errors.comment?.message} />
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting ? "Submitting check-in…" : "Submit check-in"}
      </button>
      {isSubmitting ? (
        <p className="visually-hidden" role="status" aria-live="polite">
          Check-in is being submitted.
        </p>
      ) : null}
    </form>
  );
}

type SetFieldError = ReturnType<typeof useForm<CheckInFormValues>>["setError"];

function applySubmissionError(
  error: unknown,
  setFieldError: SetFieldError,
  setGlobalError: (message: string) => void,
): void {
  if (!(error instanceof ApiError)) {
    setGlobalError(GENERIC_ERROR);
    return;
  }

  let knownFieldFound = false;
  for (const [field, message] of Object.entries(error.fields ?? {})) {
    if (field === "result" || field === "comment") {
      knownFieldFound = true;
      setFieldError(field, { type: "server", message });
    }
  }
  setGlobalError(
    knownFieldFound ? "Please correct the highlighted fields." : error.message,
  );
}

function FieldError({
  id,
  message,
}: {
  id: string | undefined;
  message: string | undefined;
}) {
  return message === undefined ? null : (
    <p className="field-error" id={id}>
      {message}
    </p>
  );
}
