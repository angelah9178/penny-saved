import { formatUsd } from "../../lib/currency";
import type { OpportunityCostExample } from "../../types/api";

export type OpportunityCostExampleListProps = {
  examples: OpportunityCostExample[];
};

export function OpportunityCostExampleList({
  examples,
}: OpportunityCostExampleListProps) {
  return (
    <ul
      className="opportunity-cost-list"
      aria-label="Opportunity-cost examples"
    >
      {examples.map((example) => (
        <li key={example.id} className="opportunity-cost-card">
          <div className="opportunity-cost-card__details">
            <h2>{example.label}</h2>
            <p>
              <strong>{formatUsd(example.dollar_value_cents)}</strong> per{" "}
              {example.unit_name}
            </p>
          </div>
          <div className="opportunity-cost-card__actions">
            <button type="button">Edit {example.label}</button>
            <button type="button" className="button--danger">
              Delete {example.label}
            </button>
          </div>
        </li>
      ))}
    </ul>
  );
}
