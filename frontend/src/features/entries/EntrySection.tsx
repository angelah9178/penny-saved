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
    <section className="entry-section">
      <h2>
        {title}{" "}
        <span aria-label={`${entries.length} entries`}>({entries.length})</span>
      </h2>

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
