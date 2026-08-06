import { formatUsd } from "../../lib/currency";
import type { OpportunityCostExample } from "../../types/api";
import { DeleteOpportunityCostExampleButton } from "./DeleteOpportunityCostExampleButton";

export type OpportunityCostExampleListProps = {
  examples: OpportunityCostExample[];
  onEdit?: ((example: OpportunityCostExample) => void) | undefined;
  onDeleted?: ((example: OpportunityCostExample) => void) | undefined;
  onDeleteStale?:
    | ((example: OpportunityCostExample) => Promise<void> | void)
    | undefined;
};

export function OpportunityCostExampleList({
  examples,
  onEdit,
  onDeleted,
  onDeleteStale,
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
            <button type="button" onClick={() => onEdit?.(example)}>
              Edit {example.label}
            </button>
            <DeleteOpportunityCostExampleButton
              example={example}
              onDeleted={onDeleted}
              onStale={onDeleteStale}
            />
          </div>
        </li>
      ))}
    </ul>
  );
}
