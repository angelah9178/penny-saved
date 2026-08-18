import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/errors";
import { DashboardReturnLink } from "../components/DashboardReturnLink";
import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { UnsavedChangesPrompt } from "../components/UnsavedChangesPrompt";
import { EntryForm } from "../features/entries/EntryForm";
import { formatCentsForEntryForm } from "../features/entries/entryFormValidation";
import {
  useEntryDetail,
  useUpdateEntryMutation,
} from "../features/entries/queries";
import { queryKeys } from "../lib/queryKeys";

export function EditEntryPage() {
  const { entryId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const detail = useEntryDetail(entryId);
  const updateEntry = useUpdateEntryMutation(entryId);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [allowNavigation, setAllowNavigation] = useState(false);
  const [entryUpdated, setEntryUpdated] = useState(false);

  useEffect(() => {
    if (entryUpdated) {
      void navigate("/dashboard", {
        replace: true,
        state: { entryUpdated: true },
      });
    }
  }, [entryUpdated, navigate]);

  if (detail.isPending) {
    return <Loading message="Loading entry…" />;
  }

  if (detail.isError) {
    const unavailable = isUnavailableDetailError(detail.error);
    return (
      <div className="entry-management-page">
        <h1>Edit entry</h1>
        <ErrorAlert
          message={detailErrorMessage(detail.error)}
          isRetrying={detail.isFetching}
          retryLabel="Retry entry"
          retryingLabel="Retrying entry…"
          {...(unavailable ? {} : { onRetry: () => void detail.refetch() })}
        />
        <DashboardReturnLink />
      </div>
    );
  }

  const entry = detail.data.entry;
  if (entry.status !== "waiting") {
    return (
      <div className="entry-management-page">
        <h1>Edit {entry.item_name}</h1>
        <ErrorAlert message="This entry is no longer waiting and cannot be edited." />
        <DashboardReturnLink />
      </div>
    );
  }

  return (
    <div className="entry-management-page">
      <h1>Edit {entry.item_name}</h1>
      <p>Update the item, price, or reason for this waiting entry.</p>
      <EntryForm
        mode="edit"
        initialValues={{
          item_name: entry.item_name,
          price: formatCentsForEntryForm(entry.price_cents),
          reason_wanted: entry.reason_wanted,
        }}
        onDirtyChange={setHasUnsavedChanges}
        onSubmit={async (payload) => {
          try {
            await updateEntry.mutateAsync(payload);
            setAllowNavigation(true);
            setEntryUpdated(true);
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) {
              setAllowNavigation(true);
            }
            if (
              error instanceof ApiError &&
              error.code === "invalid_entry_status"
            ) {
              await Promise.all([
                queryClient.invalidateQueries({
                  queryKey: queryKeys.entries.detail(entryId),
                }),
                queryClient.invalidateQueries({
                  queryKey: queryKeys.entries.dashboard(),
                }),
              ]);
              throw new ApiError(
                error.status,
                error.code,
                "This entry is no longer waiting and cannot be edited.",
              );
            }
            throw error;
          }
        }}
      />
      <DashboardReturnLink />
      <UnsavedChangesPrompt
        shouldBlock={hasUnsavedChanges && !allowNavigation}
      />
    </div>
  );
}

function detailErrorMessage(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 404) {
      return "We could not find that entry.";
    }
    if (error.status === 403) {
      return "You do not have access to that entry.";
    }
  }
  return "We could not load this entry. Please try again.";
}

function isUnavailableDetailError(error: Error): boolean {
  return (
    error instanceof ApiError && (error.status === 403 || error.status === 404)
  );
}
