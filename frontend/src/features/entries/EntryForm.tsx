import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "../../api/errors";
import type { CreateEntryRequest } from "../../types/api";
import { entryFormSchema, type EntryFormValues } from "./entryFormValidation";

export type EntryFormProps = {
  mode: "create" | "edit";
  initialValues?: EntryFormValues;
  onDirtyChange?: (isDirty: boolean) => void;
  onSubmit: (payload: CreateEntryRequest) => Promise<void> | void;
};

const EMPTY_VALUES: EntryFormValues = {
  item_name: "",
  price: "",
  reason_wanted: "",
};
const GENERIC_ERROR = "We could not save the entry. Please try again.";

export function EntryForm({
  mode,
  initialValues,
  onDirtyChange,
  onSubmit,
}: EntryFormProps) {
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
    formState: { errors, isDirty },
  } = useForm<EntryFormValues>({
    defaultValues: initialValues ?? EMPTY_VALUES,
  });

  useEffect(() => {
    if (globalError !== undefined) {
      summaryRef.current?.focus();
    }
  }, [globalError]);

  useEffect(() => {
    onDirtyChange?.(isDirty);
  }, [isDirty, onDirtyChange]);

  const submit = handleSubmit(async (values) => {
    if (submissionInFlight.current) {
      return;
    }

    clearErrors();
    setGlobalError(undefined);
    const parsed = entryFormSchema.safeParse(values);
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        const field = issue.path[0];
        if (
          field === "item_name" ||
          field === "price" ||
          field === "reason_wanted"
        ) {
          setError(field, { type: "client", message: issue.message });
        }
      }
      setGlobalError("Please correct the highlighted fields.");
      return;
    }

    submissionInFlight.current = true;
    setIsSubmitting(true);
    try {
      await onSubmit({
        item_name: parsed.data.item_name,
        price_cents: parsed.data.price,
        reason_wanted: parsed.data.reason_wanted,
      });
    } catch (error) {
      applySubmissionError(error, setError, setGlobalError);
    } finally {
      submissionInFlight.current = false;
      setIsSubmitting(false);
    }
  });

  const itemNameErrorId = errors.item_name
    ? `${formId}-item-name-error`
    : undefined;
  const priceErrorId = errors.price ? `${formId}-price-error` : undefined;
  const reasonErrorId = errors.reason_wanted
    ? `${formId}-reason-error`
    : undefined;

  return (
    <form
      className="entry-form"
      noValidate
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      {globalError === undefined ? null : (
        <div
          className="request-state request-state--error"
          ref={summaryRef}
          role="alert"
          tabIndex={-1}
        >
          {globalError}
        </div>
      )}

      <div className="form-field">
        <label htmlFor={`${formId}-item-name`}>Item name</label>
        <input
          id={`${formId}-item-name`}
          type="text"
          maxLength={200}
          aria-invalid={errors.item_name ? "true" : "false"}
          aria-describedby={itemNameErrorId}
          {...register("item_name")}
        />
        <FieldError id={itemNameErrorId} message={errors.item_name?.message} />
      </div>

      <div className="form-field">
        <label htmlFor={`${formId}-price`}>Price</label>
        <input
          id={`${formId}-price`}
          type="text"
          inputMode="decimal"
          placeholder="0.00"
          aria-invalid={errors.price ? "true" : "false"}
          aria-describedby={priceErrorId}
          {...register("price")}
        />
        <FieldError id={priceErrorId} message={errors.price?.message} />
      </div>

      <div className="form-field">
        <label htmlFor={`${formId}-reason`}>Reason wanted</label>
        <textarea
          id={`${formId}-reason`}
          maxLength={2_000}
          rows={6}
          aria-invalid={errors.reason_wanted ? "true" : "false"}
          aria-describedby={reasonErrorId}
          {...register("reason_wanted")}
        />
        <FieldError
          id={reasonErrorId}
          message={errors.reason_wanted?.message}
        />
      </div>

      <button type="submit" disabled={isSubmitting}>
        {isSubmitting
          ? mode === "create"
            ? "Adding entry…"
            : "Saving changes…"
          : mode === "create"
            ? "Add entry"
            : "Save changes"}
      </button>
    </form>
  );
}

type SetFieldError = ReturnType<typeof useForm<EntryFormValues>>["setError"];

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
    const formField = field === "price_cents" ? "price" : field;
    if (
      formField === "item_name" ||
      formField === "price" ||
      formField === "reason_wanted"
    ) {
      knownFieldFound = true;
      setFieldError(formField, { type: "server", message });
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
