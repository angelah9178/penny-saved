# DEV-013 — Entry Check-In

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [APIs Added by DEV-013](#apis-added-by-dev-013)
- [Objective](#objective)
- [Check-In in Plain English](#check-in-in-plain-english)
- [API Contract](#api-contract)
- [Commit 1 — Define the Check-In Contract](#commit-1--define-the-check-in-contract)
- [Commit 2 — Add the Protected Database Update](#commit-2--add-the-protected-database-update)
- [Commit 3 — Enforce the 48-Hour Check-In Rules](#commit-3--enforce-the-48-hour-check-in-rules)
- [Commit 4 — Connect Check-In to the Frontend](#commit-4--connect-check-in-to-the-frontend)
- [Commit 5 — Prove Boundary, Ownership, and Concurrency Safety](#commit-5--prove-boundary-ownership-and-concurrency-safety)
- [Commit 6 — Complete Check-In API Verification and Documentation](#commit-6--complete-check-in-api-verification-and-documentation)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the implementation and commit gate for that row are
complete.

|             | Commit                                                               | Title                                   | Depends on  |
| ----------- | -------------------------------------------------------------------- | --------------------------------------- | ----------- |
| &#91;x&#93; | [1](#commit-1--define-the-check-in-contract)                         | Define the check-in contract            | DEV-010     |
| &#91;x&#93; | [2](#commit-2--add-the-protected-database-update)                    | Add the protected database update       | Commit 1    |
| &#91;x&#93; | [3](#commit-3--enforce-the-48-hour-check-in-rules)                   | Enforce the 48-hour check-in rules      | Commit 2    |
| &#91;x&#93; | [4](#commit-4--connect-check-in-to-the-frontend)                     | Connect check-in to the frontend        | Commit 3    |
| &#91; &#93; | [5](#commit-5--prove-boundary-ownership-and-concurrency-safety)      | Prove boundary and concurrency safety   | Commit 4    |
| &#91; &#93; | [6](#commit-6--complete-check-in-api-verification-and-documentation) | Complete verification and documentation | Commits 1–5 |

## APIs Added by DEV-013

DEV-013 adds one backend API:

| Method | Path                               | Purpose                                               |
| ------ | ---------------------------------- | ----------------------------------------------------- |
| `POST` | `/api/entries/{entry_id}/check-in` | Resolve an eligible waiting entry as saved/purchased. |

This is the backend connection that DEV-014's visible check-in controls will call
when the user selects “I did not buy it” or “I bought it.” DEV-013 does not build the
button or check-in screen; it receives the frontend request, verifies the signed-in
user and trusted browser origin, invokes the Commit 3 service rules, and returns the
updated entry or a safe error response.

## Objective

DEV-013 adds the backend operation that resolves an eligible waiting entry as either
`saved` or `purchased`. The operation is authenticated, owner-scoped, and atomic. It
must remain correct when two requests try to check in the same entry at the same
time.

The backend—not the browser—decides whether 48 hours have passed. Within one database
transaction it locks the entry, rechecks ownership and stored status, checks the exact
eligibility boundary, and records the outcome. A successful check-in changes only:

- `status`, to `saved` or `purchased`.
- `comment`, after trimming outer whitespace and converting blank text to `null`.
- `checked_in_at`, using the service's injected UTC clock.
- `updated_at`, using the same clock value as `checked_in_at`.

The entry's item name, price, reason, owner, and creation time do not change. The
`checked_in_at` timestamp becomes the source date for later statistics work in
DEV-016.

Complete and commit each section in order. Every commit must leave backend formatting,
lint, and focused tests green. Commit 6 runs the full repository quality gate.

## Check-In in Plain English

When a user records an impulse purchase, the app asks them to wait 48 hours. Reaching
48 hours makes the entry eligible, but does not automatically decide what happened.
The user must explicitly say whether they avoided or made the purchase.

```text
Entry created at Monday 10:00 AM
                    ↓ wait 48 hours
Eligible at Wednesday 10:00 AM
                    ↓ user checks in
       ┌────────────┴────────────┐
       ↓                         ↓
Did not buy it               Bought it
status = saved               status = purchased
```

One microsecond before Wednesday at 10:00 AM is too early. Exactly Wednesday at
10:00 AM is allowed. This distinction is checked on the server so changing a device
clock cannot bypass the waiting period.

Atomic means the decision behaves as one indivisible database action. If two browser
tabs submit different answers at nearly the same moment, the first request locks and
resolves the entry. The second request then sees that the entry is no longer waiting
and receives a conflict. There can never be two successful outcomes.

```text
Tab A: saved ───────┐
                    ├─ database row lock → one success
Tab B: purchased ──┘                      → one conflict
```

## API Contract

```text
POST /api/entries/{entry_id}/check-in
```

Request:

```json
{
  "result": "saved",
  "comment": "I waited and realized I did not need it."
}
```

`result` accepts only `saved` or `purchased`. `comment` is optional. Missing, `null`,
empty, or whitespace-only comments are stored as `null`; nonblank comments are
trimmed and must stay within the database's comment length limit. Unknown fields are
rejected.

Success returns `200 OK` with the existing `EntryEnvelope` shape. The response must
show the resolved status and dashboard bucket, the normalized comment, and identical
`checked_in_at` and `updated_at` values.

| Situation                              | Status | Error code             |
| -------------------------------------- | -----: | ---------------------- |
| Missing or expired session             |  `401` | `unauthorized`         |
| Entry belongs to a different user      |  `403` | `forbidden`            |
| Entry does not exist                   |  `404` | `not_found`            |
| Waiting period has not ended           |  `409` | `early_check_in`       |
| Entry is already saved or purchased    |  `409` | `invalid_entry_status` |
| Invalid UUID, result, comment, or body |  `422` | `validation_error`     |

State-changing origin validation from DEV-008 applies to this endpoint. Database
availability and unexpected failures continue to use the established safe error
envelopes and transaction rollback behavior.

## Commit 1 — Define the Check-In Contract

**Status:** Complete.

Commit 1 defines the valid language shared by the API, service, and tests before any
entry can actually change state.

In plain English, this commit writes the rules for the check-in form that a future
frontend will send. It says that the answer must be either “I did not buy it” or “I
bought it,” and that a reflection is optional. It prevents a caller from inventing a
third outcome or changing protected entry fields during check-in.

Commit 1 defines only what a valid check-in request looks like. It does not yet
decide whether a particular stored entry may be checked in. The ownership, stored
`waiting` status, and 48-hour eligibility checks belong to Commit 3, where they can
be enforced together inside the transaction.

```text
Commit 1: Is the submitted answer and optional comment valid?
Commit 3: Is this user allowed to check in this entry right now?
```

Suggested commit message:

```text
Commit 1: Define the entry check-in contract
```

Implement:

- Add a check-in result enum containing only `saved` and `purchased`.
- Add a strict request schema with `result` and optional `comment` fields.
- Forbid unknown fields and reject invalid result values or non-string comments.
- Trim comment whitespace and normalize missing, `null`, empty, and whitespace-only
  comments to `None`.
- Enforce the existing database comment length limit after normalization.
- Reuse `EntryEnvelope` for the successful response.
- Add schema tests for both results, every empty-comment form, trimming, the maximum
  length, oversized comments, unknown fields, and invalid types.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 2 — Add the Protected Database Update

**Status:** Complete.

Commit 2 adds the protected database operation used after the service has locked and
validated an owned entry.

In plain English, this commit prepares the database layer to write the final decision
without touching the original purchase details. The row lock works like a one-person
checkout lane: while one request is deciding the result, another request must wait
and then inspect the newly resolved state.

The owned `SELECT ... FOR UPDATE` query already established by DEV-010 should remain
the single locking path. The new repository mutation stages the four allowed fields;
the service continues to own commit and rollback.

Commit 2 is responsible for safely making the database update:

- Lock the entry while check-in is in progress.
- Change `waiting` to the already-approved `saved` or `purchased` result.
- Store the optional comment.
- Set `checked_in_at` and `updated_at` to the supplied check-in time.
- Leave the item name, price, reason, owner, and creation time unchanged.

It does not decide whether the check-in is allowed. Commit 3 checks the authenticated
owner, current `waiting` status, and 48-hour eligibility before asking this database
helper to apply the result.

```text
Commit 2: Apply this validated result safely and change only allowed fields.
Commit 3: Decide whether this entry is allowed to receive the result.
```

Suggested commit message:

```text
Commit 2: Add the protected check-in database update
```

Implement:

- Reuse the authenticated-user-scoped `get_entry_for_update` repository query.
- Add a repository helper that requires the expected owner before staging a check-in.
- Set only status, comment, `checked_in_at`, and `updated_at`.
- Accept only a resolved `EntryStatus` value after service validation.
- Keep transaction commit, rollback, lifecycle decisions, and clock reads out of the
  repository.
- Add PostgreSQL repository tests proving the row is locked and only the allowed
  columns change.
- Preserve the minimal existence check used to distinguish an unknown entry from an
  entry owned by another user.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 3 — Enforce the 48-Hour Check-In Rules

**Status:** Complete.

Commit 3 implements the service operation and its transaction. This is the commit
that makes a valid check-in change stored data.

In plain English, the service is the decision maker. It gets the current time once,
locks the user's entry, and asks two questions in order: “Is this still waiting?” and
“Have the full 48 hours passed?” Only when both answers are yes does it save the
user's choice.

Commit 3 checks all of the following:

- The entry belongs to the signed-in user. Another user's entry is rejected.
- The entry still has the stored status `waiting`. A saved or purchased entry cannot
  be checked in again.
- The entry has reached `created_at + 48 hours`. One microsecond early is rejected;
  exactly 48 hours is accepted.
- The result from Commit 1 is applied through the protected update from Commit 2.
- One UTC clock reading is used for the eligibility decision, `checked_in_at`,
  `updated_at`, and the response.
- The transaction commits only after the complete update succeeds. Any failure rolls
  back without leaving a partial decision, comment, or timestamp.

```text
Lock owned entry
      ↓
Still waiting? ── no ─→ 409 invalid_entry_status
      ↓ yes
now >= created_at + 48 hours? ── no ─→ 409 early_check_in
      ↓ yes
Write result, comment, and one timestamp → commit → response
```

The same injected clock reading must drive eligibility, both persisted timestamps,
and response mapping. This prevents small timing disagreements inside one request.

Suggested commit message:

```text
Commit 3: Enforce atomic entry check-in rules
```

Implement:

- Add a `check_in_entry` service operation with the authenticated user, entry UUID,
  validated payload, and injected clock.
- Read and normalize the UTC clock exactly once for the transition.
- Lock the owned entry before checking stored status or eligibility.
- Return `invalid_entry_status` when the locked row is already saved or purchased.
- Calculate eligibility as `created_at + ENTRY_WAIT_PERIOD`.
- Return `early_check_in` when `now < eligible_at`; allow `now == eligible_at`.
- Stage the requested status, normalized comment, and identical `checked_in_at` and
  `updated_at` timestamps, then commit once.
- Roll back on domain, database, cancellation, and unexpected failures.
- Return the existing entry response mapped with the same clock value.
- Add focused service tests for saved, purchased, comments, access errors, status
  conflicts, early check-in, exact eligibility, allowed-field preservation, commit,
  and rollback.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 4 — Connect Check-In to the Frontend

**Status:** Complete.

Commit 4 exposes the service through the authenticated entry router.

In plain English, this commit gives the frontend one safe web address for submitting
the user's final choice. The route translates HTTP into the service call; it does not
repeat timing, ownership, locking, or lifecycle logic.

This is what a future visible check-in button uses behind the scenes:

```text
User selects “I did not buy it” or “I bought it” in DEV-014
                              ↓
Frontend calls POST /api/entries/{entry_id}/check-in
                              ↓
Commit 4 authenticates and accepts the web request
                              ↓
Commit 3 checks ownership, status, and 48-hour eligibility
                              ↓
Updated saved/purchased entry or a safe error response
```

Commit 4 does not create the button or page. Its responsibility is to connect that
future frontend interaction to the backend check-in service.

Suggested commit message:

```text
Commit 4: Connect check-in to the frontend
```

Implement:

- Add `POST /api/entries/{entry_id}/check-in` under the existing entries router.
- Require the current user, database session, injected clock, and trusted-origin
  dependency.
- Pass the validated request directly to the service.
- Return `200 OK` with `EntryEnvelope`.
- Document `401`, `403`, `404`, `409`, and `422` responses in OpenAPI.
- Keep the route free of SQL, eligibility calculations, manual commits, and raw error
  construction.
- Add API tests for authentication, exact-origin protection, both outcomes, optional
  comments, malformed UUIDs, invalid bodies, ownership, missing records, early
  requests, and stale-status conflicts.
- Add OpenAPI regression tests for the path, request enum, response envelope, and safe
  error models.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 5 — Prove Boundary, Ownership, and Concurrency Safety

**Status:** Planned.

Commit 5 adds PostgreSQL-backed tests for the risks that ordinary mocked tests cannot
prove: the exact time boundary and two real transactions racing for one row.

In plain English, this commit tries the dangerous cases on purpose. It checks that a
user cannot check in even one microsecond early, cannot check in someone else's item,
and cannot create two answers by clicking twice or using two tabs at once.

Suggested commit message:

```text
Commit 5: Prove atomic check-in boundaries and concurrency
```

Implement:

- Test one microsecond before `created_at + 48 hours`; assert `early_check_in` and no
  database mutation.
- Test exactly at `created_at + 48 hours`; assert a successful transition.
- Test after the boundary for both saved and purchased outcomes.
- Use separate database sessions and concurrent requests against one waiting row.
- Prove the race produces exactly one success and one `invalid_entry_status` conflict.
- Prove the final row contains one complete outcome, never a mixture of both requests.
- Verify failed races and conflicts leave no partial timestamp or comment changes.
- Verify another user's entry is unchanged and no owner or entry data leaks through
  the error response.
- Verify `checked_in_at`, rather than `created_at`, records when the result occurred for
  future statistics queries.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 6 — Complete Check-In API Verification and Documentation

**Status:** Planned.

Commit 6 closes gaps across the completed feature and records the final behavior for
future frontend and statistics work.

In plain English, this commit makes sure all the pieces agree. The documentation,
generated API description, tests, and actual database behavior must tell the same
story: 48 hours means exactly 48 hours, only the owner can decide, and the decision
can happen only once.

Suggested commit message:

```text
Commit 6: Complete the atomic entry check-in API
```

Implement:

- Add cross-endpoint regression tests showing resolved entries appear in the correct
  dashboard bucket and can no longer use waiting-entry edit or delete operations.
- Confirm the public response never exposes `user_id` or persistence internals.
- Confirm all error paths use the standard safe envelope and leave the transaction
  reusable after rollback.
- Update the root README with the check-in endpoint, request example, exact eligibility
  rule, error behavior, and development verification commands.
- Update this document's tracker, statuses, and implementation record with actual
  commit hashes and verification results.
- Run whitespace validation and the full repository quality gate.

Commit gate:

```bash
git diff --check
make check
```

## Out of Scope

- The check-in page, choice controls, confirmation state, navigation, or frontend
  cache invalidation; DEV-014 owns the user experience.
- Editing comments after an entry has been resolved; DEV-015 owns comment-only updates.
- Calculating totals, counts, date-range statistics, or opportunity-cost equivalents;
  DEV-016 through DEV-019 own those features.
- Automatically resolving an entry after 48 hours. Eligibility is derived, but the
  user must explicitly choose saved or purchased.
- Adding a fourth stored `needs_check_in` status. It remains a dashboard bucket derived
  from a waiting entry's creation time.
- Changing item name, price, reason, owner, or creation time during check-in.
- Allowing a resolved decision to be reversed or an entry to be checked in twice.
- Rate limiting or broader abuse protections; DEV-021 owns those controls.

## Implementation Record

Complete this section as the commit series is implemented.

### Commit Results

| Commit | Hash      | Result                                 |
| ------ | --------- | -------------------------------------- |
| 1      | `04dbf61` | Implemented; 312 backend tests passing |
| 2      | `de45c5a` | Implemented; 317 backend tests passing |
| 3      | `3346fdf` | Implemented; 324 backend tests passing |
| 4      | —         | Implemented; 331 backend tests passing |
| 5      | —         | Planned                                |
| 6      | —         | Planned                                |

### Final Verification

Record the date, database used for integration and concurrency tests, focused test
counts, full `make check` result, and any accepted limitations here after Commit 6.
