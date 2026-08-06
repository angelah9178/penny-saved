import { Link } from "react-router-dom";

import { EmptyState } from "../components/EmptyState";
import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { OpportunityCostExampleList } from "../features/opportunity-costs/OpportunityCostExampleList";
import { useOpportunityCostExamples } from "../features/opportunity-costs/queries";

export function OpportunityCostSettingsPage() {
  const examples = useOpportunityCostExamples();

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
        <button type="button">Create example</button>
      </div>

      {examples.isPending ? (
        <Loading message="Loading your opportunity-cost examples…" />
      ) : null}
      {examples.isError ? (
        <ErrorAlert
          message="We could not load your opportunity-cost examples. Please try again."
          onRetry={() => {
            void examples.refetch();
          }}
        />
      ) : null}
      {examples.isFetching && !examples.isPending ? (
        <p className="opportunity-cost-settings__updating" role="status">
          Updating examples…
        </p>
      ) : null}
      {examples.data?.examples.length === 0 ? (
        <EmptyState
          title="No opportunity-cost examples yet"
          message="Create an example to turn money saved into relatable units on your dashboard."
        />
      ) : null}
      {examples.data !== undefined && examples.data.examples.length > 0 ? (
        <OpportunityCostExampleList examples={examples.data.examples} />
      ) : null}
    </div>
  );
}
