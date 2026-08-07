import { Link, useLocation } from "react-router-dom";
import {
  useEffect,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from "react";

import { ErrorAlert } from "../components/ErrorAlert";
import { FeedbackMessage } from "../components/FeedbackMessage";
import { Loading } from "../components/Loading";
import { EntrySection } from "../features/entries/EntrySection";
import { useDashboardEntries } from "../features/entries/queries";
import { StatisticsSection } from "../features/stats/StatisticsSection";

export function DashboardPage() {
  const dashboard = useDashboardEntries();
  const location = useLocation();
  const entryCreated = hasEntryCreatedState(location.state);
  const entryUpdated = hasEntryUpdatedState(location.state);
  const [entryNotice, setEntryNotice] = useState<string>();
  const noticeRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (entryNotice !== undefined) noticeRef.current?.focus();
  }, [entryNotice]);

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
          isRetrying={dashboard.isFetching}
          retryLabel="Retry dashboard"
          retryingLabel="Retrying dashboard…"
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
        <FeedbackMessage message="Entry added to Waiting." tone="success" />
      ) : null}
      {entryUpdated ? (
        <FeedbackMessage message="Entry changes saved." tone="success" />
      ) : null}
      {entryNotice === undefined ? null : (
        <FeedbackMessage
          focusable
          message={entryNotice}
          ref={noticeRef}
          tone="success"
        />
      )}
      <p>Review your waiting decisions and the purchases you have resolved.</p>
      {dashboard.isFetching ? (
        <FeedbackMessage
          className="dashboard-updating"
          message="Updating dashboard…"
          tone="status"
        />
      ) : null}
      <p className="dashboard-actions">
        <Link className="dashboard-add-link" to="/entries/new">
          Add new impulse purchase
        </Link>
        <Link
          className="dashboard-settings-link"
          to="/settings/opportunity-costs"
        >
          Manage opportunity-cost examples
        </Link>
      </p>

      <StatisticsSection />

      <EntrySection
        title="Needs check-in"
        emptyMessage="Nothing needs your attention right now."
        entries={entries.needs_check_in}
        section="needs_check_in"
        onNotice={setEntryNotice}
      />
      <EntrySection
        title="Waiting"
        emptyMessage="You have no purchases in the waiting period."
        entries={entries.waiting}
        section="waiting"
        onNotice={setEntryNotice}
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

function toggleDisclosureFromKeyboard(event: KeyboardEvent<HTMLElement>) {
  if (event.key !== "Enter" && event.key !== " ") return;

  const disclosure = event.currentTarget.parentElement;
  if (!(disclosure instanceof HTMLDetailsElement)) return;

  // jsdom and some older assistive-technology/browser combinations do not apply
  // the native summary keyboard action consistently.
  event.preventDefault();
  disclosure.open = !disclosure.open;
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
