import { Link } from "react-router-dom";

import { DateTime } from "../../components/DateTime";
import { formatUsd } from "../../lib/currency";
import type { DashboardBucket, Entry } from "../../types/api";
import { WaitingAvailability } from "./WaitingAvailability";

export type EntryCardProps = {
  entry: Entry;
  section: DashboardBucket;
};

export function EntryCard({ entry, section }: EntryCardProps) {
  const showComment =
    (section === "saved" || section === "purchased") &&
    entry.comment !== null &&
    entry.comment.trim() !== "";

  return (
    <article className="entry-card">
      <h3>{entry.item_name}</h3>
      <p className="entry-card__price">{formatUsd(entry.price_cents)}</p>
      <p>
        <strong>Reason:</strong> {entry.reason_wanted}
      </p>

      <EntryStatus entry={entry} section={section} />

      {showComment ? (
        <p>
          <strong>Comment:</strong> {entry.comment}
        </p>
      ) : null}

      {section === "needs_check_in" ? (
        <Link to={`/entries/${entry.id}/check-in`}>Check in</Link>
      ) : null}
    </article>
  );
}

function EntryStatus({ entry, section }: EntryCardProps) {
  switch (section) {
    case "needs_check_in":
      return <p>The waiting period is complete.</p>;
    case "waiting":
      return (
        <p>
          <WaitingAvailability
            eligibleForCheckInAt={entry.eligible_for_check_in_at}
          />
        </p>
      );
    case "saved":
      return (
        <p>
          Saved
          {entry.checked_in_at === null ? null : (
            <>
              {" "}
              on <DateTime value={entry.checked_in_at} />
            </>
          )}
        </p>
      );
    case "purchased":
      return (
        <p>
          Purchased
          {entry.checked_in_at === null ? null : (
            <>
              {" "}
              on <DateTime value={entry.checked_in_at} />
            </>
          )}
        </p>
      );
  }
}
