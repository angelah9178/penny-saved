# DEV-015 — Comment Editing

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Comment Editing in Plain English](#comment-editing-in-plain-english)
- [Route and API Contract](#route-and-api-contract)
- [Commit 1 — Define the Comment Update Contract](#commit-1--define-the-comment-update-contract)
- [Commit 2 — Add the Locked Comment Update](#commit-2--add-the-locked-comment-update)
- [Commit 3 — Expose the Protected Comment API](#commit-3--expose-the-protected-comment-api)
- [Commit 4 — Connect Comment Editing to the Frontend](#commit-4--connect-comment-editing-to-the-frontend)
- [Commit 5 — Build the Resolved Comment Editor](#commit-5--build-the-resolved-comment-editor)
- [Commit 6 — Complete Failure Handling and Verification](#commit-6--complete-failure-handling-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the implementation and commit gate for that row are
complete.

|                  | Commit                                                                  | Title                                    | Depends on  |
| ---------------- | ----------------------------------------------------------------------- | ---------------------------------------- | ----------- |
| &#91;x&#93;      | [1](#commit-1--define-the-comment-update-contract)                      | Define the comment update contract       | DEV-013     |
| &#91;x&#93;      | [2](#commit-2--add-the-locked-comment-update)                           | Add the locked comment update            | Commit 1    |
| &#91;&#160;&#93; | [3](#commit-3--expose-the-protected-comment-api)                        | Expose the protected comment API         | Commit 2    |
| &#91;&#160;&#93; | [4](#commit-4--connect-comment-editing-to-the-frontend)                 | Connect comment editing to the frontend  | Commit 3    |
| &#91;&#160;&#93; | [5](#commit-5--build-the-resolved-comment-editor)                       | Build the resolved comment editor        | Commit 4    |
| &#91;&#160;&#93; | [6](#commit-6--complete-failure-handling-and-verification)              | Complete failures and verification       | Commits 1–5 |

## Objective

DEV-015 lets an authenticated user revise or clear the reflection attached to one of
their saved or purchased entries. It completes the V1 check-in lifecycle without
allowing the user to rewrite the historical purchase decision.

The backend adds one narrow mutation:

```text
PATCH /api/entries/{entry_id}/comment
```

The operation accepts only `comment`. It locks the owned entry, confirms that its
stored status is `saved` or `purchased`, normalizes the text, and changes only
`comment` and `updated_at`. Status, price, item name, reason, creation time, and
check-in time remain unchanged.

The frontend exposes the editor from resolved entry details. A successful save puts
the server response into the detail cache and refreshes dashboard data, so the new
comment appears without a page reload. Statistics are not invalidated because a
reflection does not change whether the item was saved or purchased or how much money
was saved.

Complete and commit each section in order. Backend commits must leave backend format,
lint, typecheck, and focused tests green. Frontend commits must leave the equivalent
frontend checks green. Commit 6 runs the full repository quality gate.

## Comment Editing in Plain English

A check-in records two different kinds of information:

- The result is the historical decision: the user saved the money or made the
  purchase.
- The comment is an optional reflection about that decision.

DEV-015 allows the reflection to change, but it never allows the decision to change.
For example, a user may replace “I decided against it” with “I borrowed one from a
friend,” or erase the reflection entirely. A saved entry remains saved, and a
purchased entry remains purchased.

```text
Saved or purchased entry detail
              ↓ edit only the reflection
"  I borrowed one instead.  "
              ↓ trim outer whitespace
"I borrowed one instead."
              ↓ backend locks and verifies the current row
comment and updated_at change
status, price, checked_in_at, and statistics stay the same
```

Blank text has a deliberate meaning. An empty or whitespace-only value is sent and
stored as `null`, which clears the existing comment. A waiting entry cannot use this
operation—even if it appears in the Needs check-in dashboard bucket—because its final
outcome has not been recorded yet.

The backend, not the visible button, protects these rules. A stale detail page may
show an editor after another request changes the entry, and a caller can construct an
API request without using the page. The server therefore checks ownership and status
again while holding the database row lock.

## Route and API Contract

| Frontend route                  | Purpose                                  | Backend API                                      |
| ------------------------------- | ---------------------------------------- | ------------------------------------------------ |
| `/entries/{entry_id}`           | View an owned entry and edit its comment | `GET`, then `PATCH /api/entries/{entry_id}/comment` |

The request contains exactly one field:

```json
{
  "comment": "I borrowed one instead."
}
```

The field is nullable. After trimming outer whitespace, a blank value becomes
`null`. Nonblank content must contain no more than 4,000 Unicode characters, matching
the established check-in comment contract. Unknown fields are rejected.

Success returns `200 OK` with the existing `EntryEnvelope`. Its `comment` contains
the normalized value, `updated_at` contains the mutation clock, and all lifecycle
fields retain their stored values.

| Situation                              | Status | Error code             |
| -------------------------------------- | -----: | ---------------------- |
| Missing or expired session             |  `401` | `unauthorized`         |
| Entry belongs to a different user      |  `403` | `forbidden`            |
| Entry does not exist                   |  `404` | `not_found`            |
| Entry still has `waiting` status       |  `409` | `invalid_entry_status` |
| Invalid UUID, comment, or request body |  `422` | `validation_error`     |

State-changing origin validation from DEV-008 applies. Database availability and
unexpected failures continue to use the established safe error envelopes and
transaction rollback behavior.

## Commit 1 — Define the Comment Update Contract

**Status:** Complete.

Commit 1 defines the small request shape and the domain language used by the later
repository, service, route, and tests. It does not update a database row yet.

The contract rules are:

- The request must contain exactly one field: `comment`.
- `comment` may be a string or `null`; omitting it is invalid because callers must
  deliberately choose whether to replace or clear the reflection.
- Leading and trailing whitespace is removed before validation and storage.
- Empty or whitespace-only text becomes `null`, which clears the comment.
- A nonblank normalized comment may contain at most 4,000 Unicode characters.
- Values of the wrong type are rejected instead of being converted to text.
- Unknown fields such as `status`, `price_cents`, or `item_name` are rejected.
- A successful operation will reuse the existing `EntryEnvelope` response shape.
- Waiting-entry rejection uses the `invalid_entry_status` lifecycle conflict; the
  database status check itself is implemented in Commit 2.

In plain English, this commit establishes that the caller may submit a reflection and
nothing else. A request cannot quietly include `status: "saved"`, a different price,
or a new check-in date because extra fields are rejected. Blank text means “remove my
comment,” not “store invisible whitespace.”

```text
Accepted: { "comment": "  I borrowed one.  " } → "I borrowed one."
Accepted: { "comment": "   " }                  → null
Rejected: { "comment": "...", "status": "saved" }
Rejected: a normalized comment longer than 4,000 characters
```

Suggested commit message:

```text
Commit 1: Define the resolved comment update contract
```

Implement:

- Add a strict comment-update request schema containing only nullable `comment`.
- Reuse the established optional-comment normalization: trim outer whitespace and
  convert empty or whitespace-only input to `None`.
- Enforce the 4,000-character limit on normalized Unicode text.
- Reuse `EntryEnvelope` for the successful response instead of creating a second
  entry representation.
- Define or reuse the lifecycle conflict for a waiting entry without leaking entry
  data.
- Add focused schema tests for omitted, null, empty, whitespace-only, boundary-length,
  over-limit, wrong-type, and extra-field requests.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 2 — Add the Locked Comment Update

**Status:** Complete.

Commit 2 implements the repository mutation and service transaction. It keeps the
database operation narrow and verifies the lifecycle rule against the current locked
row.

In plain English, this commit is the safety mechanism. Before changing the comment,
the backend reserves the row for the duration of the transaction and looks at its
current status. Only saved and purchased rows pass. This prevents a request from
using stale information while another operation is changing the same entry.

The transaction follows these steps:

1. Find the entry using both the authenticated user ID and entry ID.
2. Lock that row with `SELECT ... FOR UPDATE`.
3. If no owned row is found, return the established safe `403` or `404` error.
4. Check the current stored status while the lock is held.
5. Allow only `saved` or `purchased`; reject `waiting`.
6. Update only `comment` and `updated_at`.
7. Commit the transaction and release the lock.
8. Roll back every staged change if validation or persistence fails.

If two updates arrive together, the lock makes the second request wait. After the
first request commits, the second request acquires the lock and operates on the
latest stored row rather than stale state.

```text
Request A locks the entry
        ↓
Request B waits
        ↓
Request A verifies, updates, and commits
        ↓
Request B locks and reads the latest stored entry
```

The update is deliberately smaller than ordinary entry editing:

| Field             | May change? | Reason                                      |
| ----------------- | ----------- | ------------------------------------------- |
| `comment`         | Yes         | This is the feature the user requested.     |
| `updated_at`      | Yes         | Records when the comment was last changed.  |
| `status`          | No          | The check-in result is final.                |
| Core entry fields | No          | Resolved entries are historical records.    |
| `checked_in_at`   | No          | The original resolution time must remain.   |

Suggested commit message:

```text
Commit 2: Add the locked resolved comment update
```

Implement:

- Add an owned-entry repository read using `SELECT ... FOR UPDATE`.
- Preserve the existing scoped-miss behavior that distinguishes another owner's row
  (`403`) from a missing row (`404`) without revealing owner or entry data.
- Add a repository update that assigns only normalized `comment` and `updated_at`.
- In the service transaction, accept only stored `saved` and `purchased` statuses and
  reject `waiting` with `invalid_entry_status`.
- Read the injected UTC clock once for the update and response mapping.
- Commit only after validation succeeds; roll back on lifecycle and persistence
  failures.
- Return the refreshed entry through the established response mapper.
- Add PostgreSQL service/repository tests proving ownership, both allowed statuses,
  waiting rejection, clearing to `null`, timestamp behavior, row locking, rollback,
  and preservation of every protected field.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 3 — Expose the Protected Comment API

**Status:** Not started.

Commit 3 makes the service available through the authenticated HTTP endpoint. It
wires transport concerns to the transaction from Commit 2 rather than duplicating
ownership or status rules in the route.

In plain English, this commit adds the door the frontend can use. The door checks the
session and browser origin, validates the entry ID and body, calls the protected
service, and translates the result or error into the project's standard JSON shape.

```text
PATCH /api/entries/{entry_id}/comment
        ↓ authentication and exact-origin validation
strict comment request schema
        ↓
locked service transaction from Commit 2
        ↓
200 EntryEnvelope or established safe error envelope
```

Suggested commit message:

```text
Commit 3: Expose the resolved comment update API
```

Implement:

- Add `PATCH /api/entries/{entry_id}/comment` under the authenticated entry router.
- Apply the same exact-origin protection as every other state-changing endpoint.
- Pass the authenticated user ID, parsed entry ID, normalized request, session, and
  injected clock to the service layer.
- Return `200 OK` with the existing entry envelope.
- Map missing, other-owner, waiting-status, validation, database, and unexpected
  failures through the standard safe error handlers.
- Ensure malformed UUIDs and unknown body fields return the established
  `validation_error` response.
- Add API integration tests for saved and purchased updates, comment clearing,
  authentication, origin validation, `403` versus `404`, waiting conflict, invalid
  bodies, rollback, response shape, and protected-field preservation.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
```

## Commit 4 — Connect Comment Editing to the Frontend

**Status:** Not started.

Commit 4 adds the typed API function and TanStack Query mutation that the visible
editor will use. It does not add the editor to the page yet.

In plain English, this commit builds the behind-the-scenes messenger. A component can
say “save this reflection for this entry” without assembling a URL, handling session
credentials, decoding the entry response, or remembering which cached screens are
stale.

```text
comment editor
      ↓ entry ID and normalized comment
comment mutation hook
      ↓ shared credentialed API client
PATCH /api/entries/{entry_id}/comment
      ↓ server-confirmed EntryEnvelope
detail cache updated; dashboard invalidated; statistics unchanged
```

Suggested commit message:

```text
Commit 4: Connect resolved comment editing to the frontend
```

Implement:

- Add the typed nullable comment request and API operation.
- Encode the entry ID in `/api/entries/{entry_id}/comment` and send only `comment`.
- Add a comment-update mutation hook with automatic retries disabled.
- On success, put the returned envelope into
  `queryKeys.entries.detail(entryId)` and invalidate the dashboard query family.
- Do not invalidate statistics because neither the result, price, nor check-in time
  changes.
- Reuse protected-request reporting for `401` and preserve structured backend error
  codes for the visible editor.
- Add focused tests for method, encoded path, nullable body, response typing, retry
  behavior, exact cache effects, and session-expiry reporting.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 5 — Build the Resolved Comment Editor

**Status:** Not started.

Commit 5 adds the visible editor to owned saved and purchased entry details. Waiting
details continue to expose the DEV-012 core-field actions and do not show this
resolved-comment control.

In plain English, this commit gives the user one clearly labelled text box containing
the current reflection and one save action. Saving nonblank text replaces the old
reflection. Saving a blank value clears it. The item and decision remain visible for
context but cannot be changed through this form.

Suggested commit message:

```text
Commit 5: Build the resolved entry comment editor
```

Implement:

- Reuse or complete the protected `/entries/{entry_id}` detail route for waiting,
  saved, and purchased entries.
- Show item name, formatted price, reason, result, original check-in time, and current
  comment as read-only context.
- Render the comment editor only when the server response status is `saved` or
  `purchased`; never infer editability from a dashboard bucket or URL.
- Prepopulate the control from the server comment without converting `null` into the
  visible word “null.”
- Use an explicit label and communicate the 4,000-character limit to assistive
  technology.
- Trim outer whitespace and submit `null` for empty or whitespace-only content.
- Validate the normalized Unicode length while leaving invalid text editable.
- Disable the save action while pending and prevent duplicate click, keyboard, or
  touch submissions.
- After success, display the server-normalized comment, announce an accessible
  confirmation, and keep the user on the detail screen.
- Avoid sending a mutation when the normalized value has not changed.
- Add component/router tests for saved and purchased entries, null and existing
  comments, replacement, clearing, trimming, length boundaries, unchanged values,
  waiting entries, keyboard use, and duplicate activation.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 6 — Complete Failure Handling and Verification

**Status:** Not started.

Commit 6 completes recovery behavior, integration coverage, accessibility, responsive
behavior, and the implementation record. It verifies the whole feature rather than
adding another independent capability.

In plain English, this commit makes the editor trustworthy when reality changes
between loading and saving. If the session expires, the entry disappears, access is
lost, or the server rejects the lifecycle state, the page explains the actual result
and never claims the comment was saved. Retryable failures keep the user's text so it
can be submitted again.

Suggested commit message:

```text
Commit 6: Complete resolved comment editing
```

Implement:

- Preserve the user's edited comment after retryable request failures.
- On `invalid_entry_status`, refresh detail and dashboard data and explain that only
  resolved entries support comment editing.
- Handle `401` through the established session-expiry flow while preserving a safe
  return path.
- Replace the editor with the established inaccessible/not-found state for mutation-
  time `403` and `404` responses; do not reveal whether another user owns the ID.
- Show generic retry guidance for `503`, network, and unexpected failures without
  exposing internal details.
- Move focus to meaningful error or success feedback and announce pending, failure,
  and confirmation states without relying on color.
- Verify responsive layout, long unbroken content, zoom, keyboard-only operation,
  and touch/repeated activation behavior.
- Add an integration test covering dashboard resolved card → detail → edit or clear →
  confirmation → refreshed dashboard comment, with statistics left untouched.
- Update the implementation record below with actual files, behavior, verification,
  and remaining limitations.
- Run the complete local quality gate.

Commit gate:

```bash
make check
```

## Out of Scope

- Changing a resolved entry's saved or purchased result, or allowing a second
  check-in.
- Editing item name, price, reason wanted, creation time, or check-in time after
  resolution.
- Editing comments on waiting or Needs check-in entries. Their optional comment is
  collected when DEV-014 performs the final check-in.
- Deleting saved or purchased entries; V1 retains resolved history.
- Recalculating or invalidating statistics after a comment-only change.
- Comment history, revision comparison, rich text, attachments, mentions, or
  collaborative editing.
- Optimistically displaying an unconfirmed comment before the server responds.
- Changing database schema or adding a separate comment table; the existing nullable
  entry column supports the V1 contract.
- The final cross-feature WCAG 2.2 AA and responsive application audit; DEV-020 owns
  that broader review.
- Rate limiting or broader abuse protections; DEV-021 owns those controls.

## Implementation Record

Complete this section as the commits land. Do not mark the tracker complete from the
plan alone.

### Overview

Commit 1 defines the strict backend request contract for revising or clearing a
resolved entry comment. The database mutation, service lifecycle check, API route,
and frontend editor remain intentionally unimplemented until Commits 2 through 5.

### What Changed

- Added `EntryCommentUpdateRequest` as a required, nullable, comment-only schema.
- Extracted shared optional-comment normalization so check-in and later comment
  updates trim and clear text identically.
- Added focused schema coverage for valid normalization, Unicode length boundaries,
  omitted input, wrong types, over-limit values, and protected extra fields.
- Added an ownership-defensive repository helper that changes only `comment` and
  `updated_at` after the caller has locked and validated the entry.
- Added the locked comment-update service transaction using the existing owned
  `SELECT ... FOR UPDATE` query, safe `403`/`404` distinction, resolved-status check,
  one injected clock reading, commit, and rollback behavior.
- Added repository and PostgreSQL service tests for saved and purchased updates,
  clearing, waiting rejection, ownership, access errors, rollback, timestamps, and
  preservation of protected fields.
- Documented the complete Commit 1 contract rules and corrected backend commit gates
  to use targets that exist in the repository Makefile.

### What It Achieved

Later backend layers now have one validated request type that can express either a
normalized replacement reflection or an explicit `null` clear operation without
accepting lifecycle or core-entry fields.

The backend can now safely perform that update as one transaction. Concurrent entry
mutations serialize through the row lock, and only a currently saved or purchased
owned entry can reach the narrow repository mutation.

### Usage and Safety Notes

The schema validates request shape only. It does not establish ownership, inspect the
stored status, or update a row. Commit 2 now supplies those safety rules in the
service layer. The operation is not externally callable until Commit 3 adds the
authenticated, origin-protected HTTP route.

### Verification

- Focused schema suite: 56 passed.
- Backend Ruff formatting: passed.
- Backend Ruff lint: passed.
- Commit 1 complete backend suite against PostgreSQL: 345 passed.
- Commit 2 focused repository and service suite: 65 passed.
- Commit 2 complete backend suite against PostgreSQL: 354 passed.

### Limitations and Follow-Up

DEV-016 through DEV-019 own statistics and opportunity-cost features. DEV-020 owns
the final shared accessibility and responsive audit, and DEV-021 owns broader
security and abuse protections.
