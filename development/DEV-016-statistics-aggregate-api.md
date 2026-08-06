# DEV-016 — Statistics Aggregate API

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Feature Rules](#feature-rules)
- [Commit 1 — Define Statistics Ranges and Contracts](#commit-1--define-statistics-ranges-and-contracts)
- [Commit 2 — Calculate Statistics in PostgreSQL](#commit-2--calculate-statistics-in-postgresql)
- [Commit 3 — Build the Statistics Summary Service](#commit-3--build-the-statistics-summary-service)
- [Commit 4 — Expose the Statistics API](#commit-4--expose-the-statistics-api)
- [Commit 5 — Complete Verification and Documentation](#commit-5--complete-verification-and-documentation)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|             | Commit                                                        | Title                              | Depends on  |
| ----------- | ------------------------------------------------------------- | ---------------------------------- | ----------- |
| &#91;x&#93; | [1](#commit-1--define-statistics-ranges-and-contracts)        | Define ranges and contracts        | DEV-013     |
| &#91;x&#93; | [2](#commit-2--calculate-statistics-in-postgresql)            | Calculate statistics in PostgreSQL | Commit 1    |
| &#91;x&#93; | [3](#commit-3--build-the-statistics-summary-service)          | Build the summary service          | Commit 2    |
| &#91;x&#93; | [4](#commit-4--expose-the-statistics-api)                     | Expose the statistics API          | Commit 3    |
| &#91; &#93; | [5](#commit-5--complete-verification-and-documentation)       | Complete verification and docs     | Commits 1–4 |

## Objective

DEV-016 adds a protected backend API that calculates an authenticated user's saved
money, avoided-purchase count, and purchased count for a selected time range:

```http
GET /api/stats/summary?range=this_month
```

The backend uses `checked_in_at`, because money is not confirmed as saved or spent
until the user completes check-in. PostgreSQL calculates all three values in one
user-scoped query. The browser does not reproduce the date or aggregation rules.

Supported ranges:

```text
this_month
last_3_months
last_6_months
last_year
all_time
```

The completed endpoint returns:

```json
{
  "range": "this_month",
  "total_saved_cents": 25000,
  "avoided_purchase_count": 4,
  "purchased_count": 1,
  "opportunity_costs": []
}
```

DEV-016 leaves `opportunity_costs` empty. DEV-017 adds opportunity-cost example CRUD,
and DEV-018 calculates equivalents and builds the frontend statistics experience.

## Feature Rules

Only resolved entries contribute:

| Status      | Saved total       | Avoided count | Purchased count |
| ----------- | ----------------- | ------------- | --------------- |
| `waiting`   | No contribution   | No            | No               |
| `saved`     | Add `price_cents` | Add one       | No               |
| `purchased` | No contribution   | No            | Add one          |

Statistics always belong to the authenticated user. Another user's entries must not
affect the result.

All ranges are half-open:

```text
range_start <= checked_in_at < range_end
```

`range_end` is the request clock read once. `this_month` begins at midnight UTC on
the first day of the current UTC month. Rolling ranges subtract 3, 6, or 12 calendar
months from the request clock. Calendar subtraction clamps an invalid day to the last
day of the target month. `all_time` has no start but still excludes timestamps at or
after the request clock.

## Commit 1 — Define Statistics Ranges and Contracts

**Status:** Complete.

### In Plain English

Commit 1 defines the rules and format for statistics. It:

- Defines the five filters: this month, last 3 months, last 6 months, last year, and
  all time.
- Calculates the exact UTC start and end dates for each filter.
- Handles tricky dates correctly, such as leap years and subtracting three months
  from May 31.
- Defines the response fields for saved money and saved/purchased counts.
- Ensures money and counts are nonnegative whole numbers.
- Adds tests for all these rules.

It does not access the database or create an API endpoint. It builds the foundation
that later commits use to calculate and return statistics.

Suggested commit message:

```text
Commit 1: Define statistics ranges and UTC boundaries
```

Implement:

- Add a string enum containing all five supported range values.
- Add an immutable half-open interval with an optional start and required end.
- Add a pure function that accepts an aware timestamp and normalizes it to UTC.
- Calculate `this_month` from midnight UTC on day one.
- Subtract 3, 6, or 12 calendar months while preserving the time of day and clamping
  invalid target days.
- Give `all_time` no start and the same request-time end.
- Reject naive datetimes.
- Add a strict response schema containing the range, saved cents, two counts, and an
  empty `opportunity_costs` list.
- Require nonnegative strict integers without imposing a 32-bit ceiling.
- Test every range, timezone normalization, month/year boundaries, day clamping,
  leap years, naive timestamps, schema strictness, and large integers.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 2 — Calculate Statistics in PostgreSQL

**Status:** Complete.

### In Plain English

Commit 2 only adds the database calculation for statistics. It:

- Totals the prices of saved entries.
- Counts saved entries.
- Counts purchased entries.
- Filters by the authenticated user and selected date range.
- Ignores waiting entries and other users' data.
- Returns zeros when nothing matches.
- Performs everything in one PostgreSQL query.

It does not add the service, API endpoint, or frontend.

Suggested commit message:

```text
Commit 2: Add the user-scoped statistics aggregate
```

Implement one query equivalent to:

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

Implement:

- Add a typed repository result for the saved total and two counts.
- Require `user_id`, optional `range_start`, and required `range_end`.
- Use filtered aggregates and `COALESCE` so empty results are zeros.
- Filter by `checked_in_at`, not `created_at` or `updated_at`.
- Apply the inclusive start only when it exists and always apply the exclusive end.
- Convert database numeric values directly to Python integers without floating point.
- Perform no commit and never load entry model rows for Python aggregation.
- Add PostgreSQL tests for empty results, mixed statuses, ownership, exact start/end
  boundaries, all-time behavior, and totals above 32-bit range.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 3 — Build the Statistics Summary Service

**Status:** Complete.

### In Plain English

Commit 3 connects the internal backend pieces. It:

1. Reads the current time once.
2. Calculates the exact dates for the selected filter.
3. Calls Commit 2's PostgreSQL statistics calculation.
4. Converts the results into the response format defined in Commit 1.

The first two commits give Commit 3 its inputs and outputs:

- Commit 1 provides the supported range names, the pure function that converts a
  range into exact UTC boundaries, and the strict response format.
- Commit 2 provides the user-scoped database function that accepts those boundaries
  and returns the three calculated values.
- Commit 3 coordinates them: it reads the clock, asks Commit 1 for the boundaries,
  sends those boundaries to Commit 2, and maps Commit 2's result back into Commit 1's
  response format.

The service is still an internal Python function. It connects the backend workflow,
but a browser or frontend cannot call it directly because there is no HTTP endpoint.
Commit 4 adds that doorway.

```text
authenticated user + selected range
                  ↓
             read clock once
                  ↓
          calculate [start, end)
                  ↓
       call the PostgreSQL aggregate
                  ↓
       return the response object
```

Suggested commit message:

```text
Commit 3: Build the statistics summary service
```

Implement:

- Add a service operation requiring the database session, authenticated user ID,
  selected range, and injected clock.
- Read the clock exactly once.
- Pass the calculated start and end to the repository aggregate.
- Map the aggregate into the strict response schema.
- Echo the selected range and return `opportunity_costs: []`.
- Preserve exact integer cents and counts.
- Allow failures to reach the established safe API error handling added in Commit 4.
- Add service tests for every range, one clock read, exact repository arguments,
  empty and large results, response mapping, and propagated repository failures.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 4 — Expose the Statistics API

**Status:** Complete.

### In Plain English

“Expose the API” means adding a URL that authorized clients can call. Before Commit
4, the statistics workflow exists only as an internal Python function, and the
frontend cannot call that function directly.

Commit 4 adds the actual API endpoint:

```http
GET /api/stats/summary?range=this_month
```

When the frontend calls it, the backend:

1. Confirms the user is logged in.
2. Validates the requested range.
3. Calls Commit 3's statistics service.
4. Returns the calculated statistics as JSON.

```json
{
  "range": "this_month",
  "total_saved_cents": 25000,
  "avoided_purchase_count": 4,
  "purchased_count": 1,
  "opportunity_costs": []
}
```

The route is a safe doorway. It does not contain SQL, date arithmetic, or aggregation
logic. DEV-018 later calls this endpoint from the frontend and renders the cards and
filters.

Suggested commit message:

```text
Commit 4: Expose the protected statistics summary API
```

Implement:

- Add and register a statistics router with a `/stats` prefix.
- Add the authenticated `GET /api/stats/summary` route.
- Require and parse the supported `range` enum query parameter.
- Inject the existing database session, authenticated user, and overrideable clock.
- Delegate directly to the Commit 3 service.
- Declare the strict statistics response model.
- Document success, unauthorized, validation, unavailable, and unexpected-error
  responses using the established safe envelopes.
- Do not require mutation-only origin validation for this read-only route.
- Add API and OpenAPI tests for all ranges, authentication, missing/repeated/invalid
  range values, zero and large results, database failures, and cross-user isolation.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 5 — Complete Verification and Documentation

**Status:** Implemented and verified; pending Git commit.

### In Plain English

Commit 5 proves the pieces work safely together. It tests entries immediately before,
exactly at, and immediately after date boundaries; checks month and leap-year edges;
and confirms other users, waiting entries, and future check-ins cannot affect the
result.

It also records what was actually implemented and runs the entire repository quality
gate. It does not add a frontend or opportunity-cost calculations.

Suggested commit message:

```text
Commit 5: Complete statistics API verification and documentation
```

Implement:

- Add an end-to-end backend boundary matrix for inclusive starts and exclusive ends.
- Cover month/year transitions, day clamping, leap years, and a request exactly at
  month start.
- Prove `checked_in_at` controls the range regardless of creation or edit timestamps.
- Prove saved/purchased rules across mixed users and statuses.
- Prove empty responses use JSON zeros and large totals remain exact integers.
- Confirm invalid input and backend failures use safe non-disclosing envelopes.
- Confirm the implementation uses one aggregate query and does not load all entries.
- Update this tracker, statuses, hashes, implementation record, and actual test results
  after each corresponding gate passes.

Commit gate:

```bash
make check
```

## Out of Scope

- Opportunity-cost example CRUD; DEV-017 owns it.
- Opportunity-cost equivalent calculation and the statistics frontend; DEV-018 owns
  them.
- Opportunity-cost settings screens; DEV-019 owns them.
- Currency conversion, floating-point money, local-time or fiscal ranges, custom date
  ranges, charts, exports, and projections.
- Changing resolved outcomes or `checked_in_at` timestamps.
- Aggregate caches or precomputed tables before measured growth requires them.
- Final shared hardening and release work owned by DEV-020 through DEV-024.

## Implementation Record

### Commit Hashes

- Commit 1: `df6f815` (`Commit 1: Define statistics ranges and UTC boundaries`).
- Commit 2: `678170c` (`Commit 2: Add the user-scoped statistics aggregate`).
- Commit 3: `17432de` (`Commit 3: Build the statistics summary service`).
- Commit 4: `04ba148` (`Commit 4: Expose the protected statistics summary API`).
- Commit 5: Pending.

### What Changed

- Commit 1 added the five-value range enum, immutable UTC half-open interval,
  calendar-month boundary calculation, strict response contract, and focused tests.
- Commit 2 added the single user-scoped PostgreSQL conditional aggregate, typed result,
  half-open `checked_in_at` filtering, empty-result zeros, and repository integration
  coverage.
- Commit 3 added the internal summary service that reads the clock once, calculates
  the selected interval, calls the Commit 2 aggregate, and maps its values into the
  Commit 1 response contract.
- Commit 4 added the protected statistics router and summary endpoint, strict range
  parsing, safe response documentation, router registration, and focused API/OpenAPI
  coverage.
- Commit 5 added PostgreSQL-backed cross-layer API coverage for exact boundaries,
  mixed statuses, ownership isolation, future timestamps, large totals, empty JSON
  zeros, and the single aggregate-query shape.

### What It Achieved

Later commits now have one tested definition of every range and one strict response
shape for exact integer statistics.

Commit 2 calculates saved cents, avoided decisions, and purchased decisions in one
database query without materializing entry rows in Python.

Commit 3 connects those earlier pieces into one reusable backend workflow. Commit 4
now makes that workflow callable by authenticated clients through one read-only HTTP
endpoint.

Commit 5 proves the complete request path preserves the approved range, ownership,
status, money, and query-efficiency rules.

### Usage and Safety Notes

The endpoint delegates all date and aggregate work to the service, does not require
mutation-only origin validation, and returns only safe error envelopes. No frontend
has been added.

### Verification

- Commit 1 focused unit/schema suite: 24 passed.
- Backend Ruff formatting and lint: passed.
- Commit 2 focused PostgreSQL repository suite: 4 passed.
- Commit 3 focused unit/schema/service suite: 31 passed.
- Commit 4 focused API/service suite: 19 passed.
- Commit 5 cross-layer PostgreSQL API suite: 2 passed.
- Final backend suite against PostgreSQL: 408 passed.
- Final frontend suite: 308 passed across 37 test files.
- Final frontend/backend formatting and lint: passed.
- Final frontend typecheck: passed.
- Final frontend production build and backend application construction: passed.
- Final `make check`: passed.

### Limitations and Follow-Up

DEV-017 adds opportunity-cost examples. DEV-018 calculates equivalents and builds the
statistics UI. DEV-019 adds settings management. DEV-020 through DEV-024 complete
hardening and release work.
