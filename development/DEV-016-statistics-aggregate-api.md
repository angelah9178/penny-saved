# DEV-016 — Statistics Aggregate API

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Statistics in Plain English](#statistics-in-plain-english)
- [Range Semantics](#range-semantics)
- [Route and API Contract](#route-and-api-contract)
- [Commit 1 — Define Statistics Ranges and Boundaries](#commit-1--define-statistics-ranges-and-boundaries)
- [Commit 2 — Add the Conditional Statistics Aggregate](#commit-2--add-the-conditional-statistics-aggregate)
- [Commit 3 — Build the Statistics Summary Service](#commit-3--build-the-statistics-summary-service)
- [Commit 4 — Expose the Protected Statistics API](#commit-4--expose-the-protected-statistics-api)
- [Commit 5 — Complete Boundary, Failure, and Contract Verification](#commit-5--complete-boundary-failure-and-contract-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the implementation and commit gate for that row are
complete.

|             | Commit                                                               | Title                                | Depends on  |
| ----------- | -------------------------------------------------------------------- | ------------------------------------ | ----------- |
| &#91; &#93; | [1](#commit-1--define-statistics-ranges-and-boundaries)              | Define ranges and UTC boundaries     | DEV-013     |
| &#91; &#93; | [2](#commit-2--add-the-conditional-statistics-aggregate)             | Add the conditional aggregate        | Commit 1    |
| &#91; &#93; | [3](#commit-3--build-the-statistics-summary-service)                 | Build the summary service            | Commit 2    |
| &#91; &#93; | [4](#commit-4--expose-the-protected-statistics-api)                  | Expose the protected API             | Commit 3    |
| &#91; &#93; | [5](#commit-5--complete-boundary-failure-and-contract-verification)  | Complete verification and docs       | Commits 1–4 |

## Objective

DEV-016 gives an authenticated user a server-calculated summary of resolved impulse
purchases for one supported time range:

```text
GET /api/stats/summary?range=this_month
```

The response reports the amount avoided through saved decisions, the number of saved
decisions, and the number of purchased decisions. The backend calculates all three
values from one user-scoped PostgreSQL aggregate and uses `checked_in_at`, because an
entry does not become a confirmed saving or purchase until check-in.

Every request reads the authoritative UTC clock once. That timestamp is the exclusive
end of the selected range. A pure boundary function derives the optional inclusive
start, and the repository applies the half-open interval `[start, end)` without
loading entries into Python.

DEV-016 establishes the statistics response shape needed by later work. Its
`opportunity_costs` collection is empty; DEV-017 creates the example records and
DEV-018 extends the summary service to calculate and populate equivalents.

Complete and commit each section in order. Every commit must leave backend formatting,
lint, type checking where configured, and focused tests green. Commit 5 runs the full
repository quality gate.

## Statistics in Plain English

Only completed decisions affect statistics:

| Stored status | Total saved | Avoided count | Purchased count |
| ------------- | ----------- | ------------- | --------------- |
| `waiting`     | No          | No            | No               |
| `saved`       | Add price   | Add one       | No               |
| `purchased`   | No          | No            | Add one          |

For example, a saved $120 item and a purchased $40 item in the selected range produce:

```json
{
  "range": "this_month",
  "total_saved_cents": 12000,
  "avoided_purchase_count": 1,
  "purchased_count": 1,
  "opportunity_costs": []
}
```

The entry creation date is irrelevant to this calculation. An item created in January
and checked in as saved in March belongs to a March statistics range. A waiting item
never contributes, even if it has been waiting for more than 48 hours.

All database reads are scoped to the authenticated `user_id`. A user's summary must
not change when another user creates or resolves an entry.

## Range Semantics

The API supports exactly these values:

| Query value     | Inclusive start                                            | Exclusive end |
| --------------- | ---------------------------------------------------------- | ------------- |
| `this_month`    | 00:00:00 UTC on day 1 of the request clock's UTC month      | Request clock |
| `last_3_months` | Request clock minus 3 calendar months                      | Request clock |
| `last_6_months` | Request clock minus 6 calendar months                      | Request clock |
| `last_year`     | Request clock minus 12 calendar months                     | Request clock |
| `all_time`      | No start                                                    | Request clock |

Every interval is half-open:

```text
start <= checked_in_at < end
```

An entry exactly at `start` is included. An entry exactly at the request clock is
excluded. The exclusive end prevents a record committed after the clock was sampled
from leaking into a response whose range was calculated earlier.

“Calendar months” does not mean 90, 180, or 365 days. Subtraction keeps the UTC time
of day and the day of month when possible, then clamps to the last valid day in the
target month. Examples:

```text
2026-08-05T14:30:00Z minus 3 months  = 2026-05-05T14:30:00Z
2026-05-31T14:30:00Z minus 3 months  = 2026-02-28T14:30:00Z
2024-02-29T14:30:00Z minus 12 months = 2023-02-28T14:30:00Z
```

The boundary helper accepts only timezone-aware values, normalizes them to UTC, and
returns a small immutable range object containing `start` and `end`. It performs no
database or system-clock access, which keeps all month-edge behavior deterministic.

## Route and API Contract

### Request

```http
GET /api/stats/summary?range=last_3_months
Cookie: session=...
```

`range` is required and parsed as the supported enum. Missing, repeated, or unknown
values are rejected with the established validation response rather than silently
changing the requested period.

### Success

```json
{
  "range": "last_3_months",
  "total_saved_cents": 25000,
  "avoided_purchase_count": 4,
  "purchased_count": 1,
  "opportunity_costs": []
}
```

All monetary values are integer cents. Counts and totals are nonnegative integers.
PostgreSQL and Python must preserve totals beyond 32-bit integer range without float
conversion. An empty range returns zeros, never `null`.

### Failures

| Situation                              | Status | Error code           |
| -------------------------------------- | -----: | -------------------- |
| Missing or expired session             |  `401` | `unauthorized`       |
| Missing, repeated, or unsupported range|  `422` | `validation_error`   |
| Database unavailable                   |  `503` | Established safe code|
| Unexpected server failure              |  `500` | Established safe code|

This is a read-only route, so state-changing origin validation does not apply. It
still uses the common request ID, authentication dependency, database dependency,
safe error envelopes, and OpenAPI response documentation.

## Commit 1 — Define Statistics Ranges and Boundaries

**Status:** Planned.

Commit 1 defines the public vocabulary and pure time calculation used by every later
layer. It does not query PostgreSQL or register a route.

Suggested commit message:

```text
Commit 1: Define statistics ranges and UTC boundaries
```

Implement:

- Add a string enum for `this_month`, `last_3_months`, `last_6_months`, `last_year`,
  and `all_time`.
- Add an immutable value object containing `start: datetime | None` and
  `end: datetime`.
- Add one pure function that normalizes an aware request time to UTC and calculates
  the selected half-open interval.
- Start `this_month` at midnight UTC on the first day of the current UTC month.
- Subtract 3, 6, or 12 calendar months for rolling ranges, preserving time and
  clamping invalid target days to the target month's last day.
- Give `all_time` a `None` start while retaining the same exclusive request-time end.
- Reject naive datetimes through the established UTC normalization behavior.
- Define the strict response schemas for the range, three aggregate values, and an
  empty `opportunity_costs` list ready for DEV-018's equivalent schema.
- Constrain response totals and counts to nonnegative integers without imposing a
  32-bit ceiling.
- Add focused unit and schema tests for all enum values and response serialization.

Required boundary examples:

- A normal date and time for every supported range.
- January-to-previous-year subtraction.
- A 31st clamped into a 30-day month and February.
- Leap-day subtraction into a non-leap year.
- `this_month` when the clock is exactly at month start.
- A non-UTC aware input normalized before boundaries are calculated.
- A naive input rejected.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 2 — Add the Conditional Statistics Aggregate

**Status:** Planned.

Commit 2 adds the only statistics database query. It must aggregate in PostgreSQL and
return one small result object; it must not select resolved entries for Python to sum
or count.

The query is equivalent to:

```sql
SELECT
  COALESCE(SUM(price_cents) FILTER (WHERE status = 'saved'), 0),
  COUNT(*) FILTER (WHERE status = 'saved'),
  COUNT(*) FILTER (WHERE status = 'purchased')
FROM impulse_purchase_entries
WHERE user_id = :user_id
  AND status IN ('saved', 'purchased')
  AND (:range_start IS NULL OR checked_in_at >= :range_start)
  AND checked_in_at < :range_end;
```

Suggested commit message:

```text
Commit 2: Add the user-scoped statistics aggregate
```

Implement:

- Add a typed repository result containing `total_saved_cents`,
  `avoided_purchase_count`, and `purchased_count`.
- Build one SQLAlchemy statement using filtered aggregates and `COALESCE` for the
  saved total.
- Require `user_id`, optional `range_start`, and required `range_end` parameters.
- Apply `checked_in_at >= range_start` only when a start exists and always apply
  `checked_in_at < range_end`.
- Restrict candidate rows to `saved` and `purchased` before aggregation.
- Convert database numeric/count results to Python integers without passing through
  floating point.
- Keep transaction ownership outside the repository; this read performs no commit.

Repository tests must use PostgreSQL and prove:

- Empty datasets and ranges return three zeros.
- Saved prices contribute to the total and avoided count only.
- Purchased entries contribute to the purchased count only.
- Waiting entries never contribute.
- The query uses `checked_in_at`, not `created_at` or `updated_at`.
- A row exactly at `range_start` is included and one exactly at `range_end` is
  excluded.
- `None` start includes old resolved rows but still respects the exclusive end.
- Other-user rows do not contribute.
- Multiple saved prices sum correctly, including a total larger than 32-bit integer
  range.
- The implementation executes one aggregate statement and does not materialize entry
  model rows.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 3 — Build the Statistics Summary Service

**Status:** Planned.

Commit 3 connects the request clock, boundary calculation, repository aggregate, and
response mapper. The service is the use-case boundary; the router in Commit 4 remains
thin.

```text
authenticated user + requested range
                  ↓
           read UTC clock once
                  ↓
        calculate [start, end)
                  ↓
     one user-scoped database aggregate
                  ↓
       validated statistics response
```

Suggested commit message:

```text
Commit 3: Build the statistics summary service
```

Implement:

- Add a service operation requiring the database session, authenticated `user_id`,
  parsed range enum, and injected clock.
- Read `clock.now()` exactly once and use that value for both `range_end` and all
  boundary calculations.
- Pass the calculated start and end directly to the repository aggregate.
- Map the repository values and requested enum into the strict response schema.
- Return `opportunity_costs: []` until DEV-018 adds equivalent calculation.
- Preserve integer cents and counts without formatting currency in the backend.
- Let the established database and unexpected-error handlers translate failures; do
  not expose SQL, credentials, user IDs, or internal exception messages.

Add service tests proving every range maps to the exact expected repository arguments,
the clock is read once, aggregate values map without loss, empty results remain zeros,
the response echoes the selected range, and repository failures propagate for common
safe handling.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 4 — Expose the Protected Statistics API

**Status:** Planned.

Commit 4 makes the summary available to authenticated clients. The route parses HTTP
input and calls the service; it contains no SQL, date arithmetic, or aggregation.

Suggested commit message:

```text
Commit 4: Expose the protected statistics summary API
```

Implement:

- Add a statistics router with the `/stats` prefix and register it in the top-level
  API router.
- Add `GET /api/stats/summary` with a required `range` query parameter typed as the
  supported enum.
- Require the existing authenticated-user and async-database dependencies.
- Inject the established overrideable UTC clock for deterministic API tests.
- Delegate to the statistics service and declare the strict summary response model.
- Document successful, unauthorized, validation, unavailable, and unexpected-safe
  responses in OpenAPI using established helpers.
- Keep the route read-only and do not require the mutation-only origin dependency.

API tests must cover authenticated success for every range, missing and expired
sessions, missing/unknown/repeated range values, zero-result serialization, integer
totals, response-field strictness, database failure envelopes, and absence of
cross-user data. Assert the generated OpenAPI operation advertises the enum and all
documented responses.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 5 — Complete Boundary, Failure, and Contract Verification

**Status:** Planned.

Commit 5 closes gaps across the earlier layers and records the implementation that
actually shipped. It should not broaden DEV-016 into frontend or opportunity-cost
work.

Suggested commit message:

```text
Commit 5: Complete statistics API verification and documentation
```

Implement:

- Add an integration matrix that places entries immediately before, exactly at, and
  immediately after each meaningful start and end boundary.
- Cover month and year transitions, target-month day clamping, leap years, and a
  request made exactly at the first instant of a month.
- Prove a future `checked_in_at` value is excluded from `all_time` by the common
  exclusive end.
- Prove creation and later edit timestamps cannot move an entry between ranges.
- Prove saved and purchased inclusion rules with mixed statuses, users, and prices in
  one dataset.
- Confirm empty results are JSON zeros and large cent totals remain exact integers.
- Confirm invalid input and backend failures retain the common non-disclosing error
  envelope and request ID behavior.
- Review query shape or statement-count evidence to ensure no all-entry load or
  per-entry query was introduced.
- Update this tracker, each status, and the implementation record with actual commit
  hashes and verification results only after the corresponding work is complete.

Commit gate:

```bash
make check
```

## Out of Scope

- Opportunity-cost example CRUD; DEV-017 owns it.
- Loading examples or calculating and rounding equivalent units; DEV-018 owns it.
- Statistics cards, range controls, loading states, and frontend query integration;
  DEV-018 owns them.
- Opportunity-cost settings screens; DEV-019 owns them.
- Changing check-in outcomes or timestamps after resolution.
- Currency conversion, floating-point money, fiscal/local-time ranges, custom date
  ranges, charts, exports, pagination, or lifetime projections.
- Caching or precomputed aggregate tables. The indexed V1 aggregate remains the
  approved design until measured growth justifies a different strategy.
- Final cross-feature accessibility, production observability, abuse protection, and
  end-to-end release coverage; DEV-020 through DEV-024 own those concerns.

## Implementation Record

### Commit Hashes

- Commit 1: Pending.
- Commit 2: Pending.
- Commit 3: Pending.
- Commit 4: Pending.
- Commit 5: Pending.

### What Changed

Pending implementation.

### What It Achieved

Pending implementation.

### Usage and Safety Notes

Pending implementation.

### Verification

Pending implementation.

### Limitations and Follow-Up

DEV-017 adds opportunity-cost example CRUD. DEV-018 fills the response's
`opportunity_costs` collection and builds the statistics UI. DEV-019 adds settings
management. DEV-020 through DEV-024 complete shared hardening and release work.
