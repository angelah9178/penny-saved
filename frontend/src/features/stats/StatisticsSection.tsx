import { useSearchParams } from "react-router-dom";

import { ErrorAlert } from "../../components/ErrorAlert";
import { FeedbackMessage } from "../../components/FeedbackMessage";
import { Loading } from "../../components/Loading";
import { formatUsd } from "../../lib/currency";
import { usePersistentDisclosure } from "../../hooks/usePersistentDisclosure";
import type { OpportunityCostEquivalent, StatsRange } from "../../types/api";
import { useStatsSummary } from "./queries";

const DEFAULT_RANGE = "this_month" satisfies StatsRange;
const RANGE_OPTIONS: ReadonlyArray<{ value: StatsRange; label: string }> = [
  { value: "this_month", label: "This month" },
  { value: "last_3_months", label: "Last 3 months" },
  { value: "last_6_months", label: "Last 6 months" },
  { value: "last_year", label: "Last year" },
  { value: "all_time", label: "All time" },
];
const RANGE_VALUES = new Set<StatsRange>(
  RANGE_OPTIONS.map(({ value }) => value),
);
const NUMBER_FORMATTER = new Intl.NumberFormat("en-US", {
  maximumFractionDigits: 1,
});

export function StatisticsSection() {
  const [isExpanded, setIsExpanded] = usePersistentDisclosure(
    "statistics",
    true,
  );
  const [searchParams, setSearchParams] = useSearchParams();
  const range = parseStatsRange(searchParams.get("range"));
  const summary = useStatsSummary(range);

  function selectRange(selectedRange: StatsRange) {
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("range", selectedRange);
      return next;
    });
  }

  return (
    <section className="statistics" aria-labelledby="statistics-heading">
      <h2 id="statistics-heading" className="statistics__disclosure-heading">
        <button
          aria-controls="statistics-content"
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
          <span>Savings statistics</span>
        </button>
      </h2>

      <div
        className="statistics__collapsible-content"
        id="statistics-content"
        hidden={!isExpanded}
      >
        <div className="statistics__header">
          <p>See what your completed decisions have added up to.</p>
          <div className="statistics__filter">
            <label htmlFor="statistics-range">Time range</label>
            <select
              id="statistics-range"
              value={range}
              onChange={(event) => {
                selectRange(event.target.value as StatsRange);
              }}
            >
              {RANGE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {summary.isPending ? (
          <Loading message="Loading your statistics…" />
        ) : null}
        {summary.isError ? (
          <ErrorAlert
            message="We could not load your statistics. Please try again."
            isRetrying={summary.isFetching}
            retryLabel="Retry statistics"
            retryingLabel="Retrying statistics…"
            onRetry={() => {
              void summary.refetch();
            }}
          />
        ) : null}
        {summary.isFetching && summary.data !== undefined ? (
          <FeedbackMessage
            className="statistics__updating"
            message="Updating statistics…"
            tone="status"
          />
        ) : null}
        {summary.data === undefined ? null : (
          <>
            <dl className="statistics__cards">
              <StatisticCard
                label="Total saved"
                value={formatUsd(summary.data.total_saved_cents)}
              />
              <StatisticCard
                label="Purchases avoided"
                value={NUMBER_FORMATTER.format(
                  summary.data.avoided_purchase_count,
                )}
              />
              <StatisticCard
                label="Items purchased"
                value={NUMBER_FORMATTER.format(summary.data.purchased_count)}
              />
            </dl>
            <OpportunityCostList equivalents={summary.data.opportunity_costs} />
          </>
        )}
      </div>
    </section>
  );
}

function StatisticCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="statistics__card">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function OpportunityCostList({
  equivalents,
}: {
  equivalents: OpportunityCostEquivalent[];
}) {
  return (
    <div className="statistics__equivalents">
      <h3>What your savings are worth</h3>
      {equivalents.length === 0 ? (
        <p className="statistics__empty">
          Add opportunity-cost examples to see your savings in everyday terms.
        </p>
      ) : (
        <ul className="statistics__equivalent-list">
          {equivalents.map((equivalent) => (
            <li key={equivalent.example_id}>
              <span className="statistics__equivalent-value">
                {NUMBER_FORMATTER.format(equivalent.equivalent_units)}{" "}
                {equivalent.unit_name}
              </span>
              <span>
                {equivalent.label} at {formatUsd(equivalent.dollar_value_cents)}{" "}
                each
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function parseStatsRange(value: string | null): StatsRange {
  return value !== null && RANGE_VALUES.has(value as StatsRange)
    ? (value as StatsRange)
    : DEFAULT_RANGE;
}
