import { usePersistentDisclosure } from "../../hooks/usePersistentDisclosure";
import type { DashboardBucket, Entry } from "../../types/api";
import { EntryCard } from "./EntryCard";

export type EntrySectionProps = {
  title: string;
  emptyMessage: string;
  entries: Entry[];
  section: DashboardBucket;
  collapsible?: boolean;
  defaultExpanded?: boolean;
  onNotice?: ((message: string) => void) | undefined;
};

export function EntrySection({
  title,
  emptyMessage,
  entries,
  section,
  collapsible = false,
  defaultExpanded = true,
  onNotice,
}: EntrySectionProps) {
  const [isExpanded, setIsExpanded] = usePersistentDisclosure(
    `entries-${section}`,
    defaultExpanded,
  );
  const contentId = `entry-section-${section}-content`;

  return (
    <section className={`entry-section entry-section--${section}`}>
      <h2
        className={
          collapsible ? "entry-section__disclosure-heading" : undefined
        }
      >
        {collapsible ? (
          <button
            aria-label={title}
            aria-controls={contentId}
            aria-expanded={isExpanded}
            className="section-toggle"
            type="button"
            onClick={() => {
              setIsExpanded((expanded) => !expanded);
            }}
          >
            <span aria-hidden="true" className="section-toggle__indicator">
              ▾
            </span>
            <span>{title}</span>
            <span aria-label={`${entries.length} entries`}>
              ({entries.length})
            </span>
          </button>
        ) : (
          <>
            {title}{" "}
            <span aria-label={`${entries.length} entries`}>
              ({entries.length})
            </span>
          </>
        )}
      </h2>

      <div id={contentId} hidden={collapsible && !isExpanded}>
        {entries.length === 0 ? (
          <p className="entry-section__empty">{emptyMessage}</p>
        ) : (
          <ul className="entry-list">
            {entries.map((entry) => (
              <li className="entry-list__item" key={entry.id}>
                <EntryCard
                  entry={entry}
                  section={section}
                  onNotice={onNotice}
                />
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
