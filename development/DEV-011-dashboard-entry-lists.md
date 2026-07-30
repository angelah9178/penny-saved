# DEV-011 — Build Dashboard Entry Lists

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [What the Dashboard Must Show](#what-the-dashboard-must-show)
- [Frontend Data Rules](#frontend-data-rules)
- [Commit 1 — Connect the Frontend to the Dashboard API](#commit-1--connect-the-frontend-to-the-dashboard-api)
- [Commit 2 — Add Safe Display Formatting](#commit-2--add-safe-display-formatting)
- [Commit 3 — Build Reusable Entry Cards and Sections](#commit-3--build-reusable-entry-cards-and-sections)
- [Commit 4 — Compose the Complete Dashboard](#commit-4--compose-the-complete-dashboard)
- [Commit 5 — Handle Dashboard Loading, Errors, and Session Expiry](#commit-5--handle-dashboard-loading-errors-and-session-expiry)
- [Commit 6 — Complete Accessibility, Responsive Styling, and Verification](#commit-6--complete-accessibility-responsive-styling-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the implementation and commit gate for that row are
complete.

|             | Commit                                                                     | Title                                       | Depends on  |
| ----------- | -------------------------------------------------------------------------- | ------------------------------------------- | ----------- |
| &#91;x&#93; | [1](#commit-1--connect-the-frontend-to-the-dashboard-api)                  | Connect frontend to the dashboard API       | DEV-010     |
| &#91;x&#93; | [2](#commit-2--add-safe-display-formatting)                                | Add safe display formatting                 | Commit 1    |
| &#91;x&#93; | [3](#commit-3--build-reusable-entry-cards-and-sections)                    | Build reusable entry cards and sections     | Commit 2    |
| &#91;x&#93; | [4](#commit-4--compose-the-complete-dashboard)                             | Compose the complete dashboard              | Commit 3    |
| &#91;x&#93; | [5](#commit-5--handle-dashboard-loading-errors-and-session-expiry)         | Handle dashboard request states             | Commit 4    |
| &#91; &#93; | [6](#commit-6--complete-accessibility-responsive-styling-and-verification) | Complete dashboard quality and verification | Commits 1–5 |

## Objective

DEV-011 creates the read-only frontend dashboard that lets the user see the entry data
provided by the backend APIs built in DEV-010. It connects the dashboard to
`GET /api/entries` and displays the four backend-provided groups: Needs check-in,
Waiting, Saved, and Purchased.

DEV-011 does not create the complete frontend for every DEV-010 API. DEV-012 adds the
interactive create, detail, edit, and delete screens that use `POST`, single-entry
`GET`, `PATCH`, and `DELETE`. In short, DEV-011 displays the entry lists, and DEV-012
adds the entry-management actions.

Replace the temporary signed-in page with the first useful Penny Saved dashboard.
The page reads the authenticated user's entries from the DEV-010 API and shows the
four lists returned by the backend:

```text
Needs check-in
Waiting
Saved
Purchased
```

This task is about reading and presenting entries. It does not create, edit, delete,
or check in an entry. Those actions belong to later DEV tasks.

The backend already decides which list contains each entry. The browser must keep the
same list membership and item order. It may format cents as US dollars and timestamps
as readable text, but it must not reproduce the 48-hour rule or move an item when a
client-side timer reaches zero.

Complete and commit each section in order. Every commit must leave the frontend
format, lint, typecheck, and focused tests green. Commit 6 runs the full repository
quality gate.

## What the Dashboard Must Show

The dashboard loads this authenticated API:

```http
GET /api/entries
```

The successful response always has all four arrays:

```json
{
  "needs_check_in": [],
  "waiting": [],
  "saved": [],
  "purchased": []
}
```

Each entry card shows information already supplied by the API:

- Item name.
- Price formatted as US dollars.
- Reason wanted.
- A timing or status message appropriate to its returned list.
- A saved or purchased comment when one exists.
- Only the navigation that is useful and legal for its current state.

The four sections behave as follows:

| Section        | Main message                          | Action in DEV-011                 |
| -------------- | ------------------------------------- | --------------------------------- |
| Needs check-in | The waiting period is complete.       | Link to `/entries/{id}/check-in`. |
| Waiting        | Show when check-in becomes available. | No check-in action yet.           |
| Saved          | The user decided not to buy the item. | No mutation action in DEV-011.    |
| Purchased      | The user decided to buy the item.     | No mutation action in DEV-011.    |

The check-in route is implemented in DEV-014. DEV-011 may render the correct link even
though the destination is not complete yet. Waiting entries must not receive that
link. Edit and delete controls belong to DEV-012 and must not be added early.

Purchased entries sit inside a native `<details>` element that is closed when the
dashboard first renders. Opening or closing it is local display state only. It does
not change query data or persist across a page reload.

Every section needs its own useful empty message. An empty list is not an error. For
example, an empty Needs check-in section can explain that there is nothing to review,
while an empty Waiting section can explain that there are no purchases currently in
the waiting period.

## Frontend Data Rules

### The server owns list membership

Render each response array directly. Do not combine the arrays, sort them again, or
derive a dashboard bucket from `status`, `created_at`, or
`eligible_for_check_in_at`.

The API's order is intentional. Keeping it unchanged means the frontend automatically
follows the backend's stable ordering rules.

### The browser owns display formatting

`price_cents` stays an integer at the API boundary. Use `Intl.NumberFormat` with the
`en-US` locale and `USD` currency to turn it into display text. Do not divide money
and feed the result back into application state or an API request.

API timestamps are UTC RFC 3339 strings. Formatting code must handle invalid input
without crashing the page. A `<time>` element should keep the original machine-readable
timestamp in `dateTime` and show a readable value to the user.

For a waiting entry, the browser may say when check-in becomes available or show a
display-only countdown. That countdown must never move the entry to Needs check-in.
Only a later server response may change its list.

### TanStack Query owns remote state

Use the existing query key:

```ts
queryKeys.entries.dashboard(); // ['entries', 'dashboard']
```

The query calls `GET /api/entries` through the shared credentialed `apiFetch` client,
passes TanStack Query's `AbortSignal`, and uses the existing retry rules. Keep the data
in the query cache instead of copying it into component state.

Protected requests must use the existing session-expiry path so a `401` clears stale
authenticated state and returns the user to login with a safe dashboard return path.

## Commit 1 — Connect the Frontend to the Dashboard API

**Status:** Complete.

Commit 1 establishes the connection between the frontend dashboard and the DEV-010
backend. Specifically, it connects the frontend to the `GET /api/entries` API. It adds
the small frontend data layer that requests that API without rendering the full
dashboard yet.

In plain language, this commit gives the page one trusted way to ask for dashboard
entries. It is not a button that the user clicks, and it does not show entry cards on
the screen yet. It creates the internal API function and TanStack Query hook that the
visible dashboard components use in later commits. Components should not build URLs
or call `fetch` themselves.

```text
Dashboard page
    ↓ uses
useDashboardEntries()
    ↓ requests
GET /api/entries
    ↓ returns
Needs check-in, Waiting, Saved, and Purchased
```

Suggested commit message:

```text
Commit 1: Connect the frontend to the dashboard API
```

Implement:

- Add an entries API module under `frontend/src/features/entries`.
- Add a typed function that calls `GET /api/entries` with `apiFetch`.
- Accept and forward an `AbortSignal` so abandoned requests can be cancelled.
- Add a `useDashboardEntries` query hook using
  `queryKeys.entries.dashboard()`.
- Run the request through the existing protected-request/session-expiry helper with
  `/dashboard` as the safe return location.
- Use a short stale time of about 30 seconds while keeping the shared retry policy.
- Keep snake_case response fields and integer cents unchanged.
- Add tests for the request method, path, credentials inherited from `apiFetch`, query
  key, successful response, cancellation, and `401` session-expiry reporting.
- Do not add a second API client or a second dashboard query key.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 2 — Add Safe Display Formatting

**Status:** Complete.

Commit 2 adds small formatting helpers for values that people should not have to read
in raw API form.

In plain language, the API says `1299`; the dashboard says `$12.99`. The API gives a
UTC timestamp; the dashboard gives a readable date and time while preserving the
original timestamp for browsers and assistive technology.

Examples covered by this commit:

```text
1299 cents                     → $12.99
2026-07-30T14:30:00Z           → Jul 30, 2026, 10:30 AM
eligible_for_check_in_at time  → Check-in available Jul 30, 2026, 10:30 AM
```

This formatting is display-only. It does not change the API response, convert stored
integer cents into application data, send formatted values back to the backend, or
decide which dashboard list contains an entry. Commit 3 uses these helpers when it
builds the visible entry cards.

Suggested commit message:

```text
Commit 2: Format money and dates for display
```

Implement:

- Add a USD display helper based on `Intl.NumberFormat("en-US", ...)`.
- Format zero, cents, whole dollars, and large supported values correctly.
- Keep the helper display-only; it must not parse user input or prepare API payloads.
- Add a date/time display helper for valid UTC strings.
- Define a safe fallback for invalid timestamps rather than throwing during render.
- Add a small component or shared pattern that renders semantic `<time>` markup.
- Add a waiting-message helper or component that describes
  `eligible_for_check_in_at` without deciding bucket membership.
- Avoid tests that depend on the machine's local timezone. Fix the test timezone or
  assert stable semantic output.
- Add focused unit tests for money and timestamp edge cases.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 3 — Build Reusable Entry Cards and Sections

**Status:** Complete.

Commit 3 builds the reusable presentation pieces used by all four lists.

In plain language, one card explains one temptation and one section explains one part
of the lifecycle. The components receive data and render it; they do not know how to
load the dashboard.

This is the first commit that builds the frontend pieces the user will actually see.
It turns entry data into visible cards showing the item name, price, reason, timing or
status, comments when relevant, and the legal action for that section. It also builds
the section layout and the message shown when a section has no entries.

For example, a Needs check-in card can look like this:

```text
Needs check-in

Wireless headphones
$89.99
Reason: Useful while commuting
The waiting period is complete.
[Check in]
```

The first three commits build on each other:

```text
Commit 1: Get entries from GET /api/entries.
Commit 2: Make prices and dates readable.
Commit 3: Display that information as visible cards and sections.
```

Commit 3 does not assemble the complete live Dashboard page. Commit 4 connects these
components to the query result and places all four sections on `DashboardPage`.

Suggested commit message:

```text
Commit 3: Build dashboard entry cards and sections
```

Implement:

- Add an `EntryCard` component with typed, narrow props.
- Show item name, formatted price, reason wanted, and list-appropriate timing/status.
- Render comments for saved and purchased entries only when the API supplies a
  non-empty comment.
- Render user text through normal React text nodes; do not inject HTML.
- Add an `EntrySection` component with a heading, entry count, list, and section-level
  empty message.
- Use each entry UUID as the React list key.
- Let the caller provide the section meaning instead of recalculating it from entry
  fields.
- Add the check-in link only for entries passed through the Needs check-in section.
- Ensure a waiting entry has no check-in link, including when its eligibility
  timestamp is in the past according to the browser clock.
- Do not add edit, delete, comment-edit, or check-in submission logic.
- Add component tests for all four presentations, optional comments, empty sections,
  long text, semantic headings/lists, exact dollar output, and action visibility.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 4 — Compose the Complete Dashboard

**Status:** Complete.

Commit 4 replaces the DEV-009 placeholder with the complete list layout.

In plain language, this commit connects the query to the page and places every entry
in exactly the section chosen by the backend.

This is the commit that creates the complete frontend for listing all entries on the
actual dashboard. When the user visits `/dashboard`, the page loads entries with
`useDashboardEntries()`, shows Needs check-in, Waiting, and Saved, and places Purchased
inside a collapsed section. It preserves the backend's list order and gives each empty
section its own explanation.

The first four commits work together like this:

```text
Commit 1: Retrieve entries from GET /api/entries.
Commit 2: Format prices and dates for people to read.
Commit 3: Build visible entry cards and reusable sections.
Commit 4: Connect everything on the real Dashboard page.
```

Commit 4 provides the complete successful-response and empty-response layout. Commit
5 completes the more detailed loading, failure, retry, background-refresh, and expired
session behavior.

Suggested commit message:

```text
Commit 4: Compose the dashboard entry lists
```

Implement:

- Replace the temporary text in `DashboardPage` with the real dashboard composition.
- Add a clear page heading and short introductory text.
- Add a prominent link to `/entries/new` labelled “Add new impulse purchase”; DEV-012
  owns the destination form.
- Render sections in this order: Needs check-in, Waiting, Saved, Purchased.
- Pass each backend array straight to its section without filtering or sorting.
- Give every section an understandable independent empty message.
- Put Purchased in a semantic `<details>` disclosure that starts closed.
- Keep the disclosure's open state only for the current mounted page.
- Do not hide the other three sections when they are empty.
- Add MSW-backed page tests for a response containing every bucket and a response
  containing four empty arrays.
- Prove in a test that backend order is preserved.
- Update the existing router test that currently expects the DEV-011 placeholder.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 5 — Handle Dashboard Loading, Errors, and Session Expiry

**Status:** Complete.

Commit 5 makes the page honest about request state. A failed request must never look
like an empty dashboard.

In plain language, the user should always know whether the app is still loading,
there are genuinely no entries, the server could not respond, or their sign-in has
expired.

Commit 5 handles all states of the dashboard request, not only errors:

```text
Initial loading       → Show “Loading your entries…”
Successful response   → Show the dashboard entry lists
Successful empty data → Show four honest empty messages
Background refresh    → Keep the lists visible and show “Updating dashboard…”
Network or 5xx failure → Retry temporary failures, then show an error
Manual retry          → Let the user choose “Try again”
Expired session (401) → Return to login and preserve /dashboard
Cancelled request     → Do not show a false failure message
```

Commit 4 built the dashboard's successful listing view. Commit 5 makes that dashboard
behave correctly while its data is loading, refreshing, failing, retrying, or losing
authentication.

Suggested commit message:

```text
Commit 5: Handle dashboard loading, errors, and session expiry
```

Implement:

- Show the existing accessible loading treatment during the first dashboard request.
- Keep successful content visible during a background refresh and add a quiet updating
  message rather than replacing the whole page.
- Show the standard recoverable error alert after retryable failures are exhausted.
- Add a retry button that asks TanStack Query to refetch the same query.
- Keep the four empty messages exclusive to successful empty arrays.
- Route `401` responses through the existing global session-expiry coordinator.
- Preserve `/dashboard` as the safe return destination after the user signs in again.
- Ensure query cancellation does not show an error to the user.
- Add MSW-backed tests for initial loading, background refresh, network failure, `5xx`,
  manual retry success, `401`, and zero-data success.
- Use fake timers only where retry timing requires them; do not add arbitrary sleeps.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 6 — Complete Accessibility, Responsive Styling, and Verification

**Status:** Planned.

Commit 6 reviews the dashboard as one feature, fixes remaining presentation and test
gaps, and records what was actually delivered. It is not a place to postpone core
behavior from Commits 1–5.

In plain language, the dashboard must remain understandable with a keyboard, screen
reader, narrow phone screen, long content, or slow network.

Suggested commit message:

```text
Commit 6: Complete dashboard entry lists
```

Implement:

- Use one page-level `<h1>` and correctly nested section headings.
- Give status and background-update messages suitable live-region behavior without
  repeatedly announcing all entry content.
- Keep native links, buttons, lists, `<details>`, `<summary>`, and `<time>` semantics.
- Confirm visible keyboard focus and at least 44-by-44-pixel interactive targets.
- Style Needs check-in with clear priority that does not rely on color alone.
- Make cards stack cleanly at 320 CSS pixels with no page-level horizontal scrolling.
- Keep long item names, reasons, comments, currency, and timestamps from breaking the
  layout.
- Use a readable maximum width at larger viewport sizes.
- Respect the existing reduced-motion preference.
- Add or complete accessibility and keyboard tests for links, the retry control, and
  the Purchased disclosure.
- Verify the page never uses `dangerouslySetInnerHTML`, locally regroups entries, or
  changes API cents.
- Update README/developer documentation only where the implemented dashboard behavior
  needs to be recorded.
- Complete the implementation record below with real files, test counts, commands,
  and known limitations. Do not present planned work as completed work.
- Run the complete repository quality gate.

Commit gate:

```bash
make check
```

## Out of Scope

- Creating entries; DEV-012 owns the form and mutation.
- Entry detail, edit, and delete behavior; DEV-012 owns those flows.
- Performing a saved or purchased check-in; DEV-013 owns the API and DEV-014 owns the
  frontend experience.
- Editing resolved-entry comments; DEV-015 owns that behavior.
- Dashboard statistics; DEV-016 owns the calculation API and DEV-018 owns the
  frontend statistics panel.
- Opportunity-cost settings or equivalents; DEV-017 and DEV-018 own them.
- Recalculating the 48-hour eligibility rule in the browser.
- Moving an entry between arrays because a client-side countdown completed.
- Sorting response arrays again in the browser.
- Treating `needs_check_in` as a stored entry status.
- Sending formatted dollars, decimals, or floats to the API.
- Pagination or virtualized lists; the V1 DEV-010 endpoint is intentionally
  unpaginated.
- Final shared application-wide accessibility hardening; DEV-020 remains responsible
  for the cross-feature review.

## Implementation Record

Complete this section during Commit 6. Until then, it describes the expected record,
not completed behavior.

### Overview

Record how DEV-011 replaced the authenticated placeholder with the four server-owned
dashboard entry lists.

### Files and Responsibilities

List the final files that own:

- Dashboard API access and the TanStack Query hook.
- Currency and timestamp display formatting.
- Entry card and section presentation.
- Dashboard page composition and request states.
- Dashboard styles and tests.

### Verified Behavior

Record evidence that:

- All four arrays render, including independent empty states.
- Backend list membership and order remain unchanged.
- Only Needs check-in entries receive check-in navigation.
- Purchased starts collapsed.
- Loading, retryable errors, retry, cancellation, and expired authentication behave as
  designed.
- Money remains integer cents in data and becomes USD only for display.
- The layout works with keyboard input and narrow screens.

### Verification

Record the final `make check` date, frontend and backend test totals, production build
result, and any focused dashboard commands used during development.

### Limitations and Follow-up

Record remaining work accurately. At minimum, DEV-012 must add entry management,
DEV-014 must complete check-in navigation, and DEV-018 must add dashboard statistics.
