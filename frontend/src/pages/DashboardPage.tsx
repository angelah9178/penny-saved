import { Link } from "react-router-dom";

import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { EntrySection } from "../features/entries/EntrySection";
import { useDashboardEntries } from "../features/entries/queries";

export function DashboardPage() {
  const dashboard = useDashboardEntries();

  if (dashboard.isPending) {
    return <Loading message="Loading your entries…" />;
  }

  if (dashboard.isError) {
    return <ErrorAlert message="We could not load your dashboard." />;
  }

  const entries = dashboard.data;

  return (
    <>
      <h1>Dashboard</h1>
      <p>Review your waiting decisions and the purchases you have resolved.</p>
      <p>
        <Link to="/entries/new">Add new impulse purchase</Link>
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
        <summary>Purchased ({entries.purchased.length})</summary>
        <EntrySection
          title="Purchased entries"
          emptyMessage="Entries you decide to buy will appear here."
          entries={entries.purchased}
          section="purchased"
        />
      </details>
    </>
  );
}
