import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { ApiError } from "../../api/errors";
import { FeedbackMessage } from "../../components/FeedbackMessage";
import type { CreateOpportunityCostExampleRequest } from "../../types/api";
import {
  EMPTY_OPPORTUNITY_COST_FORM_VALUES,
  opportunityCostFormSchema,
  type OpportunityCostFormValues,
} from "./formValidation";

export type OpportunityCostFormProps = {
  mode: "create" | "edit";
  initialValues?: OpportunityCostFormValues;
  isPending?: boolean;
  onCancel?: (() => void) | undefined;
  onSubmit: (
    payload: CreateOpportunityCostExampleRequest,
  ) => Promise<void> | void;
};

export function OpportunityCostForm({
  mode,
  initialValues,
  isPending = false,
  onCancel,
  onSubmit,
}: OpportunityCostFormProps) {
  const formId = useId();
  const summaryRef = useRef<HTMLDivElement>(null);
  const [validationSummary, setValidationSummary] = useState(false);
  const [globalError, setGlobalError] = useState<string>();
  const {
    clearErrors,
    handleSubmit,
    register,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<OpportunityCostFormValues>({
    defaultValues: initialValues ?? EMPTY_OPPORTUNITY_COST_FORM_VALUES,
  });

  useEffect(() => {
    if (validationSummary || globalError !== undefined) {
      summaryRef.current?.focus();
    }
  }, [globalError, validationSummary]);

  const submit = handleSubmit(async (values) => {
    clearErrors();
    setValidationSummary(false);
    setGlobalError(undefined);
    const parsed = opportunityCostFormSchema.safeParse(values);

    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        const field = issue.path[0];
        if (
          field === "label" ||
          field === "unit_name" ||
          field === "dollar_value"
        ) {
          setError(field, { type: "client", message: issue.message });
        }
      }
      setValidationSummary(true);
      return;
    }

    try {
      await onSubmit({
        label: parsed.data.label,
        unit_name: parsed.data.unit_name,
        dollar_value_cents: parsed.data.dollar_value,
      });
    } catch (error) {
      applySubmissionError(
        error,
        setError,
        setValidationSummary,
        setGlobalError,
      );
    }
  });

  const disabled = isPending || isSubmitting;
  const labelErrorId = errors.label ? `${formId}-label-error` : undefined;
  const unitErrorId = errors.unit_name ? `${formId}-unit-error` : undefined;
  const valueHelpId = `${formId}-value-help`;
  const valueErrorId = errors.dollar_value
    ? `${formId}-value-error`
    : undefined;

  return (
    <form
      className="opportunity-cost-form"
      noValidate
      onSubmit={(event) => {
        void submit(event);
      }}
    >
      {validationSummary || globalError !== undefined ? (
        <FeedbackMessage
          focusable
          message={
            validationSummary
              ? "Please correct the highlighted fields."
              : (globalError ?? "We could not save this example.")
          }
          ref={summaryRef}
          tone="error"
        />
      ) : null}

      <div className="form-field">
        <label htmlFor={`${formId}-label`}>Label</label>
        <input
          id={`${formId}-label`}
          type="text"
          required
          maxLength={120}
          disabled={disabled}
          aria-invalid={errors.label ? "true" : "false"}
          aria-describedby={labelErrorId}
          {...register("label")}
        />
        <FieldError id={labelErrorId} message={errors.label?.message} />
      </div>

      <div className="form-field">
        <label htmlFor={`${formId}-unit-name`}>Unit name</label>
        <input
          id={`${formId}-unit-name`}
          type="text"
          required
          maxLength={80}
          disabled={disabled}
          aria-invalid={errors.unit_name ? "true" : "false"}
          aria-describedby={unitErrorId}
          {...register("unit_name")}
        />
        <FieldError id={unitErrorId} message={errors.unit_name?.message} />
      </div>

      <div className="form-field">
        <label htmlFor={`${formId}-dollar-value`}>Dollar value</label>
        <input
          id={`${formId}-dollar-value`}
          type="text"
          required
          inputMode="decimal"
          placeholder="0.00"
          disabled={disabled}
          aria-invalid={errors.dollar_value ? "true" : "false"}
          aria-describedby={
            valueErrorId === undefined
              ? valueHelpId
              : `${valueHelpId} ${valueErrorId}`
          }
          {...register("dollar_value")}
        />
        <p className="form-help" id={valueHelpId}>
          Enter the value of one unit in US dollars, such as 10.00.
        </p>
        <FieldError id={valueErrorId} message={errors.dollar_value?.message} />
      </div>

      <div className="opportunity-cost-form__actions">
        <button type="submit" disabled={disabled}>
          {disabled
            ? mode === "create"
              ? "Creating example…"
              : "Saving changes…"
            : mode === "create"
              ? "Create example"
              : "Save changes"}
        </button>
        {onCancel === undefined ? null : (
          <button type="button" disabled={disabled} onClick={onCancel}>
            Cancel
          </button>
        )}
      </div>
    </form>
  );
}

type SetFieldError = ReturnType<
  typeof useForm<OpportunityCostFormValues>
>["setError"];

function applySubmissionError(
  error: unknown,
  setFieldError: SetFieldError,
  setValidationSummary: (visible: boolean) => void,
  setGlobalError: (message: string) => void,
): void {
  if (error instanceof ApiError) {
    let knownFieldFound = false;
    for (const [field, message] of Object.entries(error.fields ?? {})) {
      const formField = field === "dollar_value_cents" ? "dollar_value" : field;
      if (
        formField === "label" ||
        formField === "unit_name" ||
        formField === "dollar_value"
      ) {
        knownFieldFound = true;
        setFieldError(formField, { type: "server", message });
      }
    }
    if (knownFieldFound) {
      setValidationSummary(true);
      return;
    }
  }

  setGlobalError("We could not save the example. Please try again.");
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
