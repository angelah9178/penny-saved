# DEV-019 — Opportunity-Cost Settings UI

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Feature Rules](#feature-rules)
- [API and UI Contract](#api-and-ui-contract)
- [Commit 1 — Connect the Frontend to the Opportunity-Cost API](#commit-1--connect-the-frontend-to-the-opportunity-cost-api)
- [Commit 2 — Build the Protected Settings List](#commit-2--build-the-protected-settings-list)
- [Commit 3 — Build the Shared Example Form](#commit-3--build-the-shared-example-form)
- [Commit 4 — Add Create and Edit Workflows](#commit-4--add-create-and-edit-workflows)
- [Commit 5 — Add Safe Example Deletion](#commit-5--add-safe-example-deletion)
- [Commit 6 — Complete States, Cache Refresh, and Verification](#commit-6--complete-states-cache-refresh-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|                  | Commit                                                           | Title                                 | Depends on  |
| ---------------- | ---------------------------------------------------------------- | ------------------------------------- | ----------- |
| &#91;x&#93;      | [1](#commit-1--connect-the-frontend-to-the-opportunity-cost-api) | Connect opportunity-cost data         | DEV-017–018 |
| &#91;x&#93;      | [2](#commit-2--build-the-protected-settings-list)                | Build protected settings list         | Commit 1    |
| &#91;x&#93;      | [3](#commit-3--build-the-shared-example-form)                    | Build shared form and money rules     | Commit 2    |
| &#91;x&#93;      | [4](#commit-4--add-create-and-edit-workflows)                    | Add create and edit workflows         | Commit 3    |
| &#91;x&#93;      | [5](#commit-5--add-safe-example-deletion)                        | Add safe deletion                     | Commit 4    |
| &#91;&#160;&#93; | [6](#commit-6--complete-states-cache-refresh-and-verification)   | Complete states, refresh, and quality | Commits 1–5 |

## Objective

DEV-019 gives authenticated users a protected settings screen where they can manage
the personal comparisons shown in dashboard statistics. A user can list, create,
edit, and delete opportunity-cost examples without a full-page reload.

For example, the user can define:

```text
Label: Hours worked
Unit name: hours
Dollar value: $10.00
```

The frontend converts `$10.00` into `1,000` integer cents and sends only the three
documented mutable fields. After the server confirms a change, the settings list and
every cached statistics range refresh so the dashboard equivalents reflect the new
examples.

DEV-017 remains the source of truth for validation, ownership, ordering, and CRUD
behavior. DEV-018 remains the source of truth for calculating and displaying
equivalents. DEV-019 adds the user-facing management experience for those existing
backend capabilities.

## Feature Rules

Each example contains three user-editable values:

| Field        | Display input | Submitted value                            |
| ------------ | ------------- | ------------------------------------------ |
| Label        | Text          | Trimmed nonblank string, at most 120 chars |
| Unit name    | Text          | Trimmed nonblank string, at most 80 chars  |
| Dollar value | USD text      | Integer cents from 1 to 999,999,999,999    |

Money parsing follows the same exact rules as entry prices:

- accept ordinary decimal dollar input with at most two decimal places;
- reject exponent notation, commas, negatives, signs, and nonnumeric text;
- reject values below `$0.01` or above `$9,999,999,999.99`;
- convert with string parsing, never binary floating-point multiplication; and
- convert stored cents back to a two-decimal string when editing.

Duplicate labels remain valid. Two examples named “Hours worked” may intentionally
have different dollar values. The frontend uses each example's `id`, not its label or
array position, as the stable React key.

The list preserves the server order from DEV-017: `created_at ASC, id ASC`. The
browser does not sort examples by label or updated time and does not optimistically
invent a different order.

Only authenticated users may access `/settings/opportunity-costs`. Frontend route
protection is a convenience; the backend continues to enforce authentication and
ownership on every request.

## API and UI Contract

The frontend uses the four protected DEV-017 endpoints:

```text
GET    /api/opportunity-cost-examples
POST   /api/opportunity-cost-examples
PATCH  /api/opportunity-cost-examples/{example_id}
DELETE /api/opportunity-cost-examples/{example_id}
```

Create and update submit exactly:

```json
{
  "label": "Hours worked",
  "unit_name": "hours",
  "dollar_value_cents": 1000
}
```

The frontend never submits `id`, `user_id`, timestamps, or calculated equivalent
values. POST and PATCH consume the server-confirmed example envelope. DELETE consumes
the empty `204 No Content` response without attempting JSON parsing.

The settings page provides:

- a page heading and a clear path back to the dashboard;
- an ordered list showing label, unit name, and formatted dollar value;
- an empty state explaining how examples affect dashboard statistics;
- one shared accessible form for creating and editing;
- explicit edit and delete actions for each stable example ID;
- an accessible confirmation dialog naming the example before deletion;
- field-level and global validation or server errors;
- disabled pending controls that prevent duplicate mutations; and
- success announcements after confirmed create, update, and delete operations.

After every successful mutation, the frontend invalidates both:

```text
['opportunity-costs', 'list']
['stats', ...every cached statistics range]
```

DEV-018 already provides the shared invalidation foundation. DEV-019 uses it so a
changed example affects the settings screen and dashboard equivalents immediately.

## Commit 1 — Connect the Frontend to the Opportunity-Cost API

**Status:** Complete — `4ff2100`.

### In Plain English

Commit 1 teaches the frontend how to call the four opportunity-cost endpoints. It
adds functions for listing, creating, updating, and deleting examples and wraps them
in TanStack Query options and mutation options.

In other words, this commit connects the frontend data layer to the existing backend
API. `GET` retrieves the user's examples, `POST` creates one, `PATCH` updates the
example identified by its ID, and `DELETE` removes that identified example. The
frontend sends and receives the DEV-017 contracts; it does not recalculate statistics
or replace backend validation and ownership checks.

Nothing is visible yet. This commit is the data connection between the existing
DEV-017 backend and the settings components built later. It also establishes the
correct cache keys, session-expiry return path, cancellation, retry rules, and
post-mutation refresh behavior before UI code depends on them.

Suggested commit message:

```text
Commit 1: Connect the frontend to opportunity-cost examples
```

Implement:

- Add credentialed GET, POST, PATCH, and DELETE API functions.
- Encode `example_id` safely in PATCH and DELETE URLs.
- Forward TanStack Query cancellation to GET.
- Consume the empty DELETE `204` without parsing a body.
- Add list query options using `queryKeys.opportunityCosts.list()`.
- Use the established protected-request wrapper and
  `/settings/opportunity-costs` return path.
- Apply shared query retry behavior to GET and disable mutation retries.
- Add create, update, and delete mutation options using the exact request types.
- On success, use the DEV-018 invalidation helper to refresh the example list and
  every statistics range.
- Add API and query tests for exact methods, URLs, bodies, credentials, cancellation,
  response parsing, cache keys, invalidation, session expiry, and retry behavior.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 2 — Build the Protected Settings List

**Status:** Complete — `cc56758`.

### In Plain English

Commit 2 creates the page a user visits to manage examples. It registers the protected
`/settings/opportunity-costs` route, adds a dashboard/settings navigation path, and
renders the examples returned by Commit 1 in the server's stable order.

This is a separate management page rather than another section of the dashboard.
Authenticated users can navigate to it to see their opportunity-cost examples and
the create, edit, and delete actions associated with managing them, then return to
the dashboard through a clear link.

At this point the user can see existing examples but cannot change them yet. The page
shows what each unit costs, explains an empty list, and exposes clear actions that
later commits connect to create, edit, and delete behavior.

Suggested commit message:

```text
Commit 2: Build the opportunity-cost settings list
```

Implement:

- Register `/settings/opportunity-costs` beneath the existing protected route.
- Add a discoverable dashboard link to manage opportunity-cost examples.
- Add the settings page and ordered example-list components.
- Render label, unit name, and `dollar_value_cents` formatted as USD.
- Use example IDs as list keys and preserve server order and duplicate labels.
- Add a clear create action and per-example edit/delete triggers.
- Add an empty state explaining that examples turn saved money into relatable units.
- Add basic initial loading and recoverable list-error handling without showing a
  failed request as an empty list.
- Add component/router tests for protection, navigation, populated and empty lists,
  duplicate labels, ordering, long content, large values, loading, and retry.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Commit 3 — Build the Shared Example Form

**Status:** Complete — `e4ed1bd`.

### In Plain English

Commit 3 builds one accessible form that both create and edit workflows will share.
It validates and trims the label and unit, parses a dollar string into exact integer
cents, and converts existing cents back into a two-decimal edit value.

The form contains a label, a unit name, and a dollar value. It rejects blank or
overlong text and invalid money formats such as commas, signs, exponent notation,
negative values, and more than two decimal places. Valid dollar input is converted
to integer cents using string parsing, so `$10.00` becomes `1,000` without
floating-point rounding.

Create mode starts empty, while edit mode can display server-confirmed values with
exactly two decimal places. Both modes use the same validation and return the same
three-field API payload to their parent component.

The form is still presentation and validation infrastructure. It can report valid
data through a callback, but it does not send create or update requests until Commit
4 connects those actions.

Suggested commit message:

```text
Commit 3: Build the shared opportunity-cost form
```

Implement:

- Extract or reuse the established exact dollar-to-cents parsing utility rather than
  duplicating entry price arithmetic.
- Keep entry price behavior and tests unchanged during any shared-utility refactor.
- Add the 120-character label and 80-character unit-name rules.
- Trim text before validating blank values and lengths.
- Enforce the `$0.01` through `$9,999,999,999.99` dollar-value range.
- Reject exponent notation, commas, signs, negatives, extra decimals, and unsafe
  values.
- Add a reusable React Hook Form component with accessible labels, help text, error
  associations, and a focused error summary.
- Support empty create defaults and server-confirmed edit defaults.
- Disable submission while pending and expose create/edit-specific button labels.
- Add validation and component tests for normalization, exact boundaries, invalid
  currency, keyboard submission, error focus, and edit-value formatting.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 4 — Add Create and Edit Workflows

**Status:** Complete — `a0a7d50`.

### In Plain English

Commit 4 lets the user create a new example and edit an existing one. The shared form
from Commit 3 converts user-friendly dollar input into the exact request body, then
Commit 1's mutations send it to the protected API.

This is the commit where the page's Create and Edit controls become functional.
Create opens an empty form and calls `POST /api/opportunity-cost-examples`; Edit opens
the same form with the selected server values and calls
`PATCH /api/opportunity-cost-examples/{example_id}`.

After the backend accepts either request, the user sees a success confirmation, the
form closes, the example list refreshes, and cached dashboard statistics refresh so
the changed comparisons are used there too. Failed requests keep the user's input
available and show safe field-level or global feedback.

The interface changes only after the server confirms success. It prevents duplicate
submissions, displays field or global server errors, announces the result, refreshes
both examples and statistics, and returns the user to the stable settings list.

Suggested commit message:

```text
Commit 4: Add opportunity-cost create and edit workflows
```

Implement:

- Connect the create action to an empty shared form.
- Connect each edit action to the matching server-confirmed example values.
- Submit only `label`, `unit_name`, and `dollar_value_cents`.
- Prevent duplicate submits and keep controls disabled while a request is pending.
- Map backend field errors to their matching controls and show global errors safely.
- Do not expose private server details from unexpected, ownership, or missing errors.
- On success, announce creation/update and close or reset the form deliberately.
- Refresh the stable example list and every statistics range after server success.
- Handle stale edit `403`/`404` by refreshing the list and explaining that the
  example is no longer available.
- Preserve auth-expiry redirection to login with the settings return path.
- Add integration tests for create/edit success, normalization, exact payloads,
  duplicate labels, server validation, unavailable service, stale ownership-safe
  errors, session expiry, cache refresh, and duplicate-submit prevention.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Commit 5 — Add Safe Example Deletion

**Status:** Complete — `3a58381`.

### In Plain English

Commit 5 lets the user delete an example, but only after an explicit confirmation
that names the selected comparison. The dialog traps keyboard focus, closes on Escape
or Cancel, and returns focus to the original delete button.

This commit connects the visible Delete action to
`DELETE /api/opportunity-cost-examples/{example_id}`. Selecting Delete only opens the
confirmation; the request is not sent until the user activates the clearly labeled
destructive confirmation button.

While the request is pending, repeat confirmation is disabled. A recoverable failure
keeps both the example and dialog available with safe feedback. Only a confirmed
`204 No Content` closes the dialog and allows refreshed server data to remove the
example.

The example remains visible while deletion is pending or if the request fails. It is
removed only after the backend returns `204`. A successful deletion refreshes both
the settings list and statistics, so the removed equivalent disappears from the
dashboard.

Suggested commit message:

```text
Commit 5: Add safe opportunity-cost deletion
```

Implement:

- Add an accessible `alertdialog` naming the example.
- Trap focus between dialog controls and return focus to the trigger on close.
- Support explicit Cancel, Escape, and one clearly labeled destructive action.
- Disable repeat confirmation while DELETE is pending.
- Keep the example and dialog available after recoverable failure.
- Remove the example only after the server confirms an empty `204`.
- Refresh the example list and every statistics range after success.
- Handle stale `403`/`404` safely by refreshing server truth without exposing another
  user's data.
- Preserve session-expiry behavior and the settings return path.
- Add tests for confirmation text, focus trap/restoration, Escape, cancellation,
  duplicate-click prevention, success, failure, stale records, auth expiry, and cache
  refresh.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
make frontend-build
```

## Commit 6 — Complete States, Cache Refresh, and Verification

**Status:** Implemented and verified; awaiting manual commit.

### In Plain English

Commit 6 proves the complete settings experience works reliably as one feature. It
follows examples through create, ordered list, edit, delete, and dashboard-equivalent
refresh while checking loading, empty, failure, retry, and expired-session behavior.

It also finishes the page's accessibility and responsive behavior, verifies that
rapid actions cannot leave stale forms or cache data visible, and records the final
quality results. This commit should mostly strengthen tests and polish integration,
not introduce a new example-management capability.

Suggested commit message:

```text
Commit 6: Complete opportunity-cost settings verification
```

Implement:

- Add a complete MSW-backed create/list/edit/delete settings journey.
- Prove every successful mutation refreshes both examples and all statistics ranges.
- Prove failed mutations do not remove or replace server-confirmed list data.
- Verify background list refresh retains content with an updating indicator.
- Verify retry recovery, rapid action safety, stale-response protection, and auth
  expiry across list and mutation paths.
- Verify duplicate labels and stable server order throughout the complete workflow.
- Complete semantic headings, landmarks, labels, descriptions, error associations,
  live announcements, keyboard order, focus movement, dialog behavior, touch targets,
  long-content wrapping, and mobile-to-desktop layouts within DEV-019's components.
- Confirm no raw API/server error, credentials, ownership data, or integer-cent
  arithmetic leaks into user-facing output.
- Update this tracker, statuses, hashes, implementation record, and actual test
  results after each corresponding gate passes.

Commit gate:

```bash
make check
```

## Out of Scope

- Changing backend opportunity-cost CRUD, ownership, validation, or ordering rules;
  DEV-017 owns them.
- Recalculating statistics or equivalent units in the settings frontend; DEV-018 owns
  those backend calculations and dashboard presentation.
- Unique labels, drag-and-drop ordering, sharing, public templates, categories,
  currencies other than USD, soft deletion, pagination, or bulk actions.
- Editing server-owned IDs, owners, timestamps, or calculated values.
- Final cross-application accessibility, responsive, security, observability, smoke,
  and release work owned by DEV-020 through DEV-024.

## Implementation Record

Complete this section as the commit series is implemented.

### Commit Hashes

- Commit 1: `4ff2100` — `Commit 1: Connect the frontend to opportunity-cost examples`.
- Commit 2: `cc56758` — `Commit 2: Build the opportunity-cost settings list`.
- Commit 3: `e4ed1bd` — `Commit 3: Build the shared opportunity-cost form`.
- Commit 4: `a0a7d50` — `Commit 4: Add opportunity-cost create and edit workflows`.
- Commit 5: `3a58381` — `Commit 5: Add safe opportunity-cost deletion`.
- Commit 6: Pending.

### What Changed

Commit 1 added the opportunity-cost API module and reusable TanStack Query data
layer. The frontend can now list, create, update, and delete examples through the
DEV-017 endpoints. Requests use the protected settings return path, GET cancellation
and shared retry behavior, mutation retries are disabled, IDs are safely encoded,
and every successful mutation invalidates both the example list and all statistics
ranges.

Focused API and query tests cover request methods, URLs, bodies, credentials,
response handling, cancellation, cache keys, invalidation, session expiry, and retry
behavior.

Commit 2 added the separate protected `/settings/opportunity-costs` management page,
a discoverable dashboard link, and a clear return path to the dashboard. The page
renders examples in server order with formatted dollar values and stable IDs, exposes
create/edit/delete triggers for later workflows, and distinguishes initial loading,
recoverable errors, background refreshes, and a genuine empty list.

Page, component, dashboard, and router tests cover route protection, navigation,
empty and populated states, duplicate labels, ordering, long content, large values,
keyboard order, retry behavior, and background refreshes.

Commit 3 added a shared accessible form for create and edit modes plus focused
validation and conversion helpers. It trims label and unit values, enforces their
120- and 80-character limits, reuses the established exact dollar parser, formats
server cents for editing, associates help and errors with their controls, focuses
the validation summary, and disables controls while submission is pending.

Validation and component tests cover normalization, exact money boundaries,
unsupported money syntax, Unicode-aware text limits, edit formatting, keyboard
submission, accessible errors, and pending-state duplicate-submit prevention.

Commit 4 connected the page's create and edit controls to the shared form and the
POST/PATCH mutations. It opens empty or server-prefilled values as appropriate,
submits only the three mutable fields, keeps input available after recoverable
failures, maps backend field errors safely, announces confirmed success, and closes
the form only after server confirmation. Successful mutations refresh the list and
all statistics ranges through the existing cache helper.

Stale edit responses refresh server truth and show an ownership-safe explanation.
Integration tests cover exact normalized payloads, server-confirmed create/edit
results, safe validation and service errors, stale edits, pending controls, and
duplicate-submit prevention. Session expiry and cache invalidation remain covered by
the Commit 1 mutation tests.

Commit 5 added an accessible deletion confirmation that names the selected example,
traps keyboard focus, supports Cancel and Escape, restores focus to the trigger, and
disables repeat confirmation while DELETE is pending. Recoverable errors retain the
example and dialog with safe feedback; stale ownership or missing responses refresh
server truth without exposing private details.

The dialog closes after the server confirms `204 No Content`, then the shared
mutation invalidates the example list and every statistics range. Component and page
tests cover cancellation, focus behavior, Escape, duplicate clicks, confirmed
success, recoverable failure, stale `403`/`404` responses, and server-driven removal.
Session expiry and cache refresh remain covered by the Commit 1 mutation tests.

Commit 6 added a stateful MSW integration journey that follows duplicate-label
examples through stable ordered listing, creation, editing, and confirmed deletion.
It proves every successful mutation invalidates all five cached statistics ranges,
and proves a failed edit cannot replace the server-confirmed list or expose a raw
server message. Existing focused coverage completes loading, empty, retry, background
refresh, stale response, auth expiry, rapid action, keyboard, dialog, long-content,
and responsive-layout behavior.

The master development plan now marks completed DEV-018. DEV-019 remains unchecked
until its final manual commit and normal merge/acceptance process are complete.

### What It Achieved

The frontend now has a tested connection to the backend opportunity-cost API that
later commits can use without duplicating request, authentication, or cache-refresh
logic. This commit intentionally does not render user-visible settings UI.

Authenticated users can open a dedicated management screen and see their current
examples and management actions.

Create and edit now share one tested form that produces the exact three-field API
payload, and both workflows are connected to the backend. Users can also safely
delete an example through an explicit, server-confirmed workflow.

The complete opportunity-cost settings experience is now implemented and verified
as one server-driven feature. Changes refresh both management data and dashboard
equivalents without a full-page reload, while failed operations preserve confirmed
data and avoid leaking private backend details.

### Usage and Safety Notes

The frontend sends integer cents and only the three documented mutable fields. The
backend remains authoritative for validation, authentication, ownership, ordering,
and persistence. Successful example changes must invalidate both settings and
statistics data.

### Verification

Record each focused gate after its commit and the final `make check` result after
Commit 6.

Commit 1 passed on 2026-08-06:

```text
make frontend-format-check — passed
make frontend-lint         — passed
make frontend-typecheck    — passed
make frontend-test         — passed (43 files, 349 tests)
```

Commit 2 passed on 2026-08-06:

```text
make frontend-format-check — passed
make frontend-lint         — passed
make frontend-typecheck    — passed
make frontend-test         — passed (45 files, 357 tests)
make frontend-build        — passed
```

Commit 3 passed on 2026-08-06:

```text
make frontend-format-check — passed
make frontend-lint         — passed
make frontend-typecheck    — passed
make frontend-test         — passed (47 files, 386 tests)
```

Commit 4 passed on 2026-08-06:

```text
make frontend-format-check — passed
make frontend-lint         — passed
make frontend-typecheck    — passed
make frontend-test         — passed (47 files, 391 tests)
make frontend-build        — passed
```

Commit 5 passed on 2026-08-06:

```text
make frontend-format-check — passed
make frontend-lint         — passed
make frontend-typecheck    — passed
make frontend-test         — passed (48 files, 398 tests)
make frontend-build        — passed
```

Commit 6 passed on 2026-08-06:

```text
make check — passed
frontend: 49 files, 400 tests passed
backend:  486 tests passed
frontend production build passed
backend application build check passed
```

### Limitations and Follow-Up

DEV-020 through DEV-024 complete shared hardening, smoke coverage, operations, and
release work.
