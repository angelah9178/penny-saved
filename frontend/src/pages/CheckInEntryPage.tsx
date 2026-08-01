import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { ApiError } from "../api/errors";
import { DateTime } from "../components/DateTime";
import { ErrorAlert } from "../components/ErrorAlert";
import { Loading } from "../components/Loading";
import { CheckInForm } from "../features/entries/CheckInForm";
import {
  useCheckInEntryMutation,
  useEntryDetail,
} from "../features/entries/queries";
import { formatUsd } from "../lib/currency";
import type { Entry } from "../types/api";

export function CheckInEntryPage() {
  const { entryId = "" } = useParams();
  const returnPath = `/entries/${encodeURIComponent(entryId)}/check-in`;
  const detail = useEntryDetail(entryId, returnPath);
  const checkIn = useCheckInEntryMutation(entryId);

  if (detail.isPending) {
    return <Loading message="Loading check-in…" />;
  }

  if (detail.isError) {
    return (
      <CheckInPageLayout title="Check in">
        <ErrorAlert
          message={detailErrorMessage(detail.error)}
          onRetry={() => void detail.refetch()}
        />
      </CheckInPageLayout>
    );
  }

  const entry = detail.data.entry;
  if (!isEligibleWaitingEntry(entry)) {
    return (
      <CheckInPageLayout title={`Check in: ${entry.item_name}`}>
        <EntryContext entry={entry} />
        <div className="request-state request-state--empty">
          <p>{unavailableMessage(entry)}</p>
        </div>
      </CheckInPageLayout>
    );
  }

  return (
    <CheckInPageLayout title={`Check in: ${entry.item_name}`}>
      <p>
        Review your original decision, then explicitly choose what happened.
      </p>
      <EntryContext entry={entry} />
      <CheckInForm
        onSubmit={async (payload) => {
          await checkIn.mutateAsync(payload);
        }}
      />
    </CheckInPageLayout>
  );
}

function CheckInPageLayout({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="check-in-page">
      <h1>{title}</h1>
      {children}
      <Link to="/dashboard">Back to dashboard</Link>
    </div>
  );
}

function EntryContext({ entry }: { entry: Entry }) {
  return (
    <section
      className="check-in-context"
      aria-labelledby="check-in-context-title"
    >
      <h2 id="check-in-context-title">Your original decision</h2>
      <dl>
        <div>
          <dt>Item</dt>
          <dd>{entry.item_name}</dd>
        </div>
        <div>
          <dt>Price</dt>
          <dd>{formatUsd(entry.price_cents)}</dd>
        </div>
        <div>
          <dt>Reason wanted</dt>
          <dd>{entry.reason_wanted}</dd>
        </div>
        <div>
          <dt>Recorded</dt>
          <dd>
            <DateTime value={entry.created_at} />
          </dd>
        </div>
        <div>
          <dt>Check-in became available</dt>
          <dd>
            <DateTime value={entry.eligible_for_check_in_at} />
          </dd>
        </div>
      </dl>
    </section>
  );
}

function isEligibleWaitingEntry(entry: Entry): boolean {
  return (
    entry.status === "waiting" && entry.dashboard_bucket === "needs_check_in"
  );
}

function unavailableMessage(entry: Entry): string {
  if (entry.status === "saved") {
    return "This entry has already been resolved as saved.";
  }
  if (entry.status === "purchased") {
    return "This entry has already been resolved as purchased.";
  }
  return "This entry is still in its waiting period. Check in when the server marks it as ready.";
}

function detailErrorMessage(error: Error): string {
  if (error instanceof ApiError) {
    if (error.status === 404) return "We could not find that entry.";
    if (error.status === 403) return "You do not have access to that entry.";
  }
  return "We could not load this entry. Please try again.";
}
