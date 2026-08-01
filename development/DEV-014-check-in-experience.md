# DEV-014 — Check-In Experience

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Check-In Experience in Plain English](#check-in-experience-in-plain-english)
- [Frontend Route and API](#frontend-route-and-api)
- [Commit 1 — Connect Check-In to the Backend](#commit-1--connect-check-in-to-the-backend)
- [Commit 2 — Build the Check-In Form](#commit-2--build-the-check-in-form)
- [Commit 3 — Add the Protected Check-In Route](#commit-3--add-the-protected-check-in-route)
- [Commit 4 — Submit and Confirm Both Outcomes](#commit-4--submit-and-confirm-both-outcomes)
- [Commit 5 — Handle Conflicts and Request Failures](#commit-5--handle-conflicts-and-request-failures)
- [Commit 6 — Complete Accessibility, Integration, and Verification](#commit-6--complete-accessibility-integration-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after the implementation and commit gate for that row are
complete.

|             | Commit                                                              | Title                                   | Depends on  |
| ----------- | ------------------------------------------------------------------- | --------------------------------------- | ----------- |
| &#91;x&#93; | [1](#commit-1--connect-check-in-to-the-backend)                     | Connect check-in to the backend         | DEV-013     |
| &#91;x&#93; | [2](#commit-2--build-the-check-in-form)                             | Build the check-in form                 | Commit 1    |
| &#91;x&#93; | [3](#commit-3--add-the-protected-check-in-route)                    | Add the protected check-in route        | Commit 2    |
| &#91;x&#93; | [4](#commit-4--submit-and-confirm-both-outcomes)                    | Submit and confirm both outcomes        | Commit 3    |
| &#91;x&#93; | [5](#commit-5--handle-conflicts-and-request-failures)               | Handle conflicts and request failures   | Commit 4    |
| &#91; &#93; | [6](#commit-6--complete-accessibility-integration-and-verification) | Complete accessibility and verification | Commits 1–5 |

## Objective

DEV-014 gives an eligible user the visible frontend experience for resolving a
waiting entry. From the dashboard's Needs check-in section, the user can open the
protected check-in route, review the original purchase decision, explicitly choose
whether they avoided or made the purchase, optionally add a reflection, and submit
the choice to the atomic DEV-013 API.

This work uses the existing backend operations:

```text
GET  /api/entries/{entry_id}          → load the owned entry and its original context
POST /api/entries/{entry_id}/check-in → resolve it as saved or purchased
```

The frontend does not calculate whether 48 hours have passed and does not move an
entry between dashboard buckets on its own. The server remains authoritative for
ownership, stored status, and exact eligibility. This matters when a browser clock is
wrong, a dashboard is stale, or another tab resolves the entry first.

After a successful check-in, the returned entry becomes the current detail-cache
value and every view derived from the resolution is refreshed. The user sees an
accessible confirmation that states the actual saved or purchased result and can
return to a dashboard showing current server data.

Complete and commit each section in order. Every commit must leave frontend format,
lint, typecheck, and focused tests green. Commit 6 runs the full repository quality
gate.

## Check-In Experience in Plain English

The check-in page reminds the user what they considered buying, how much it cost, and
why they wanted it. The page then asks what actually happened. Neither answer is
preselected because saving and purchasing have different meanings and the user must
make a deliberate choice.

```text
Dashboard: Needs check-in
          ↓ select Check in
Review item, price, reason, and waiting context
          ↓ choose exactly one outcome
┌───────────────────────┬──────────────────────┐
│ I did not buy it      │ I bought it          │
│ result = saved        │ result = purchased   │
└───────────────────────┴──────────────────────┘
          ↓ optionally add a reflection
Server validates ownership, status, and the exact 48-hour boundary
          ↓
Confirmation and refreshed dashboard data
```

An optional comment helps the user remember what influenced the decision. Outer
whitespace is removed and blank text becomes `null`, matching the DEV-013 contract.
The comment is reflection, not the decision itself; the form cannot submit until the
user explicitly chooses saved or purchased.

The server may reject a request even when the page looked eligible. For example,
another tab may already have resolved the entry, or the browser and server clocks may
disagree near the 48-hour boundary. The page explains what happened, refreshes server
truth where appropriate, and never pretends that an unconfirmed mutation succeeded.

## Frontend Route and API

| Route                          | Purpose                                     | Backend API                                         |
| ------------------------------ | ------------------------------------------- | --------------------------------------------------- |
| `/entries/{entry_id}/check-in` | Review and resolve one eligible owned entry | `GET`, then `POST /api/entries/{entry_id}/check-in` |

The route is protected by the existing authentication guard and uses the shared
credentialed `apiFetch` client. Its submission body contains only the check-in
contract fields:

```json
{
  "result": "saved",
  "comment": "I waited and realized I can borrow one."
}
```

`result` is either `saved` or `purchased`. `comment` is optional and must not be used
to send item name, price, reason, ownership, status, or timestamps back to the server.

On success, cache handling must:

- Store the returned `EntryEnvelope` under `queryKeys.entries.detail(entryId)`.
- Invalidate `queryKeys.entries.dashboard()` so the entry moves to the confirmed
  saved or purchased bucket using server data.
- Invalidate statistics-related query keys because later DEV-016 and DEV-018 views
  derive totals from resolved entries and `checked_in_at`.
- Avoid retrying the mutation automatically. A deliberate lifecycle decision must
  never be repeated without the user asking.

## Commit 1 — Connect Check-In to the Backend

**Status:** Complete.

Commit 1 adds the typed frontend operation and TanStack Query mutation used by the
later screen. It connects existing frontend infrastructure to DEV-013 without adding
the visible check-in page yet.

In plain English, this commit builds the behind-the-scenes messenger. Later code can
say “resolve this entry as saved” or “resolve it as purchased” without assembling a
URL, managing credentials, decoding the response, or remembering which cached views
have become stale.

For example, a later page can call the frontend operation like this:

```ts
checkIn({
  entryId: "abc-123",
  result: "saved",
  comment: "I realized I did not need it.",
});
```

Commit 1 turns that instruction into the authenticated backend request:

```http
POST /api/entries/abc-123/check-in
Content-Type: application/json

{
  "result": "saved",
  "comment": "I realized I did not need it."
}
```

It then receives the updated entry, places it in the detail cache, and marks the
dashboard and statistics data for refresh. Backend errors remain available for the
future page to explain. The mutation is never retried automatically because check-in
is a deliberate, one-time lifecycle decision.

Commit 1 does not create a page, form, or visible button. It installs the frontend
“wiring”; Commits 2 through 4 add the controls and connect the complete user journey.

```text
Future check-in form
        ↓ passes entry ID, result, and optional comment
check-in mutation hook
        ↓ uses shared credentialed API client
POST /api/entries/{entry_id}/check-in
        ↓ returns the server-confirmed entry
detail cache updated; dashboard and statistics invalidated
```

Suggested commit message:

```text
Commit 1: Connect check-in to the backend
```

Implement:

- Add frontend contract types for the `saved` and `purchased` check-in results and
  the request body.
- Add a typed API function for `POST /api/entries/{entry_id}/check-in`.
- Send only `result` and normalized `comment` in the JSON body.
- Add a check-in mutation hook and explicitly disable automatic retries.
- On success, store the returned entry detail and invalidate dashboard and
  statistics-related query keys.
- Reuse the existing protected-request reporting for `401 unauthorized` responses.
- Preserve the backend's structured error code and field details for the page to
  interpret in later commits.
- Add focused tests for the HTTP method, encoded entry path, body, response type,
  mutation retry behavior, and every cache effect.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 2 — Build the Check-In Form

**Status:** Complete.

Commit 2 builds the reusable visible form for choosing an outcome and writing the
optional reflection. It is responsible for collecting a clear decision, not for
loading an entry or choosing what happens after success.

In plain English, this commit asks one required question—“Did you buy it?”—and gives
the user an optional place to explain why. It never guesses the answer from button
order, a default value, or the entry's price.

The two choices use the language shown to the user while sending the stable API
values:

| Visible choice   | API value   | Meaning                                     |
| ---------------- | ----------- | ------------------------------------------- |
| I did not buy it | `saved`     | The user avoided the considered purchase.   |
| I bought it      | `purchased` | The user completed the considered purchase. |

Suggested commit message:

```text
Commit 2: Build the check-in form
```

Implement:

- Present saved and purchased as one clearly labelled, keyboard-operable choice
  group with neither option selected initially.
- Require an explicit result before allowing submission and place focus on, or
  announce, the result error when it is missing.
- Add an optional labelled comment control with its character limit communicated to
  assistive technology.
- Trim outer comment whitespace and convert empty or whitespace-only input to `null`
  before calling the submit callback.
- Enforce the backend's 4,000-character normalized comment limit without preventing
  the user from correcting invalid input.
- Disable every resolution action while submission is pending so one interaction
  cannot create duplicate requests.
- Preserve the chosen result and comment after a failed request.
- Announce validation and pending states without relying on color alone.
- Add component tests for both results, no selected result, omitted and blank
  comments, trimming, the length boundary, keyboard use, and duplicate submission.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 3 — Add the Protected Check-In Route

**Status:** Complete.

Commit 3 adds `/entries/{entry_id}/check-in`, loads the current owned entry, and
places its original decision context beside the form from Commit 2.

In plain English, this commit makes sure the user knows which decision they are
resolving. Before asking for an answer, it shows the item, price, original reason, and
relevant date information returned by the backend. It also prevents a copied URL from
turning into an unsafe or misleading screen.

```text
Protected route opens
        ↓
Load GET /api/entries/{entry_id}
        ↓
┌─────────────────────────────────────────┐
│ Eligible waiting entry → show context   │
│ and check-in form                       │
├─────────────────────────────────────────┤
│ Loading → show loading state            │
│ 401 → preserve route and return to login│
│ 403/404 → show safe unavailable state   │
│ resolved/waiting → show server truth    │
└─────────────────────────────────────────┘
```

Suggested commit message:

```text
Commit 3: Add the protected check-in route
```

Implement:

- Register the parameterized route beneath the existing protected application shell.
- Load the entry through the existing cancellable detail query rather than copying
  dashboard state into the page.
- Display the item name, formatted price, original reason, creation time, and server
  lifecycle context needed to make the decision.
- Render the form only when the current response identifies the entry as eligible
  for check-in; do not infer eligibility by comparing the browser clock.
- Handle loading, request failure, `403 forbidden`, `404 not_found`, and malformed
  entry identifiers with useful, non-leaking states and safe navigation.
- Send an expired session back through the established login flow with the full
  check-in route as the safe return destination.
- Ensure the existing Needs check-in dashboard link reaches the new route and that
  Waiting, Saved, and Purchased cards do not gain a check-in action.
- Add route tests for protection, parameter handling, loading, original context,
  access errors, direct navigation, and the dashboard-to-check-in journey.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 4 — Submit and Confirm Both Outcomes

**Status:** Complete.

Commit 4 connects the route and form to the mutation from Commit 1. It completes the
successful saved and purchased journeys and shows a confirmation based on the actual
server response.

In plain English, this commit makes the buttons real. After the user deliberately
chooses and submits an outcome, the page waits for the server. Only a successful
response produces a success message. That message says whether the item was saved or
purchased and gives the user a clear way back to the refreshed dashboard.

Commit 3 already added the page and its basic mutation call so an active form would
not contain a submit button that silently did nothing. Commit 4 completes everything
the user expects after that call: it waits for the confirmed response, replaces the
form with the matching saved or purchased confirmation, and provides the return to
the refreshed dashboard. Put another way, Commit 3 makes submission technically
possible; Commit 4 makes successful submission a complete and trustworthy user
journey.

```text
User submits saved or purchased
             ↓
Form becomes pending and cannot submit again
             ↓
Server returns updated entry
             ↓
Show matching confirmation from response status
             ↓
Return to dashboard with refreshed server data
```

Suggested commit message:

```text
Commit 4: Submit and confirm check-in outcomes
```

Implement:

- Call the check-in mutation with the route entry ID, selected result, and normalized
  optional comment.
- Keep the page and all resolution controls in one pending state until the request
  settles.
- Do not optimistically move the entry or announce success before the API confirms
  the transition.
- Replace the form with an accessible confirmation that uses the returned status,
  item name, and normalized comment rather than assumptions from submitted input.
- Provide a clear return-to-dashboard action after confirmation.
- Ensure saved results appear in Saved and purchased results appear in Purchased
  after dashboard refetch.
- Keep the confirmed detail cache aligned with the response while dashboard and
  future statistics data revalidate.
- Add tests for complete saved and purchased submissions, with and without comments,
  confirmation wording, navigation, cache updates, and a single request during rapid
  repeated activation.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 5 — Handle Conflicts and Request Failures

**Status:** Complete.

Commit 5 makes the page honest when the browser's view is older than the server's
truth or when a request cannot complete.

In plain English, a check-in page can become stale while it is open. Another tab may
resolve the entry first, or the server may say the full waiting period has not ended
even though the user's device clock suggests otherwise. This commit explains those
conditions, refreshes the right information, and lets the user recover without
turning a failed request into a false success.

Error behavior:

| Backend response                      | Frontend behavior                                                    |
| ------------------------------------- | -------------------------------------------------------------------- |
| `409 early_check_in`                  | Explain that check-in is not available yet and refresh server truth. |
| `409 invalid_entry_status`            | Refresh detail/dashboard data and show the already-resolved state.   |
| `401 unauthorized`                    | Start the established session-expiry flow with a safe return path.   |
| `403 forbidden` or `404 not_found`    | Replace the form with a safe unavailable state.                      |
| `422 validation_error`                | Associate useful field details with result or comment when possible. |
| Network, `5xx`, or unexpected failure | Keep the user's input and offer an explicit retry.                   |

Suggested commit message:

```text
Commit 5: Handle check-in conflicts and failures
```

Implement:

- Interpret backend error codes instead of using status alone for both `409`
  conditions.
- On `early_check_in`, never start a browser countdown that grants eligibility;
  refresh detail and dashboard queries and guide the user back to current data.
- On `invalid_entry_status`, refresh the detail and dashboard before presenting the
  server-confirmed saved or purchased state.
- Preserve result and comment input for retryable failures and re-enable submission
  only after the failed request settles.
- Map validation details to the correct form control while also providing a form-level
  summary for errors that do not belong to one field.
- Coordinate `401` with the existing session-expiry behavior without duplicate
  notices or unsafe return URLs.
- Cancel obsolete detail reads on unmount and prevent late responses from replacing
  a newer success or conflict state.
- Add focused tests for clock disagreement, stale status, expired authentication,
  access loss, validation, network failure, retry, and preserved form values.

Commit gate:

```bash
make frontend-format-check
make frontend-lint
make frontend-typecheck
make frontend-test
```

## Commit 6 — Complete Accessibility, Integration, and Verification

**Status:** Planned.

Commit 6 reviews DEV-014 as one complete experience, closes gaps between the focused
commits, and records the behavior that was actually implemented.

In plain English, the earlier commits build each part of check-in. This final commit
proves the entire journey works for both answers, remains understandable during slow
or failed requests, works without a mouse, and leaves every cached view consistent
with the server.

Suggested commit message:

```text
Commit 6: Complete the check-in experience
```

Implement:

- Add protected-route integration tests covering dashboard navigation, entry load,
  explicit resolution, optional comment, confirmation, and return to the refreshed
  dashboard for both saved and purchased results.
- Verify the choice group, comment, validation messages, pending announcement,
  conflict notice, confirmation, and navigation have correct labels, focus order,
  focus placement, and live-region behavior.
- Verify rapid clicks, Enter presses, and repeated touch activation cannot submit the
  mutation twice.
- Verify narrow and wide layouts with long item names, reasons, comments, prices, and
  server messages.
- Confirm the frontend never calculates eligibility, invents a lifecycle transition,
  or treats a client timestamp as permission to check in.
- Confirm successful results update detail and refresh dashboard and all
  statistics-related query families.
- Confirm every failure preserves server truth and no failed request displays the
  success confirmation.
- Update this document's tracker, statuses, implementation record, commit hashes,
  verification totals, and discovered limitations.
- Run whitespace validation and the full repository quality gate.

Commit gate:

```bash
git diff --check
make check
```

## Out of Scope

DEV-014 does not include:

- Reimplementing check-in ownership, locking, lifecycle, or 48-hour eligibility in
  the browser. DEV-013's backend remains authoritative.
- Automatically resolving an entry when 48 hours pass. The user must explicitly
  choose saved or purchased.
- Editing a comment after a successful resolution; DEV-015 owns resolved-entry
  comment editing.
- Reversing a saved or purchased result or allowing a second check-in.
- Adding statistics calculations or opportunity-cost equivalents; DEV-016 through
  DEV-019 own those APIs and screens.
- Optimistically moving entries between dashboard buckets before the server confirms
  the result.
- Changing item name, price, or reason during check-in; DEV-012 owns edits while an
  entry remains waiting.
- Changing the backend API or database schema unless a separately reviewed defect
  requires it.
- The final cross-feature WCAG 2.2 AA and responsive application audit; DEV-020 owns
  that broader review.

## Implementation Record

Complete this section during Commit 6. Record the final commit hashes, meaningful
design decisions, test totals, verification date, and follow-up work. Keep the table
of contents, tracker, status labels, commit descriptions, and actual implementation
synchronized as the series is completed.
