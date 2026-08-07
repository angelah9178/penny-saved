import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { ApiError } from "../api/errors";
import { EmptyState } from "../components/EmptyState";
import { ErrorAlert } from "../components/ErrorAlert";
import { FeedbackMessage } from "../components/FeedbackMessage";
import { Loading } from "../components/Loading";
import { OpportunityCostExampleList } from "../features/opportunity-costs/OpportunityCostExampleList";
import { OpportunityCostForm } from "../features/opportunity-costs/OpportunityCostForm";
import { formatCentsForOpportunityCostForm } from "../features/opportunity-costs/formValidation";
import {
  useCreateOpportunityCostExampleMutation,
  useOpportunityCostExamples,
  useUpdateOpportunityCostExampleMutation,
} from "../features/opportunity-costs/queries";
import type {
  CreateOpportunityCostExampleRequest,
  OpportunityCostExample,
} from "../types/api";

type ActiveForm =
  | { mode: "create" }
  | { mode: "edit"; example: OpportunityCostExample };

export function OpportunityCostSettingsPage() {
  const examples = useOpportunityCostExamples();
  const createExample = useCreateOpportunityCostExampleMutation();
  const updateExample = useUpdateOpportunityCostExampleMutation();
  const [activeForm, setActiveForm] = useState<ActiveForm>();
  const [notice, setNotice] = useState<string>();
  const noticeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (notice !== undefined) noticeRef.current?.focus();
  }, [notice]);

  async function submitForm(payload: CreateOpportunityCostExampleRequest) {
    if (activeForm === undefined) return;

    try {
      if (activeForm.mode === "create") {
        await createExample.mutateAsync(payload);
        setNotice("Opportunity-cost example created.");
      } else {
        await updateExample.mutateAsync({
          exampleId: activeForm.example.id,
          payload,
        });
        setNotice("Opportunity-cost example updated.");
      }
      setActiveForm(undefined);
    } catch (error) {
      if (
        activeForm.mode === "edit" &&
        error instanceof ApiError &&
        (error.status === 403 || error.status === 404)
      ) {
        await examples.refetch();
        setActiveForm(undefined);
        setNotice(
          "That example is no longer available. The list has been refreshed.",
        );
        return;
      }
      throw error;
    }
  }

  return (
    <div className="opportunity-cost-settings">
      <nav aria-label="Breadcrumb">
        <Link to="/dashboard">Return to dashboard</Link>
      </nav>
      <div className="opportunity-cost-settings__header">
        <div>
          <h1>Opportunity-cost examples</h1>
          <p>
            Manage the everyday comparisons used to show what your savings are
            worth.
          </p>
        </div>
        {activeForm === undefined ? (
          <button
            type="button"
            onClick={() => {
              setNotice(undefined);
              setActiveForm({ mode: "create" });
            }}
          >
            Create example
          </button>
        ) : null}
      </div>

      {notice === undefined ? null : (
        <FeedbackMessage
          focusable
          message={notice}
          ref={noticeRef}
          tone="success"
        />
      )}

      {activeForm === undefined ? null : (
        <section
          className="opportunity-cost-settings__form"
          aria-labelledby="example-form-heading"
        >
          <h2 id="example-form-heading">
            {activeForm.mode === "create"
              ? "Create example"
              : `Edit ${activeForm.example.label}`}
          </h2>
          <OpportunityCostForm
            key={
              activeForm.mode === "create" ? "create" : activeForm.example.id
            }
            mode={activeForm.mode}
            {...(activeForm.mode === "edit"
              ? {
                  initialValues: {
                    label: activeForm.example.label,
                    unit_name: activeForm.example.unit_name,
                    dollar_value: formatCentsForOpportunityCostForm(
                      activeForm.example.dollar_value_cents,
                    ),
                  },
                }
              : {})}
            isPending={createExample.isPending || updateExample.isPending}
            onCancel={() => setActiveForm(undefined)}
            onSubmit={submitForm}
          />
        </section>
      )}

      {examples.isPending ? (
        <Loading message="Loading your opportunity-cost examples…" />
      ) : null}
      {examples.isError ? (
        <ErrorAlert
          message="We could not load your opportunity-cost examples. Please try again."
          isRetrying={examples.isFetching}
          retryLabel="Retry examples"
          retryingLabel="Retrying examples…"
          onRetry={() => {
            void examples.refetch();
          }}
        />
      ) : null}
      {examples.isFetching && examples.data !== undefined ? (
        <FeedbackMessage
          className="opportunity-cost-settings__updating"
          message="Updating examples…"
          tone="status"
        />
      ) : null}
      {examples.data?.examples.length === 0 ? (
        <EmptyState
          title="No opportunity-cost examples yet"
          message="Create an example to turn money saved into relatable units on your dashboard."
        />
      ) : null}
      {examples.data !== undefined && examples.data.examples.length > 0 ? (
        <OpportunityCostExampleList
          examples={examples.data.examples}
          onEdit={(example) => {
            setNotice(undefined);
            setActiveForm({ mode: "edit", example });
          }}
          onDeleted={(example) => {
            setActiveForm(undefined);
            setNotice(`${example.label} was deleted.`);
          }}
          onDeleteStale={async () => {
            await examples.refetch();
            setActiveForm(undefined);
            setNotice(
              "That example is no longer available. The list has been refreshed.",
            );
          }}
        />
      ) : null}
    </div>
  );
}
