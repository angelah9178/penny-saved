import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../api/errors";
import { UnsavedChangesPrompt } from "../components/UnsavedChangesPrompt";
import { EntryForm } from "../features/entries/EntryForm";
import { useCreateEntryMutation } from "../features/entries/queries";

export function NewEntryPage() {
  const navigate = useNavigate();
  const createEntry = useCreateEntryMutation();
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);
  const [allowNavigation, setAllowNavigation] = useState(false);
  const [entryCreated, setEntryCreated] = useState(false);

  useEffect(() => {
    if (entryCreated) {
      void navigate("/dashboard", {
        replace: true,
        state: { entryCreated: true },
      });
    }
  }, [entryCreated, navigate]);

  return (
    <div className="entry-management-page">
      <h1>Add a new entry</h1>
      <p>
        Record a purchase you are considering. It will begin in the Waiting
        section.
      </p>
      <EntryForm
        mode="create"
        onDirtyChange={setHasUnsavedChanges}
        onSubmit={async (payload) => {
          try {
            await createEntry.mutateAsync(payload);
            setAllowNavigation(true);
            setEntryCreated(true);
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) {
              setAllowNavigation(true);
            }
            throw error;
          }
        }}
      />
      <Link to="/dashboard">Back to dashboard</Link>
      <UnsavedChangesPrompt
        shouldBlock={hasUnsavedChanges && !allowNavigation}
      />
    </div>
  );
}
