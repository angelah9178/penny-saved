# DEV-017 — Opportunity-Cost Example API

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Feature Rules](#feature-rules)
- [Route and API Contract](#route-and-api-contract)
- [Commit 1 — Define Opportunity-Cost Contracts](#commit-1--define-opportunity-cost-contracts)
- [Commit 2 — Add Owned Example Repositories](#commit-2--add-owned-example-repositories)
- [Commit 3 — Create and List Opportunity-Cost Examples](#commit-3--create-and-list-opportunity-cost-examples)
- [Commit 4 — Update and Delete Opportunity-Cost Examples](#commit-4--update-and-delete-opportunity-cost-examples)
- [Commit 5 — Complete Security and Verification](#commit-5--complete-security-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|             | Commit                                                            | Title                          | Depends on  |
| ----------- | ----------------------------------------------------------------- | ------------------------------ | ----------- |
| &#91; &#93; | [1](#commit-1--define-opportunity-cost-contracts)             | Define contracts               | DEV-005     |
| &#91; &#93; | [2](#commit-2--add-owned-example-repositories)                | Add owned repositories         | Commit 1    |
| &#91; &#93; | [3](#commit-3--create-and-list-opportunity-cost-examples)     | Create and list examples       | Commit 2    |
| &#91; &#93; | [4](#commit-4--update-and-delete-opportunity-cost-examples)   | Update and delete examples     | Commit 3    |
| &#91; &#93; | [5](#commit-5--complete-security-and-verification)            | Complete security and quality  | Commits 1–4 |

## Objective

DEV-017 lets an authenticated user manage the personal comparisons that later make
saved money easier to understand. An example might say that 1,000 cents represents
one hour of work:

```json
{
  "label": "hours worked",
  "unit_name": "hours",
  "dollar_value_cents": 1000
}
```

The backend provides protected create, list, update, and delete operations. Every
database access is scoped to the authenticated user. Text is normalized, money stays
in integer cents, duplicate labels remain allowed, and list ordering is stable.

DEV-017 stores and manages examples only. DEV-018 loads them into statistics,
calculates equivalent units, and builds the frontend display. DEV-019 builds the
frontend settings screens.

## Feature Rules

An opportunity-cost example contains:

| Field                | Rule                                      |
| -------------------- | ----------------------------------------- |
| `label`              | Trimmed, nonblank, at most 120 characters |
| `unit_name`          | Trimmed, nonblank, at most 80 characters  |
| `dollar_value_cents` | Strict integer from 1 to 999,999,999,999  |

For example:

```text
label: "  hours worked  "       → "hours worked"
unit_name: " hours "             → "hours"
dollar_value_cents: 1000         → accepted
dollar_value_cents: 0            → rejected
dollar_value_cents: "1000"       → rejected instead of converted
```

Duplicate labels are allowed. A user may intentionally define two “hours worked”
examples with different cent values. Stable list order is `created_at ASC, id ASC`,
so duplicates and timestamp ties never appear in random order.

Repositories stage changes but never commit. Services own commits and rollbacks and
read the injected UTC clock once per mutation. Updates and deletes lock the owned row
before changing it.

## Route and API Contract

```text
GET    /api/opportunity-cost-examples
POST   /api/opportunity-cost-examples
PATCH  /api/opportunity-cost-examples/{example_id}
DELETE /api/opportunity-cost-examples/{example_id}
```

Create and update accept exactly these mutable fields:

```json
{
  "label": "hours worked",
  "unit_name": "hours",
  "dollar_value_cents": 1000
}
```

Create returns `201 Created`; update returns `200 OK`. Both return:

```json
{
  "example": {
    "id": "example_id",
    "label": "hours worked",
    "unit_name": "hours",
    "dollar_value_cents": 1000,
    "created_at": "2026-07-15T12:00:00Z",
    "updated_at": "2026-07-15T12:00:00Z"
  }
}
```

List returns examples in stable creation order. Delete returns an empty `204 No
Content` response.

| Situation                         | Status | Error code         |
| --------------------------------- | -----: | ------------------ |
| Missing or expired session        |  `401` | `unauthorized`     |
| Example belongs to another user   |  `403` | `forbidden`        |
| Example ID does not exist         |  `404` | `not_found`        |
| Invalid UUID, fields, or body     |  `422` | `validation_error` |
| Database unavailable              |  `503` | `service_unavailable` |
| Unexpected server failure         |  `500` | `internal_error`   |

Create, update, and delete use the established state-changing origin protection. GET
is read-only and does not require that mutation-only dependency.

## Commit 1 — Define Opportunity-Cost Contracts

**Status:** Planned.

### In Plain English

Commit 1 defines what valid opportunity-cost data looks like. It decides which fields
the user may send, trims accidental outer spaces, rejects blank or oversized text,
and requires a positive whole-number cent value.

It also defines the JSON returned to clients. It does not read or change the database
and does not add an API URL yet. Later commits use these contracts as their shared
rulebook.

Suggested commit message:

```text
Commit 1: Define opportunity-cost example contracts
```

Implement:

- Add strict create and update request schemas containing only `label`, `unit_name`,
  and `dollar_value_cents`.
- Normalize label and unit by trimming outer whitespace before validation.
- Reject blank label/unit values after normalization.
- Enforce the database lengths of 120 and 80 characters.
- Require strict integer cents between 1 and `999_999_999_999`.
- Reject unknown fields such as `id`, `user_id`, `created_at`, or `updated_at`.
- Add the public example response, single-example envelope, and list response.
- Serialize timestamps as UTC-aware datetimes and omit `user_id` from public data.
- Add schema tests for normalization, blanks, exact limits, over-limit values, cents
  boundaries, wrong types, extra fields, and serialization.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 2 — Add Owned Example Repositories

**Status:** Planned.

### In Plain English

Commit 2 adds the database operations. Every operation requires the logged-in user's
ID, so one user cannot list or change another user's examples.

It can stage a new example, list examples in a predictable order, find and lock one
owned example, update its allowed values, and stage deletion. It does not commit
transactions or expose API endpoints; later services decide when work commits or
rolls back.

Suggested commit message:

```text
Commit 2: Add owned opportunity-cost repositories
```

Implement:

- Add a create helper assigning the owner, ID, normalized fields, and server times.
- Add a user-scoped list query ordered by `created_at ASC, id ASC`.
- Add user-scoped reads by ID, including a `SELECT ... FOR UPDATE` variant for
  update/delete.
- Add an ID-only existence check used only after an owned lookup misses.
- Add narrow update and delete helpers that verify ownership before staging changes.
- Change only label, unit, dollar value, and `updated_at` during update.
- Keep repositories free of commits and rollbacks.
- Add PostgreSQL tests for staging, ordering ties, duplicates, ownership isolation,
  row locking, existence checks, protected fields, delete staging, and constraints.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 3 — Create and List Opportunity-Cost Examples

**Status:** Planned.

### In Plain English

Commit 3 makes the first two user workflows available: creating an example and seeing
all of your examples. The service reads the server clock, stages a normalized example,
commits it, and returns public JSON. Listing asks the repository only for the current
user's examples and preserves their stable order.

This commit also adds the protected POST and GET URLs. Other users' records never
appear, duplicate labels are accepted, and a failed create rolls back completely.

Suggested commit message:

```text
Commit 3: Create and list opportunity-cost examples
```

Implement:

- Add response mapping that never exposes `user_id` or ORM internals.
- Add a create service that reads the clock once and owns commit/rollback.
- Add a list service that returns the repository's stable owned order.
- Add the `/opportunity-cost-examples` router and register it under `/api`.
- Add authenticated `POST` returning `201` and authenticated `GET` returning `200`.
- Require trusted origin for POST but not GET.
- Document authentication, validation, database, and unexpected safe errors.
- Add service/API tests for normalization, timestamps, duplicate labels, ordering,
  authentication, origin enforcement, rollback, response shape, and empty lists.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 4 — Update and Delete Opportunity-Cost Examples

**Status:** Planned.

### In Plain English

Commit 4 completes editing and deletion. Before either operation, the backend finds
the example using both the logged-in user ID and example ID and locks the row. Update
changes only the three allowed fields and update time. Delete removes the owned row
and returns no response body.

If the owned lookup misses, the backend safely distinguishes an existing other-user
ID (`403`) from a truly missing ID (`404`) without returning private example data.
Every failure rolls back the transaction.

Suggested commit message:

```text
Commit 4: Update and delete opportunity-cost examples
```

Implement:

- Add locked update and delete services with service-owned transactions.
- Use the ID-only existence check after an owned miss to produce the required safe
  `403` versus `404` result.
- Preserve owner, ID, and `created_at` during updates.
- Read the clock once for a successful update and assign only `updated_at`.
- Add `PATCH /api/opportunity-cost-examples/{example_id}` returning the example
  envelope.
- Add `DELETE /api/opportunity-cost-examples/{example_id}` returning an empty `204`.
- Require authentication and trusted origin for both mutations.
- Add tests for success, normalization, locks, preservation, malformed UUID, strict
  fields, `403`/`404`, rollback, empty delete body, and safe failure envelopes.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 5 — Complete Security and Verification

**Status:** Planned.

### In Plain English

Commit 5 proves all four operations work safely together. It follows examples through
create, ordered list, update, and delete; confirms users remain isolated; and checks
that invalid values cannot enter through either the API or database.

It also verifies concurrent mutations, failures, OpenAPI documentation, and the full
repository quality gate. It records what actually shipped without adding frontend or
equivalent calculations.

Suggested commit message:

```text
Commit 5: Complete opportunity-cost API verification
```

Implement:

- Add a complete create/list/update/delete PostgreSQL-backed API flow.
- Prove duplicate labels and stable `created_at, id` ordering across the complete API.
- Prove every read and mutation remains isolated by authenticated user.
- Verify exact text/cents boundaries at both schema and database layers.
- Verify update/delete row locks and deterministic concurrent outcomes.
- Verify transaction rollback after injected repository and persistence failures.
- Verify safe `401`, `403`, `404`, `422`, `500`, and `503` envelopes and request IDs.
- Verify OpenAPI paths, operation IDs, schemas, status codes, and empty `204` response.
- Update tracker statuses, commit hashes, implementation record, and actual test
  results after each gate passes.

Commit gate:

```bash
make check
```

## Out of Scope

- Calculating equivalent units from saved totals; DEV-018 owns it.
- Adding examples to the statistics summary response; DEV-018 owns it.
- Frontend statistics cards, filters, and opportunity-cost messages; DEV-018 owns
  them.
- Frontend example settings, forms, and deletion confirmation; DEV-019 owns them.
- Unique label enforcement; duplicate labels are intentionally allowed in V1.
- Floating-point money, currency conversion, soft deletion, sharing, templates,
  pagination, or reordering controls.
- Final shared hardening and release work owned by DEV-020 through DEV-024.

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

DEV-018 integrates examples into statistics and calculates equivalents. DEV-019 adds
the settings UI. DEV-020 through DEV-024 complete hardening and release work.
