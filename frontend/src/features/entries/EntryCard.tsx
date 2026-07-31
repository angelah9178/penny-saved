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
      <header className="entry-card__header">
        <div className="entry-card__title-group">
          <h3>{entry.item_name}</h3>
          <p className="entry-card__price">{formatUsd(entry.price_cents)}</p>
        </div>
        <span className={`entry-card__status entry-card__status--${section}`}>
          {sectionLabel(section)}
        </span>
      </header>

      <div className="entry-card__body">
        <p>
          <strong>Reason:</strong> {entry.reason_wanted}
        </p>

        <EntryStatus entry={entry} section={section} />

        {showComment ? (
          <p>
            <strong>Comment:</strong> {entry.comment}
          </p>
        ) : null}
      </div>

      {section === "needs_check_in" || section === "waiting" ? (
        <footer className="entry-card__actions">
          {section === "needs_check_in" ? (
            <Link to={`/entries/${entry.id}/check-in`}>Check in</Link>
          ) : null}
          <Link to={`/entries/${entry.id}/edit`}>Edit</Link>
        </footer>
      ) : null}
    </article>
  );
}

function sectionLabel(section: DashboardBucket): string {
  switch (section) {
    case "needs_check_in":
      return "Needs check-in";
    case "waiting":
      return "Waiting";
    case "saved":
      return "Saved";
    case "purchased":
      return "Purchased";
  }
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
