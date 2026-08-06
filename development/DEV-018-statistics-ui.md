# DEV-018 — Statistics and Equivalents UI

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Feature Rules](#feature-rules)
- [API and UI Contract](#api-and-ui-contract)
- [Commit 1 — Define Opportunity-Cost Equivalent Contracts](#commit-1--define-opportunity-cost-equivalent-contracts)
- [Commit 2 — Calculate Equivalents in the Statistics Service](#commit-2--calculate-equivalents-in-the-statistics-service)
- [Commit 3 — Complete Backend Equivalent Verification](#commit-3--complete-backend-equivalent-verification)
- [Commit 4 — Connect the Frontend to Statistics](#commit-4--connect-the-frontend-to-statistics)
- [Commit 5 — Build the Statistics and Equivalents Experience](#commit-5--build-the-statistics-and-equivalents-experience)
- [Commit 6 — Complete States, Cache Refresh, and Verification](#commit-6--complete-states-cache-refresh-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|                  | Commit                                                                  | Title                                  | Depends on  |
| ---------------- | ----------------------------------------------------------------------- | -------------------------------------- | ----------- |
| &#91;&#160;&#93; | [1](#commit-1--define-opportunity-cost-equivalent-contracts)            | Define equivalent contracts            | DEV-016–017 |
| &#91;&#160;&#93; | [2](#commit-2--calculate-equivalents-in-the-statistics-service)         | Calculate equivalents                  | Commit 1    |
| &#91;&#160;&#93; | [3](#commit-3--complete-backend-equivalent-verification)                | Verify backend equivalents             | Commit 2    |
| &#91;&#160;&#93; | [4](#commit-4--connect-the-frontend-to-statistics)                      | Connect frontend statistics            | Commit 3    |
| &#91;&#160;&#93; | [5](#commit-5--build-the-statistics-and-equivalents-experience)         | Build statistics experience            | Commit 4    |
| &#91;&#160;&#93; | [6](#commit-6--complete-states-cache-refresh-and-verification)          | Complete states, refresh, and quality  | Commits 1–5 |

## Objective

DEV-018 turns the existing statistics aggregate and opportunity-cost examples into a
complete dashboard experience. The backend enriches the protected statistics summary
with one equivalent for each of the authenticated user's examples. The frontend lets
the user select a supported range and displays saved money, avoided purchases,
purchased items, and the equivalent units returned by the server.

For example, if the selected range contains 25,000 cents saved and the user has an
example worth 1,000 cents per hour, the summary includes 25 hours:

```json
{
  "range": "this_month",
  "total_saved_cents": 25000,
  "avoided_purchase_count": 4,
  "purchased_count": 1,
  "opportunity_costs": [
    {
      "example_id": "example_id",
      "label": "hours worked",
      "unit_name": "hours",
      "dollar_value_cents": 1000,
      "equivalent_units": 25
    }
  ]
}
```

The backend remains the source of truth for date ranges, saved totals, counts,
equivalent division, and rounding. The browser formats returned values for people to
read; it does not reproduce those business rules.

## Feature Rules

The existing five range values remain unchanged:

```text
this_month
last_3_months
last_6_months
last_year
all_time
```

The statistics service loads examples belonging to the same authenticated user as
the aggregate. For every valid example it calculates:

```text
Decimal(total_saved_cents) / Decimal(dollar_value_cents)
```

The result is quantized to one decimal with `ROUND_HALF_UP`. Exact whole results are
serialized as JSON integers; fractional results are JSON numbers. The frontend must
treat both forms as numeric values and must not depend on a lexical trailing zero such
as `25.0`.

Examples retain the stable order established by DEV-017: `created_at ASC, id ASC`.
An impossible legacy or corrupted zero-value example is skipped and logged safely,
even though request validation and the database constraint prevent new zero values.
The log may identify the example and request context but must not expose credentials,
cookies, or unrelated user data.

The range selection defaults to `this_month`. It may be stored in the URL as
`?range=` so reload, links, and browser navigation preserve the selection. An absent
or unknown URL value falls back safely to `this_month` without sending an invalid API
request.

## API and UI Contract

DEV-018 extends the existing endpoint; it does not introduce a second statistics URL:

```http
GET /api/stats/summary?range=this_month
```

Each opportunity-cost result contains:

| Field                | Meaning                                      |
| -------------------- | -------------------------------------------- |
| `example_id`         | Stable ID used as the frontend list key      |
| `label`              | User-defined comparison label                |
| `unit_name`          | Unit displayed beside the equivalent         |
| `dollar_value_cents` | Integer-cent value used by the backend       |
| `equivalent_units`   | Server-calculated integer or one-decimal value |

The dashboard statistics area provides:

- a labeled control for the five server-supported ranges;
- cards for total saved, avoided-purchase count, and purchased count;
- an opportunity-cost section in stable server order;
- a clear empty state when no examples exist;
- an initial loading state without false zero values;
- a retryable error state that does not masquerade as empty data; and
- a background-updating indicator while keeping the previous summary visible.

Money is formatted from integer cents with `Intl.NumberFormat` in US dollars. Counts
use locale number formatting. Equivalent values are displayed from
`equivalent_units` exactly as returned numerically; the frontend never divides the
saved total by the example value.

## Commit 1 — Define Opportunity-Cost Equivalent Contracts

**Status:** Planned.

### In Plain English

Commit 1 defines the new piece of data that the statistics endpoint can return. It
describes an equivalent's example ID, label, unit, cent value, and calculated number
of units. It then replaces the summary's permanently empty placeholder with a typed
list of those results.

This commit is the rulebook for data crossing the backend boundary. It does not query
PostgreSQL, calculate division, or change the frontend. Later commits can rely on one
strict and tested response shape.

Suggested commit message:

```text
Commit 1: Define opportunity-cost equivalent contracts
```

Implement:

- Add a public opportunity-cost equivalent response schema.
- Include `example_id`, normalized display fields, positive bounded cent value, and
  numeric `equivalent_units`.
- Accept exact whole and one-decimal numeric equivalents without using binary
  floating-point arithmetic during calculation.
- Replace the statistics response's placeholder list with the typed equivalent list.
- Keep ownership fields and ORM details out of the public response.
- Add schema tests for whole and fractional values, zero totals, invalid fields,
  extra fields, strict cents, and serialization.
- Update OpenAPI expectations for the enriched summary schema.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 2 — Calculate Equivalents in the Statistics Service

**Status:** Planned.

### In Plain English

Commit 2 performs the actual opportunity-cost calculation. After the service gets the
saved total for the selected range, it loads only the logged-in user's examples and
divides the total by each example's cent value using exact decimal arithmetic.

It rounds halfway values up to one decimal, preserves the examples' stable order,
and puts the results into Commit 1's response format. A bad zero-value row is skipped
and logged instead of breaking the entire statistics page. There is still no frontend
in this commit.

Suggested commit message:

```text
Commit 2: Add opportunity-cost equivalents to statistics
```

Implement:

- Reuse the DEV-017 owned list repository rather than adding an unscoped query.
- Load examples with the same authenticated `user_id` used by the aggregate.
- Calculate with `Decimal` values created from integer cents.
- Quantize to one decimal with `ROUND_HALF_UP`.
- Serialize exact whole values as integers and fractional values as JSON numbers.
- Preserve repository order and duplicate labels.
- Return an empty list when the user has no examples.
- Return zero equivalents when the selected range has no saved money.
- Defensively skip and safely log an invalid zero divisor.
- Keep one request-clock read for the range and keep repositories transaction-free.
- Add focused service tests for ownership, order, no examples, zero totals, whole and
  fractional results, half-up boundaries, large values, and defensive skipping.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 3 — Complete Backend Equivalent Verification

**Status:** Planned.

### In Plain English

Commit 3 proves that equivalent calculations work through the real protected HTTP
endpoint, not just inside a service test. It creates statistics and example records,
requests each relevant range, and confirms that saved totals and equivalents stay in
sync and remain isolated between users.

It also checks rounding edges, stable ordering, safe database failures, and the
published API documentation. This finishes the backend portion before the frontend
starts depending on it.

Suggested commit message:

```text
Commit 3: Verify statistics opportunity-cost equivalents
```

Implement:

- Add PostgreSQL-backed API tests containing multiple users, ranges, and examples.
- Prove equivalents use the filtered saved total and exclude purchased and waiting
  entry prices.
- Prove other users' entries and examples cannot influence or appear in a response.
- Cover whole, fractional, exact-half, zero-total, large-value, and duplicate-label
  cases.
- Verify stable example order in the final API response.
- Verify invalid zero records are skipped and logged without leaking sensitive data.
- Verify safe `401`, `422`, `500`, and `503` behavior remains intact.
- Verify OpenAPI documents the complete nested response.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 4 — Connect the Frontend to Statistics

**Status:** Planned.

### In Plain English

Commit 4 teaches the frontend how to request a statistics summary and understand the
enriched response. It adds a small API function and a TanStack Query hook whose cache
key includes the selected range, so each filter has the correct cached result.

This is data plumbing only. It does not yet build the visible statistics cards or
range selector. It makes the server response safely available to the UI added by the
next commit.

Suggested commit message:

```text
Commit 4: Connect the frontend to statistics summaries
```

Implement:

- Confirm the shared TypeScript contracts match the backend response exactly.
- Add a credentialed statistics summary API function using the existing API client.
- Send exactly one supported `range` query value.
- Add a query hook using the existing range-aware statistics key factory.
- Keep previous successful data available during range changes where supported by
  the installed TanStack Query version.
- Preserve standard authentication-expiry and API error handling.
- Add API and query tests for URL encoding, every range, response parsing, cache-key
  separation, retained data, errors, and retry behavior.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 5 — Build the Statistics and Equivalents Experience

**Status:** Planned.

### In Plain English

Commit 5 builds what the user sees on the dashboard. It adds the five-option range
control, three summary cards, and a readable list showing what the saved amount means
in each of the user's chosen units.

The UI formats cents as dollars and numbers for display, but trusts the backend's
totals and `equivalent_units`. Changing the filter updates the URL and requests the
matching server summary without a full-page reload.

Suggested commit message:

```text
Commit 5: Build the statistics and equivalents experience
```

Implement:

- Add a statistics feature area with narrow presentational components.
- Add an accessible labeled control containing the exact five API range values.
- Default missing or invalid URL range values to `this_month`.
- Preserve range selection through reload and browser back/forward navigation.
- Render total saved, avoided-purchase count, and purchased count cards.
- Format integer cents as USD and counts with locale-aware formatting.
- Render equivalent label, unit, value, and comparison context in stable server order.
- Use `example_id`, not a label or array index, as each equivalent's key.
- Display integer and fractional JSON numbers without depending on lexical `.0`.
- Compose the statistics experience into the protected dashboard.
- Add component/router tests for every filter, URL fallback, zero statistics, whole
  and fractional equivalents, duplicate labels, large values, and navigation.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Commit 6 — Complete States, Cache Refresh, and Verification

**Status:** Planned.

### In Plain English

Commit 6 makes the experience dependable in real use. It distinguishes loading,
empty examples, server failure, and background refresh; keeps old statistics visible
while a new range loads; and lets the user retry recoverable failures.

It also proves that a completed check-in refreshes statistics so saved money and
equivalents change without a page reload. The query contract is prepared for DEV-019
example mutations to invalidate both example settings and statistics. Finally, it
runs the full repository quality gate and records what actually shipped.

Suggested commit message:

```text
Commit 6: Complete statistics UI states and verification
```

Implement:

- Add a labeled initial loading state that does not show fabricated zero values.
- Keep previous data visible with a non-disruptive updating indicator on range
  changes and background refetches.
- Show a clear no-examples message without confusing it with zero saved money.
- Show recoverable errors with a retry action; never render request failure as empty
  statistics.
- Preserve established session-expiry behavior.
- Verify successful saved and purchased check-ins invalidate all statistics ranges.
- Confirm comment-only changes do not invalidate statistics.
- Provide or verify the shared invalidation helper DEV-019 example mutations will use
  to refresh opportunity-cost lists and statistics.
- Complete semantic headings, accessible names, focus behavior, live announcements,
  keyboard use, and responsive layout within DEV-018's components.
- Add integration tests for initial load, retry, background refresh, rapid range
  changes, cache invalidation, auth expiry, and stale-response safety.
- Update this tracker, statuses, hashes, implementation record, and actual verification
  results after each commit gate passes.

Commit gate:

```bash
make check
```

## Out of Scope

- Creating, editing, or deleting opportunity-cost examples in the frontend; DEV-019
  owns the settings experience.
- Recalculating totals, ranges, or equivalents in TypeScript.
- Custom date ranges, local-time ranges, currencies other than USD, charts, exports,
  projections, goals, budgets, or comparison templates.
- Changing the DEV-016 aggregate rules or DEV-017 example validation and ownership
  rules.
- Final cross-application accessibility, responsive, security, observability, smoke,
  and release work owned by DEV-020 through DEV-024.

## Implementation Record

Complete this section as the commit series is implemented.

### Commit Hashes

- Commit 1: Pending.
- Commit 2: Pending.
- Commit 3: Pending.
- Commit 4: Pending.
- Commit 5: Pending.
- Commit 6: Pending.

### What Changed

Pending implementation.

### What It Achieved

Pending implementation.

### Usage and Safety Notes

The backend owns range, aggregation, decimal division, and rounding rules. The
frontend must use authenticated API data and perform display formatting only.

### Verification

Record the focused gate results after each commit and the final `make check` result
after Commit 6.

### Limitations and Follow-Up

DEV-019 will add opportunity-cost example settings. DEV-020 through DEV-024 will
complete shared hardening and release work.
