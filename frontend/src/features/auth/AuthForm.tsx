import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/errors";
import { queryKeys } from "../../lib/queryKeys";
import { safeReturnPath } from "../../routes/returnPath";
import type { AuthRequest, AuthResponse } from "../../types/api";
import { login, signup } from "./api";
import { resetSessionExpiry } from "./sessionExpiry";
import { authFormSchema, type AuthFormValues } from "./validation";

export type AuthFormProps = {
  mode: "login" | "signup";
};

const GENERIC_ERROR = "We could not complete your request. Please try again.";

export function AuthForm({ mode }: AuthFormProps) {
  const formId = useId();
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const summaryRef = useRef<HTMLDivElement>(null);
  const submissionInFlight = useRef(false);
  const [globalError, setGlobalError] = useState<string>();
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors },
  } = useForm<AuthFormValues>({
    defaultValues: { email: "", password: "" },
  });
  const mutation = useMutation({
    mutationFn: mode === "signup" ? signup : login,
  });

  useEffect(() => {
    if (globalError !== undefined) {
      summaryRef.current?.focus();
    }
  }, [globalError]);

  useEffect(() => {
    return () => reset({ email: "", password: "" });
  }, [reset]);

  const submit = handleSubmit(async (values) => {
    if (submissionInFlight.current) {
      return;
    }

    setGlobalError(undefined);
    const parsed = authFormSchema.safeParse(values);
    if (!parsed.success) {
      for (const issue of parsed.error.issues) {
        const field = issue.path[0];
        if (field === "email" || field === "password") {
          setError(field, { type: "client", message: issue.message });
        }
      }
      setGlobalError("Please correct the highlighted fields.");
      return;
    }

    submissionInFlight.current = true;
    try {
      const response = await mutation.mutateAsync(parsed.data as AuthRequest);
      reset({ email: "", password: "" });
      queryClient.setQueryData<AuthResponse | null>(
        queryKeys.auth.me(),
        response,
      );
      resetSessionExpiry();
      await navigate(returnPathFromState(location.state), { replace: true });
    } catch (error) {
      applyApiError(
        error,
        mode,
        parsed.data.password,
        setError,
        setGlobalError,
      );
    } finally {
      submissionInFlight.current = false;
    }
  });

  const emailErrorId = errors.email ? `${formId}-email-error` : undefined;
  const passwordErrorId = errors.password
    ? `${formId}-password-error`
    : undefined;

  return (
    <form
      className="auth-form"
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
        <label htmlFor={`${formId}-email`}>Email</label>
        <input
          id={`${formId}-email`}
          type="email"
          autoComplete="email"
          aria-invalid={errors.email ? "true" : "false"}
          aria-describedby={emailErrorId}
          {...register("email")}
        />
        {errors.email?.message === undefined ? null : (
          <p className="field-error" id={emailErrorId}>
            {errors.email.message}
          </p>
        )}
      </div>

      <div className="form-field">
        <label htmlFor={`${formId}-password`}>Password</label>
        <input
          id={`${formId}-password`}
          type="password"
          autoComplete={mode === "signup" ? "new-password" : "current-password"}
          aria-invalid={errors.password ? "true" : "false"}
          aria-describedby={passwordErrorId}
          {...register("password")}
        />
        {errors.password?.message === undefined ? null : (
          <p className="field-error" id={passwordErrorId}>
            {errors.password.message}
          </p>
        )}
      </div>

      <button type="submit" disabled={mutation.isPending}>
        {mutation.isPending
          ? mode === "signup"
            ? "Creating account…"
            : "Logging in…"
          : mode === "signup"
            ? "Create account"
            : "Log in"}
      </button>
    </form>
  );
}

type SetFieldError = ReturnType<typeof useForm<AuthFormValues>>["setError"];

function applyApiError(
  error: unknown,
  mode: AuthFormProps["mode"],
  password: string,
  setFieldError: SetFieldError,
  setGlobalError: (message: string) => void,
) {
  if (!(error instanceof ApiError)) {
    setGlobalError(GENERIC_ERROR);
    return;
  }

  if (mode === "signup" && error.code === "duplicate_email") {
    setFieldError("email", {
      type: "server",
      message: "An account with this email already exists.",
    });
    setGlobalError("Please correct the highlighted fields.");
    return;
  }

  if (mode === "login" && error.code === "invalid_credentials") {
    setGlobalError("The email or password is incorrect.");
    return;
  }

  if (error.status === 422 && error.fields !== undefined) {
    let knownFieldFound = false;
    for (const [field, message] of Object.entries(error.fields)) {
      if (field === "email" || field === "password") {
        knownFieldFound = true;
        setFieldError(field, {
          type: "server",
          message: safeMessage(message, password),
        });
      }
    }
    setGlobalError(
      knownFieldFound
        ? "Please correct the highlighted fields."
        : "The submitted information is invalid.",
    );
    return;
  }

  setGlobalError(safeMessage(error.message, password));
}

function safeMessage(message: string, password: string): string {
  return password.length > 0 && message.includes(password)
    ? GENERIC_ERROR
    : message;
}

function returnPathFromState(state: unknown): string {
  if (typeof state !== "object" || state === null || !("returnTo" in state)) {
    return safeReturnPath(undefined);
  }
  return safeReturnPath(state.returnTo);
}
