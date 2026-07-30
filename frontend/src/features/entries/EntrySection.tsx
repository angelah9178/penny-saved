import type { DashboardBucket, Entry } from "../../types/api";
import { EntryCard } from "./EntryCard";

export type EntrySectionProps = {
  title: string;
  emptyMessage: string;
  entries: Entry[];
  section: DashboardBucket;
};

export function EntrySection({
  title,
  emptyMessage,
  entries,
  section,
}: EntrySectionProps) {
  return (
    <section className={`entry-section entry-section--${section}`}>
      <h2>
        {title}{" "}
        <span aria-label={`${entries.length} entries`}>({entries.length})</span>
      </h2>

      {section === "needs_check_in" && entries.length > 0 ? (
        <p className="entry-section__priority">
          <strong>Action needed:</strong> Review entries whose waiting period is
          complete.
        </p>
      ) : null}

      {entries.length === 0 ? (
        <p className="entry-section__empty">{emptyMessage}</p>
      ) : (
        <ul className="entry-list">
          {entries.map((entry) => (
            <li key={entry.id}>
              <EntryCard entry={entry} section={section} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
