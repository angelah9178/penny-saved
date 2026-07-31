# DEV-012 — Entry Management

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Entry Management in Plain English](#entry-management-in-plain-english)
- [Frontend Routes and APIs](#frontend-routes-and-apis)
- [Commit 1 — Connect Entry Management to the Backend](#commit-1--connect-entry-management-to-the-backend)
- [Commit 2 — Build the Create and Edit Form](#commit-2--build-the-create-and-edit-form)
- [Commit 3 — Add the New Entry Process](#commit-3--add-the-new-entry-process)
- [Commit 4 — Build Entry Detail and Edit Flows](#commit-4--build-entry-detail-and-edit-flows)
- [Commit 5 — Add Safe Entry Deletion](#commit-5--add-safe-entry-deletion)
- [Commit 6 — Complete Entry Management States and Verification](#commit-6--complete-entry-management-states-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the implementation and commit gate for that row are
complete.

|             | Commit                                                                      | Title                                      | Depends on  |
| ----------- | --------------------------------------------------------------------------- | ------------------------------------------ | ----------- |
| &#91;x&#93; | [1](#commit-1--connect-entry-management-to-the-backend)                     | Connect entry management to the backend    | DEV-010     |
| &#91;x&#93; | [2](#commit-2--build-the-create-and-edit-form)                             | Build the Create and Edit form             | Commit 1    |
| &#91;x&#93; | [3](#commit-3--add-the-new-entry-process)                                 | Add the new entry process                  | Commit 2    |
| &#91; &#93; | [4](#commit-4--build-entry-detail-and-edit-flows)                           | Build detail and edit flows                | Commit 3    |
| &#91; &#93; | [5](#commit-5--add-safe-entry-deletion)                                     | Add safe entry deletion                    | Commit 4    |
| &#91; &#93; | [6](#commit-6--complete-entry-management-states-and-verification)           | Complete states and verification           | Commits 1–5 |

## Objective

DEV-012 turns the read-only dashboard from DEV-011 into an entry-management
experience. A signed-in user can record a possible impulse purchase, open an entry,
edit it while it is still waiting, and delete it after confirming the choice.

This work uses the authenticated backend APIs completed in DEV-010:

```text
POST   /api/entries            → create a waiting entry
GET    /api/entries/{entry_id} → load one owned entry
PATCH  /api/entries/{entry_id} → edit an owned waiting entry
DELETE /api/entries/{entry_id} → delete an owned waiting entry
```

The forms accept a human-readable dollar amount, but the API continues to receive an
integer number of cents. After a successful create, edit, or delete, TanStack Query
refreshes the relevant cached data so the dashboard changes without a full-page
reload.

The backend remains the authority for ownership, status, and validation. Hiding an
Edit or Delete button is helpful user experience, but it is not a security boundary.
A stale page may still submit after an entry stops being editable, so the frontend
must handle the backend's `409 Conflict` response honestly.

Complete and commit each section in order. Every commit must leave frontend format,
lint, typecheck, and focused tests green. Commit 6 runs the full repository quality
gate.

## Entry Management in Plain English

When a user considers buying something, they enter its name, its dollar price, and
why they want it. The frontend checks for obvious mistakes, converts the price to
whole cents, and sends the entry to the backend. The backend creates it with the
status `waiting`.

```text
User enters: Coffee grinder, $89.99, "Better coffee at home"
                         ↓
Frontend sends: 8999 cents
                         ↓
Backend creates a waiting entry
                         ↓
Dashboard refreshes and shows the new entry
```

While the stored status is still `waiting`, the user may change the item name, price,
or reason. An entry shown in Needs check-in is still stored as `waiting`, so it also
remains editable and deletable until a later check-in changes its stored status.

Saved and purchased entries are historical records. Their core fields cannot be
edited or deleted. The detail screen therefore does not offer those actions, and the
backend rejects any stale or manually constructed request with `409 Conflict`.

Deleting is permanent. The user must first see a confirmation that names the entry
and then choose the explicit destructive action. Cancelling the confirmation changes
nothing.

## Frontend Routes and APIs

| Route                        | Purpose                              | Backend API                     |
| ---------------------------- | ------------------------------------ | ------------------------------- |
| `/entries/new`               | Create a waiting entry               | `POST /api/entries`             |
| `/entries/{entry_id}`        | View an owned entry                  | `GET /api/entries/{entry_id}`   |
| `/entries/{entry_id}/edit`   | Edit an owned waiting entry          | `PATCH /api/entries/{entry_id}` |
| Detail-page delete action    | Delete an owned waiting entry        | `DELETE /api/entries/{entry_id}`|

All routes are protected by the existing authentication guard. Requests use the
shared credentialed `apiFetch` client and the established query keys:

```ts
queryKeys.entries.dashboard();
queryKeys.entries.detail(entryId);
```

Create invalidates the dashboard query. Edit stores the returned entry in the detail
cache and invalidates both detail and dashboard data. Delete removes the detail cache
and invalidates the dashboard. Mutations are not retried automatically because
repeating a write may produce an unintended second action.

## Commit 1 — Connect Entry Management to the Backend

**Status:** Complete.

Commit 1 builds the internal frontend connection to the four DEV-010 APIs used by
this task. It adds typed request functions and TanStack Query hooks, but it does not
build the visible forms yet.

In plain language, this commit prepares the behind-the-scenes frontend code that later
screens use to create, view, edit, and delete entries. It does not build the visible
forms yet.

This is partly what lets the user edit entries, but it supports all entry-management
actions:

- Create an entry.
- Load one entry for the detail and edit pages.
- Edit an entry.
- Delete an entry.
- Refresh the dashboard and entry details after a change so the user immediately sees
  current information.

A page component should say “create this entry” or “load this entry”; it should not
assemble URLs, call `fetch`, interpret a `204` body, or remember which cached lists
need refreshing.

```text
Visible entry screen
       ↓ uses
entry query or mutation hook
       ↓ uses
shared credentialed API client
       ↓ calls
DEV-010 entry API
```

Suggested commit message:

```text
Commit 1: Connect entry management to the backend
```

Implement:

- Add typed functions for single-entry `GET`, `POST`, `PATCH`, and `DELETE`.
- Send only `item_name`, `price_cents`, and `reason_wanted` for create and edit.
- Forward an `AbortSignal` when loading entry detail.
- Correctly accept the delete API's `204 No Content` response.
- Add detail-query and create, edit, and delete mutation hooks.
- Use the existing protected-request handling for an expired session.
- Do not automatically retry mutations.
- Define cache behavior for every successful mutation.
- Add focused tests for methods, paths, JSON bodies, response handling, query keys,
  cancellation, and `401` reporting.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 2 — Build the Create and Edit Form

**Status:** Complete.

Commit 2 creates the reusable form foundation used by both Create and Edit. It also
defines exactly how a dollar amount typed by a person becomes cents for the API.

In simple terms, Commit 2 has two related responsibilities:

- Convert money between user-friendly dollars and API cents. For example, the user
  types `89.99`, the frontend sends `8999`, and an existing `8999` cents becomes
  `89.99` when placed in the Edit form.
- Build the shared Item name, Price, and Reason wanted fields used by both Create and
  Edit, including validation messages and accessible labels.

The dashboard's `$89.99` display formatting already exists from DEV-011. Commit 2
specifically handles money entered into forms and provides the common form structure;
Commits 3 and 4 place that form on the Create and Edit pages.

In plain language, JavaScript decimal arithmetic can introduce rounding surprises.
This commit avoids that problem by reading the price as text and separating the
dollars and cents. It never calculates API money by multiplying a floating-point
number by 100.

```text
"89.99" → dollars "89" + cents "99" → 8999
"12"    → dollars "12" + cents "00" → 1200
"0.5"   → dollars "0"  + cents "50" → 50
```

Values such as `1e3`, `1,000`, `-2.00`, `$5.00`, more than two decimal places, and
amounts outside the backend range are rejected. Formatting cents for an edit form is
the reverse operation: `8999` becomes `89.99` without losing a cent.

The shared form has visible labels and errors connected to their fields. Client-side
validation provides quick feedback, while backend field errors remain authoritative
and must also be shown.

Suggested commit message:

```text
Commit 2: Build the create and edit form
```

Implement:

- Add string-based helpers that parse dollar text into integer cents and format cents
  as a two-decimal edit value.
- Require a price from `$0.01` through `$9,999,999,999.99` with no more than two
  decimal places.
- Build shared controls for item name, price, and reason wanted.
- Trim item name and reason before submission.
- Enforce the frontend mirrors of the backend's 200-character item-name limit and
  2,000-character reason limit.
- Reject empty trimmed text and malformed price input with field-specific messages.
- Preserve the user's input after validation or server failure.
- Connect error text with `aria-describedby` and mark invalid fields with
  `aria-invalid`.
- Add unit and component tests for valid prices, boundary values, malformed values,
  trimming, length limits, and accessible errors.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 3 — Add the New Entry Process

**Status:** Complete.

Commit 3 makes the existing “Add new impulse purchase” dashboard link useful by
building the protected `/entries/new` page.

In plain language, this is the first commit in DEV-012 that lets the user change
stored data. The user fills in the shared form, submits it once, and returns to a
dashboard that includes the new waiting entry.

Put simply, Commit 3 builds the complete process for creating a new entry:

```text
Dashboard “Add new impulse purchase” link
→ Create Entry page
→ Form from Commit 2
→ Send the entry to the backend
→ Return to the dashboard
→ Show the new entry in Waiting
```

It also prevents duplicate submissions, preserves the form when a request fails,
returns an expired session to login, warns before discarding unsaved changes, and
refreshes the dashboard after successful creation.

```text
Dashboard Add link → Create form → POST /api/entries
                                      ↓ success
                           refresh dashboard cache
                                      ↓
                             return to dashboard
```

While submission is pending, the submit action is disabled to prevent accidental
duplicates. A validation error keeps the user on the form next to the field that
needs attention. A temporary server failure keeps their entered values and offers a
clear retry path rather than silently losing their work.

Suggested commit message:

```text
Commit 3: Add the new entry process
```

Implement:

- Register the protected `/entries/new` route.
- Render the shared form with empty initial values and create-specific headings.
- Convert valid price text to cents only at the submission boundary.
- Disable duplicate submission while the mutation is pending.
- Map backend field errors to the appropriate form controls.
- Show a useful form-level message for network and server failures.
- On success, invalidate the dashboard query, announce confirmation, and navigate to
  `/dashboard`.
- Warn before leaving when the user has unsaved changed values.
- Add MSW-backed tests for success, invalid input, backend validation, server failure,
  duplicate-submit prevention, cache refresh, and session expiry.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 4 — Build Entry Detail and Edit Flows

**Status:** Not started.

Commit 4 adds the single-entry detail page, dashboard navigation to that page, and the
edit screen for entries whose stored status is `waiting`.

In plain language, the detail page is the user's stable place to inspect one entry.
It loads the server's current version rather than trusting an old dashboard card. If
the entry is editable, the user can open a form already filled with its core fields.
Saving sends only those allowed fields and refreshes both the detail and dashboard.

```text
Dashboard card → Entry detail → Edit form → PATCH /api/entries/{id}
                                                    ↓ success
                                         refresh detail + dashboard
```

The interface only shows Edit when the returned stored status is `waiting`. This is
convenience, not enforcement. If the entry changes status after the page loads, the
backend returns `409 Conflict`; the frontend refreshes server data and explains that
the entry is no longer editable.

Suggested commit message:

```text
Commit 4: Add entry detail and editing
```

Implement:

- Register protected detail and edit routes.
- Add useful detail navigation to waiting and Needs check-in dashboard cards.
- Load detail through the established detail query key.
- Show loading, not-found, forbidden, retryable-error, and expired-session states.
- Pre-fill the shared form from the server response, including exact cents-to-dollar
  conversion.
- Show Edit only when the stored status is `waiting`.
- Submit only the three editable core fields.
- Put a successful edit response into the detail cache and invalidate detail and
  dashboard queries.
- Handle `409 Conflict` by refreshing server truth and explaining the lifecycle
  change.
- Warn before leaving an edit form with unsaved changes.
- Add MSW-backed tests for detail, successful edit, hidden illegal actions, field
  errors, conflicts, failures, cache refresh, and cancellation.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 5 — Add Safe Entry Deletion

**Status:** Not started.

Commit 5 adds deletion to the detail page with an explicit accessible confirmation.

In plain language, selecting Delete must not immediately erase an entry. The app
opens a confirmation that names the item, gives the user a safe Cancel choice, and
requires a second clear action before calling the backend.

```text
Delete button → Confirmation opens
                    ├─ Cancel → nothing changes
                    └─ Delete entry → DELETE /api/entries/{id}
                                             ↓ 204
                                  clear detail + refresh dashboard
                                             ↓
                                      return to dashboard
```

Only a server-confirmed `204 No Content` counts as deletion. If the request fails,
the confirmation stays useful and the user receives an explanation. If the server
reports that the entry is no longer waiting, the frontend refreshes the entry rather
than pretending it was deleted.

Suggested commit message:

```text
Commit 5: Add waiting entry deletion
```

Implement:

- Show Delete only for entries whose stored status is `waiting`.
- Open a confirmation dialog that names the entry and describes permanence.
- Provide separate Cancel and destructive Delete actions.
- Move focus into the dialog, keep keyboard focus within it, close on Escape when
  safe, and restore focus to the trigger after cancellation.
- Disable repeated destructive submission while deletion is pending.
- On `204`, remove the detail query, invalidate the dashboard, announce success, and
  navigate to `/dashboard`.
- On `409`, close or update the confirmation, refresh detail and dashboard data, and
  explain that the entry can no longer be deleted.
- Preserve the entry and show retryable feedback on network or server failure.
- Add MSW-backed tests for confirm, cancel, keyboard behavior, successful `204`,
  conflict, failure, duplicate clicks, navigation, and cache cleanup.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 6 — Complete Entry Management States and Verification

**Status:** Not started.

Commit 6 reviews the create, detail, edit, and delete experience as one complete
feature and closes gaps that focused implementation tests may miss.

In plain language, the earlier commits make each operation work. This commit proves
that they work together for keyboard users, narrow screens, slow requests, stale
pages, long content, expired sessions, and backend failures. It also records what was
actually implemented and verified.

Suggested commit message:

```text
Commit 6: Complete entry management flows
```

Implement:

- Verify every new route is protected and uses a safe sign-in return path.
- Verify focus placement, visible focus, labels, error announcements, dialog behavior,
  and pending-state announcements.
- Confirm forms and detail content work at narrow and wide viewport sizes.
- Confirm long item names, reasons, server messages, and prices do not break layouts.
- Test cancellation and component unmounting without false error messages.
- Test a complete create, detail, edit, and delete journey with MSW.
- Prove successful mutations refresh the dashboard without a browser reload.
- Prove request payloads always contain integer cents, never decimal dollars.
- Update this document's tracker, statuses, implementation record, verification
  totals, and any discovered limitations.
- Run the full repository quality gate.

Commit gate:

```bash
make check
```

## Out of Scope

DEV-012 does not include:

- Performing the saved-or-purchased check-in transition; DEV-013 and DEV-014 own the
  backend and frontend check-in flows.
- Editing comments on saved or purchased entries; DEV-015 owns comment editing.
- Dashboard statistics or opportunity-cost equivalents; DEV-016 through DEV-019 own
  those features.
- Reimplementing ownership or lifecycle security in the browser. DEV-010's backend
  remains authoritative.
- Optimistic lifecycle changes. Mutation results must reflect confirmed server data.
- Changing the backend API contracts or database schema unless a separately reviewed
  defect requires it.

## Implementation Record

DEV-012 is in progress. Commit 1 added the typed frontend operations and TanStack
Query integration for entry detail, creation, editing, and deletion. Successful
mutations now invalidate the dashboard; edits also update and invalidate entry detail,
while deletion removes the deleted detail from the cache. Protected requests report
session expiry with the route the user was using, detail requests support
cancellation, and mutations explicitly do not retry.

Commit 2 added one shared Create/Edit form with accessible labels and field errors,
trimmed text validation, backend-aligned length limits, exact string-based dollar
parsing, and exact cents-to-edit-value formatting. The form preserves user input after
failures, maps backend `price_cents` errors to the visible Price field, and prevents
duplicate submission while a save is pending.

Commit 3 added the protected `/entries/new` page and connected the shared form to the
create mutation. Successful creation returns to the dashboard with a status
announcement and refreshed Waiting data. Failed requests preserve input, pending
requests cannot be submitted twice, guests and expired sessions return safely to
login, and changed forms warn before in-app navigation or browser unload discards
their contents.

Commits 4–6 are not started. Continue filling in this section as they are completed
rather than recording planned work as implemented work.

The final record should include:

- The commit hash and final title for each completed section.
- Any deliberate differences from this plan.
- The final `make check` date and test totals.
- Known limitations and the DEV task responsible for each follow-up.
