import { Link, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import type { KeyboardEvent } from "react";

import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { EntrySection } from "../features/entries/EntrySection";
import { useDashboardEntries } from "../features/entries/queries";

export function DashboardPage() {
  const dashboard = useDashboardEntries();
  const location = useLocation();
  const entryCreated = hasEntryCreatedState(location.state);
  const entryUpdated = hasEntryUpdatedState(location.state);

  if (dashboard.isPending) {
    return (
      <DashboardFrame>
        <Loading message="Loading your entries…" />
      </DashboardFrame>
    );
  }

  if (dashboard.isError) {
    return (
      <DashboardFrame>
        <ErrorAlert
          message="We could not load your dashboard. Please try again."
          onRetry={() => {
            void dashboard.refetch();
          }}
        />
      </DashboardFrame>
    );
  }

  const entries = dashboard.data;

  return (
    <DashboardFrame>
      {entryCreated ? (
        <p className="request-state request-state--success" role="status">
          Entry added to Waiting.
        </p>
      ) : null}
      {entryUpdated ? (
        <p className="request-state request-state--success" role="status">
          Entry changes saved.
        </p>
      ) : null}
      <p>Review your waiting decisions and the purchases you have resolved.</p>
      {dashboard.isFetching ? (
        <p className="dashboard-updating" role="status" aria-live="polite">
          Updating dashboard…
        </p>
      ) : null}
      <p className="dashboard-actions">
        <Link className="dashboard-add-link" to="/entries/new">
          Add new impulse purchase
        </Link>
      </p>

      <EntrySection
        title="Needs check-in"
        emptyMessage="Nothing needs your attention right now."
        entries={entries.needs_check_in}
        section="needs_check_in"
      />
      <EntrySection
        title="Waiting"
        emptyMessage="You have no purchases in the waiting period."
        entries={entries.waiting}
        section="waiting"
      />
      <EntrySection
        title="Saved"
        emptyMessage="Entries you decide not to buy will appear here."
        entries={entries.saved}
        section="saved"
      />

      <details className="purchased-disclosure">
        <summary tabIndex={0} onKeyDown={toggleDisclosureFromKeyboard}>
          Purchased ({entries.purchased.length})
        </summary>
        <EntrySection
          title="Purchased entries"
          emptyMessage="Entries you decide to buy will appear here."
          entries={entries.purchased}
          section="purchased"
        />
      </details>
    </DashboardFrame>
  );
}

function hasEntryCreatedState(state: unknown): boolean {
  return (
    typeof state === "object" &&
    state !== null &&
    "entryCreated" in state &&
    state.entryCreated === true
  );
}

function hasEntryUpdatedState(state: unknown): boolean {
  return (
    typeof state === "object" &&
    state !== null &&
    "entryUpdated" in state &&
    state.entryUpdated === true
  );
}

function DashboardFrame({ children }: { children: ReactNode }) {
  return (
    <div className="dashboard">
      <h1>Dashboard</h1>
      {children}
    </div>
  );
}

function toggleDisclosureFromKeyboard(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== "Enter" && event.key !== " ") {
    return;
  }

  const disclosure = event.currentTarget.parentElement;

  if (!(disclosure instanceof HTMLDetailsElement)) {
    return;
  }

  event.preventDefault();
  disclosure.open = !disclosure.open;
}
