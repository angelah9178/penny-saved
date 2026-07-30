# DEV-010 — Implement Entry CRUD and Dashboard API

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Entry Lifecycle in Plain English](#entry-lifecycle-in-plain-english)
- [Commit 1 — Define Entry Contracts and Lifecycle Mapping](#commit-1--define-entry-contracts-and-lifecycle-mapping)
- [Commit 2 — Add Owned Entry Repository Operations](#commit-2--add-owned-entry-repository-operations)
- [Commit 3 — Implement Entry Creation and Dashboard Listing](#commit-3--implement-entry-creation-and-dashboard-listing)
- [Commit 4 — Add Entry Detail and Waiting-Entry Updates](#commit-4--add-entry-detail-and-waiting-entry-updates)
- [Commit 5 — Add Waiting-Entry Deletion](#commit-5--add-waiting-entry-deletion)
- [Commit 6 — Complete Entry API Security, Documentation, and Verification](#commit-6--complete-entry-api-security-documentation-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are
complete.

|             | Commit                                                                     | Title                                  | Depends on  |
| ----------- | -------------------------------------------------------------------------- | -------------------------------------- | ----------- |
| &#91;x&#93; | [1](#commit-1--define-entry-contracts-and-lifecycle-mapping)               | Define entry contracts and mapping     | —           |
| &#91;x&#93; | [2](#commit-2--add-owned-entry-repository-operations)                      | Add owned repository operations        | Commit 1    |
| &#91;x&#93; | [3](#commit-3--implement-entry-creation-and-dashboard-listing)             | Implement create and dashboard listing | Commit 2    |
| &#91; &#93; | [4](#commit-4--add-entry-detail-and-waiting-entry-updates)                 | Add detail and waiting-entry updates   | Commit 3    |
| &#91; &#93; | [5](#commit-5--add-waiting-entry-deletion)                                 | Add waiting-entry deletion             | Commit 4    |
| &#91; &#93; | [6](#commit-6--complete-entry-api-security-documentation-and-verification) | Complete security and verification     | Commits 1–5 |

## Objective

Implement the authenticated backend API for creating, reading, updating, deleting,
and grouping impulse-purchase entries. DEV-010 turns the entry table introduced by
DEV-005 into the server-owned data boundary used by the dashboard and later check-in
features:

**CRUD** stands for **Create, Read, Update, and Delete**. These are the four basic
operations used to manage stored information:

- **Create:** Add a new impulse-purchase entry.
- **Read:** List the user's entries or retrieve one entry.
- **Update:** Change the item name, price, or reason while the entry is unresolved.
- **Delete:** Remove an unresolved entry.

In DEV-010, “dashboard API” means the read operation also organizes entries into the
four dashboard sections expected by the frontend.

```text
POST   /api/entries            → create a waiting entry
GET    /api/entries            → return all four dashboard buckets
GET    /api/entries/{entry_id} → return one owned entry
PATCH  /api/entries/{entry_id} → edit an entry whose stored status is waiting
DELETE /api/entries/{entry_id} → delete an entry whose stored status is waiting
```

Every operation requires the authenticated-user dependency from DEV-008. Repository
queries must be scoped by that user's ID, services must own transaction and lifecycle
decisions, and routes must only translate between HTTP and the service layer.

The list response always contains these arrays, even when they are empty:

```json
{
  "needs_check_in": [],
  "waiting": [],
  "saved": [],
  "purchased": []
}
```

The backend derives the displayed bucket; the client must not infer or rewrite entry
status. A stored `waiting` entry appears in `needs_check_in` once it reaches 48 hours,
but its stored status remains `waiting` until DEV-013 performs a check-in transition.

Complete and commit each section in order. Every commit must preserve `make check`.
Database integration tests must use only the explicit disposable `TEST_DATABASE_URL`,
and every time-sensitive test must use an injected UTC clock rather than sleeping or
depending on wall-clock time.

## Entry Lifecycle in Plain English

When a user records something they are tempted to buy, the backend creates an entry
with the stored status `waiting`. The user supplies the item name, price in whole
cents, and reason wanted. The backend supplies its identifier and timestamps.

For the first 48 hours, the entry belongs in the dashboard's `waiting` array. At the
exact eligibility time, it moves into the `needs_check_in` array. This is only a
different dashboard view of the same stored `waiting` entry:

```text
created_at + 48 hours > now  → waiting
created_at + 48 hours <= now → needs_check_in
```

Saved and purchased entries use their stored status as their dashboard bucket. All
derived values in one response must use the same request-scoped `now`, preventing an
entry from being classified using one instant and serialized using another.

While the stored status is `waiting`, the owner may edit the item name, price, and
reason, or delete the entry. This remains true after the entry becomes eligible for
check-in because eligibility changes its derived bucket, not its stored status. Once
an entry is saved or purchased, its core details become historical data and attempts
to edit or delete it return `409 Conflict`.

Ownership is enforced on the backend for every operation. If an entry exists but
belongs to another user, the contract requires `403 Forbidden`; if it does not exist,
the API returns `404 Not Found`. The ownership check must reveal no owner identity or
entry contents.

## Commit 1 — Define Entry Contracts and Lifecycle Mapping

**Status:** Complete.

Commit 1 defines the accepted input, public output, normalization rules, and derived
dashboard behavior before database operations or routes depend on them.

In plain language, Commit 1 only establishes the rules and lifecycle of an entry. It
defines what information an entry contains, what input is valid, what the backend may
return, and how the entry's dashboard classification changes as it ages or reaches a
resolved status.

This commit creates the entry rulebook that later CRUD commits follow. It decides
which fields a user may send, how text is cleaned up, how money is represented, and
how a stored entry is assigned to a dashboard section. It does not query the database,
save an entry, or expose an API endpoint yet.

The lifecycle established here is:

```text
new entry
    ↓
stored as waiting and displayed in Waiting
    ↓ after exactly 48 hours
still stored as waiting but displayed in Needs check-in
    ↓ after a later check-in
stored and displayed as Saved or Purchased
```

DEV-010 uses the waiting portion of this lifecycle for CRUD behavior. DEV-013 will
implement the actual transition from `waiting` to `saved` or `purchased`; Commit 1
defines how those statuses are represented so every later endpoint uses the same
rules.

Money must cross every boundary as an integer number of cents. Floating-point values,
numeric strings, booleans, zero, negative values, and values above the database limit
must be rejected. This prevents rounding ambiguity such as whether `19.99` becomes
1,998 or 1,999 cents.

Input behavior:

- `item_name` and `reason_wanted` are required bounded strings.
- Required text is stripped at its outer edges and rejected if empty afterward.
- `price_cents` is a strict positive integer within the database constraint.
- Unknown properties are rejected rather than silently ignored.
- Create and update use deliberate schemas; clients cannot set status, ownership,
  timestamps, comments, or check-in fields.

Every public entry representation includes:

```text
id
item_name
price_cents
reason_wanted
status
dashboard_bucket
comment
created_at
eligible_for_check_in_at
checked_in_at
updated_at
```

`to_entry_response(entry, now)` must be the single mapping function used by create,
list, detail, and update. It computes `eligible_for_check_in_at` from `created_at` and
uses the supplied clock value to derive `dashboard_bucket` consistently.

Suggested commit message:

```text
Commit 1: Define entry contracts and lifecycle mapping
```

Implement:

- Add strict create and core-update request schemas.
- Add entry, wrapped-entry, and four-bucket dashboard response schemas.
- Reuse the database status enum rather than introducing incompatible status values.
- Add the dashboard bucket type with `needs_check_in`, `waiting`, `saved`, and
  `purchased`.
- Centralize required-text normalization without changing meaningful internal spaces.
- Reject non-integer and out-of-range cent values, including booleans.
- Add a pure response mapper using an explicit aware UTC `now`.
- Derive eligibility as exactly `created_at + 48 hours`.
- Add unit tests one microsecond before and exactly at the eligibility boundary.
- Test all status-to-bucket mappings and prove mapping does not mutate the model.
- Test serialization includes `updated_at` and never exposes `user_id`.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-typecheck
make backend-test
```

## Commit 2 — Add Owned Entry Repository Operations

**Status:** Complete.

Commit 2 adds the database access required by the entry services. Every primary read
and mutation accepts `user_id`; there is no unscoped repository helper that returns a
complete entry for an arbitrary ID.

In plain language, this commit builds the storage layer while keeping each user's data
separate. Even if a caller knows another entry's UUID, the normal query includes both
the UUID and current user's ID, so it cannot return or change the other user's entry.

**Users can access and modify only their own entries.** This is the main purpose of
Commit 2. Every entry operation uses the identity from the authenticated session; it
does not trust a user ID supplied by the browser. The repository looks for an entry
using both values:

```text
requested entry ID + authenticated user ID → owned entry or no result
```

### What Is a UUID?

**UUID** stands for **Universally Unique Identifier**. It is a long identifier used to
distinguish one database record from another. An entry UUID looks similar to:

```text
22222222-2222-4222-8222-222222222222
```

The application assigns each entry its own UUID so routes such as
`/api/entries/{entry_id}` can identify the requested entry. UUIDs are designed to be
extremely unlikely to collide and are harder to guess sequentially than IDs such as
`1`, `2`, and `3`.

A UUID identifies an entry, but it does **not** prove that the requesting user owns
that entry. Knowing or guessing another entry's UUID must never grant access. Commit 2
therefore combines the entry UUID with the authenticated user's ID in every primary
read or mutation query.

For example:

```text
User A requests Entry 123 owned by User A → return the entry
User A requests Entry 456 owned by User B → do not return entry data
User A requests an unknown entry UUID      → no entry exists
```

When a scoped lookup finds nothing, a minimal existence query may check only whether
the UUID exists. That is enough for a service to distinguish the required `403` from
`404` response. It must not load or disclose the other user's fields or owner ID.

Dashboard ordering must be deterministic. Entries with equal primary sort values need
a stable ID tie-breaker so repeated requests do not shuffle them unpredictably.

Suggested commit message:

```text
Commit 2: Add owned entry repository operations
```

Implement:

- Add repository operations to create, list, retrieve, lock, update, and delete owned
  entries.
- Require `user_id` for every operation that reads or mutates entry data.
- Add a minimal ID-existence query used only after an owned lookup misses.
- Keep SQLAlchemy queries inside the repository rather than routes or schemas.
- Order waiting and needs-check-in candidates deterministically for dashboard use.
- Order resolved entries deterministically according to the database design.
- Lock mutable rows with `SELECT ... FOR UPDATE` before update or deletion decisions.
- Stage changes without committing; services retain transaction ownership.
- Add PostgreSQL integration tests for ownership scoping and ordering ties.
- Prove the existence check returns no entry fields or owner information.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-typecheck
TEST_DATABASE_URL=postgresql+asyncpg://... make backend-test
```

## Commit 3 — Implement Entry Creation and Dashboard Listing

**Status:** Complete.

Commit 3 introduces the first entry services and routes: authenticated creation and
the dashboard-oriented list response.

Commit 3 implements exactly two **backend actions**:

1. **Create an entry:** `POST /api/entries` accepts the authenticated user's item
   name, integer price in cents, and reason wanted, then stores a new waiting entry.
2. **List entries for the dashboard:** `GET /api/entries` retrieves only the
   authenticated user's entries and returns them in the `needs_check_in`, `waiting`,
   `saved`, and `purchased` arrays.

These are backend API and database actions. Commit 3 does not build or render the
visual dashboard; DEV-011 will use the list response to build the frontend dashboard.

In plain language, creation records a new purchase temptation for the logged-in user.
The backend always starts it in `waiting`; clients cannot pretend it is already saved
or purchased. Listing then retrieves only that user's entries and separates them into
the four arrays the dashboard needs.

The service obtains `now` once per request. Creation uses that same value for
`created_at`, `updated_at`, and response mapping. Listing uses one `now` for every
entry so all eligibility decisions in the response share an exact boundary.

Suggested commit message:

```text
Commit 3: Implement entry creation and dashboard listing
```

Implement:

- Add create and list use cases in the entry service.
- Assign a server-generated UUID and the authenticated user's ID on create.
- Force new entries to `waiting` with null `comment` and `checked_in_at`.
- Use one injected clock reading for create timestamps and derived response fields.
- Commit the create transaction in the service and roll back safely on failure.
- Partition the owned list into all four dashboard arrays.
- Return all arrays even when the user has no entries in a bucket.
- Add authenticated `POST /api/entries` and `GET /api/entries` routes.
- Return `201 Created` with the standard wrapped entry from create.
- Reject missing, invalid, or expired sessions through the DEV-008 dependency.
- Add service and API integration tests for normalization, cent boundaries, ownership,
  empty lists, mixed buckets, exact 48-hour classification, and ordering ties.
- Prove a newly created entry appears in a subsequent list without changing status.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-typecheck
TEST_DATABASE_URL=postgresql+asyncpg://... make backend-test
```

## Commit 4 — Add Entry Detail and Waiting-Entry Updates

**Status:** Planned.

Commit 4 adds retrieval of one owned entry and editing of its core fields while its
stored status remains `waiting`.

In plain language, the detail endpoint supplies the current server representation of
one entry. The update endpoint lets its owner correct the item name, price, or reason
before the entry is resolved. Eligibility alone does not make an entry immutable: an
eligible `needs_check_in` entry is still stored as `waiting` and remains editable.

The update service locks the row before checking status and changing it. This prevents
a later check-in implementation from resolving the entry concurrently while an edit
is based on stale lifecycle state.

Suggested commit message:

```text
Commit 4: Add entry detail and waiting-entry updates
```

Implement:

- Add owned detail and core-update service operations.
- Add authenticated `GET /api/entries/{entry_id}` and
  `PATCH /api/entries/{entry_id}` routes.
- Use the shared mapper so detail and update return the same complete shape.
- Accept only `item_name`, `price_cents`, and `reason_wanted` in the update payload.
- Lock the owned row and permit updates only when stored status is `waiting`.
- Update `updated_at` from the injected clock without changing `created_at`.
- Preserve status, comment, `checked_in_at`, user ownership, and entry identity.
- Return `409 invalid_entry_status` for saved or purchased entries.
- Return the required safe `403` for another user's entry and `404` for an unknown ID.
- Return `422 validation_error` for malformed UUIDs and invalid request fields.
- Add tests for waiting and eligible-waiting updates, immutable fields, ownership,
  normalization, invalid payloads, and lifecycle conflicts.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-typecheck
TEST_DATABASE_URL=postgresql+asyncpg://... make backend-test
```

## Commit 5 — Add Waiting-Entry Deletion

**Status:** Planned.

Commit 5 completes CRUD with deletion of owned entries whose stored status remains
`waiting`.

In plain language, users may remove an unresolved temptation, including one currently
shown in `needs_check_in`. Saved and purchased entries are retained as history because
deleting them would change later statistics and erase the user's decision record.

Deletion locks the owned row, checks its stored status, deletes it inside a
service-owned transaction, and returns no representation. A successful response is
exactly `204 No Content` with an empty body.

Suggested commit message:

```text
Commit 5: Add waiting-entry deletion
```

Implement:

- Add the owned delete use case and authenticated
  `DELETE /api/entries/{entry_id}` route.
- Lock the row before applying the lifecycle rule.
- Permit deletion for both `waiting` and derived `needs_check_in` entries.
- Reject saved or purchased entries with `409 invalid_entry_status`.
- Commit deletion in the service and roll back safely on failure.
- Return `204 No Content` with no JSON and no response body.
- Preserve `403`, `404`, and malformed-ID behavior from the detail/update boundary.
- Add tests for each stored status, the derived eligible bucket, cross-user access,
  unknown IDs, database persistence, and the exact empty response contract.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-typecheck
TEST_DATABASE_URL=postgresql+asyncpg://... make backend-test
```

## Commit 6 — Complete Entry API Security, Documentation, and Verification

**Status:** Planned.

Commit 6 reviews the entire DEV-010 boundary as one feature, fills remaining negative
coverage, and records the verified implementation. It should not become a container
for postponed core behavior from Commits 1–5.

In plain language, the earlier commits build the API one capability at a time. This
commit proves those pieces work safely together: users see only their own data, every
endpoint uses the same response rules, lifecycle conflicts are predictable, and bad
requests receive stable errors without exposing database details.

Suggested commit message:

```text
Commit 6: Complete entry CRUD and dashboard API
```

Implement:

- Mount the entry router exactly once under `/api` if earlier vertical slices did not
  already complete final router registration.
- Confirm all state-changing routes use the existing same-origin protection.
- Confirm every route depends on authenticated session resolution.
- Confirm routes contain no SQL, ownership decisions, or lifecycle calculations.
- Confirm services own commits and rollbacks and repositories never commit.
- Verify `user_id`, ORM internals, and unrelated owners' data never enter responses or
  error details.
- Verify validation, forbidden, missing, lifecycle-conflict, database-unavailable, and
  unexpected failures use the standard safe error envelope.
- Add cross-endpoint contract tests proving entry representations remain identical.
- Add request-clock tests proving one list cannot classify entries with different
  clock reads.
- Add regression coverage for integer-cent bounds, whitespace-only text, unknown
  fields, malformed UUIDs, and deterministic ordering.
- Update API and developer documentation with entry endpoints and response behavior.
- Complete the implementation record below with actual files, behavior, commands, and
  limitations; do not leave planned claims presented as completed facts.
- Run the complete repository quality gate.

Commit gate:

```bash
make check
```

When a disposable PostgreSQL URL is not already configured by the test environment,
run the database-backed suite explicitly with `TEST_DATABASE_URL`. Never infer a test
database from `DATABASE_URL`.

## Out of Scope

- Dashboard pages and client-side entry lists; DEV-011 owns them.
- Frontend create, edit, and delete forms; DEV-012 owns them.
- Saved/purchased transitions and the check-in endpoint; DEV-013 owns them.
- Resolved-entry comment updates; DEV-015 owns them.
- Statistics calculations; DEV-016 owns them.
- Opportunity-cost example operations; DEV-017 owns them.
- Rate limiting and broader abuse protections; DEV-021 owns them.
- Treating a derived dashboard bucket as a fourth stored database status.
- Accepting decimal currency values or performing floating-point money conversion.
- Allowing clients to set ownership, status, comments, or server timestamps through
  create or core-update requests.

## Implementation Record

Complete this section as Commit 6 after the feature has been implemented and verified.

### Overview

DEV-010 is planned to add authenticated entry CRUD and the dashboard list API on top
of the DEV-005 entry model and DEV-008 session boundary.

### What It Achieved

Not implemented yet. Replace this statement with the completed user-visible and
backend outcomes after Commits 1–5 pass their gates.

### API and Lifecycle Behavior

Record the final routes, status codes, normalization behavior, dashboard ordering,
and exact 48-hour boundary behavior demonstrated by the implementation.

### Ownership and Security

Record how authenticated ownership is scoped, how `403` and `404` are distinguished
without data leakage, and which negative tests verify the boundary.

### Verification

Record the exact commands run, PostgreSQL-backed suites completed, and final
`make check` result.

### Limitations and Follow-up

Record any remaining limitations and link them to DEV-011 through DEV-021 as
appropriate.
