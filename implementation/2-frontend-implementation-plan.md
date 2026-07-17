# Frontend Implementation Plan

## Scope and Principles

The frontend is a responsive React single-page application. It renders server-owned state, collects validated input, and provides clear feedback. It must not decide check-in eligibility, regroup entries, calculate saved totals, or infer authorization.

Use React functional components, strict TypeScript, React Router, TanStack Query, React Hook Form, and Zod. Server responses remain the authority after every mutation.

## Application Structure

```text
frontend/src/
  api/
    client.ts
    errors.ts
  app/
    App.tsx
    providers.tsx
    queryClient.ts
  components/
    Button.tsx
    Currency.tsx
    EmptyState.tsx
    ErrorAlert.tsx
    Field.tsx
    Loading.tsx
    Modal.tsx
    PageShell.tsx
  features/
    auth/
    entries/
    opportunity-costs/
    stats/
  hooks/
  lib/
    currency.ts
    dateTime.ts
  pages/
  routes/
    router.tsx
    ProtectedRoute.tsx
    GuestRoute.tsx
  test/
    handlers.ts
    server.ts
    render.tsx
  types/
    api.ts
```

Keep reusable primitives in `components`; domain UI and query hooks live with their feature. Pages compose features and should contain little business logic.

## Routes

| Route | Access | Screen |
|---|---|---|
| `/` | public | Redirect to `/dashboard` if authenticated, otherwise `/login` |
| `/signup` | guest | Signup form |
| `/login` | guest | Login form |
| `/dashboard` | protected | Stats and grouped entries |
| `/entries/new` | protected | Add impulse purchase |
| `/entries/:entryId` | protected | Entry details and status-appropriate actions |
| `/entries/:entryId/check-in` | protected | Eligible check-in form |
| `/settings/opportunity-costs` | protected | Manage examples |
| `*` | any | Not-found screen |

Use route-level lazy imports. Protected routes wait for the `/auth/me` bootstrap query before rendering or redirecting so refreshes do not flash the login page. Guest routes similarly redirect authenticated users.

## API Client

Create one `apiFetch<T>()` wrapper:

- Base path comes from `VITE_API_BASE_URL`, defaulting to `/api`.
- Always sends `credentials: "include"`, `Accept: application/json`, and JSON `Content-Type` when a body exists.
- Parses successful JSON; handles `204` without parsing.
- Converts the standard error envelope into `ApiError` with `status`, `code`, `message`, and optional `fields`.
- On `401`, clears auth-dependent cached data and navigates to login while preserving a safe return path.
- Supports `AbortSignal` from TanStack Query.
- Does not retry mutations or `4xx` responses. Queries may retry network/`5xx` failures at most twice with backoff.

Define explicit TypeScript types for `User`, `Entry`, `DashboardEntries`, `StatsSummary`, `OpportunityCostExample`, request payloads, enums, and error envelopes. Compile with `strict`, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.

## Query Keys and Cache Rules

```text
['auth', 'me']
['entries', 'dashboard']
['entries', 'detail', entryId]
['stats', 'summary', range]
['opportunity-costs', 'list']
```

- Auth bootstrap: `staleTime` 5 minutes; no retry on `401`.
- Dashboard/detail: short stale time (about 30 seconds).
- Stats: keyed by range and invalidated after check-in.
- Opportunity costs: invalidated after example CRUD; stats is also invalidated because equivalents change.
- Entry creation/edit/delete/check-in/comment mutation invalidates dashboard and affected detail.
- Prefer setting mutation response data into the detail cache, followed by invalidation. Avoid optimistic lifecycle transitions; conflicts must reflect server truth.
- Clear the entire query cache on logout.

## Authentication UI

Signup and login use email and password fields with visible labels, autocomplete values (`email`, `new-password`, `current-password`), and submit-state disabling. Client validation improves feedback but backend validation remains authoritative.

- Normalize email by trimming for submission; backend owns lowercase normalization.
- Do not store the password outside form state or log form payloads.
- Display duplicate-email errors only on signup and generic invalid-credentials errors on login.
- Logout calls the server, then clears cache and navigates to `/login` even if the session already expired.
- No token or user record is written to local storage.

## Dashboard Composition

```text
DashboardPage
  DashboardHeader + Add button
  StatsPanel
    RangeSelect
    SummaryCards
    OpportunityCostList
  EntrySection: Needs check-in
  EntrySection: Waiting
  EntrySection: Saved
  PurchasedDisclosure (collapsed initially)
```

Render arrays exactly as returned by the backend. Each section has an independent empty state. Entry cards show item, formatted price, relevant timestamp, reason, and action. Needs-check-in receives the strongest visual priority. Waiting shows the server-provided `eligible_for_check_in_at`; the UI may render a human-readable time but must not move the item between buckets locally.

Purchased is a semantic `<details>` disclosure, closed on initial render. Preserve its open state only during the mounted dashboard session.

## Entry Flows

### Create and edit

Fields and client constraints:

| Field | Input | Validation |
|---|---|---|
| Item name | text | trimmed, 1–200 characters |
| Price | decimal text/input mode decimal | valid USD, at least $0.01, at most $9,999,999,999.99, max 2 decimals |
| Reason wanted | textarea | trimmed, 1–2000 characters |

Convert price text to cents using string parsing, never binary floating-point multiplication. Reject exponent notation, signs other than an optional leading `+` (prefer rejecting it), commas, and more than two decimal places. Convert cents back to a two-decimal edit string.

On success, show a non-blocking confirmation, invalidate entries, and navigate to `/dashboard`. Prevent duplicate submits while pending. If navigation occurs with unsaved changed values, warn the user.

The detail page shows edit/delete actions only when response `status` is `waiting`; this is convenience, not enforcement. A `409` refreshes detail/dashboard and explains that the entry is no longer editable.

### Delete

Use an accessible confirmation modal naming the item. Keep focus trapped, return focus to the trigger, and require an explicit destructive action. On `204`, invalidate dashboard, remove detail cache, and navigate to dashboard.

### Check-in

The page presents immutable entry details, an optional comment (max 4000 characters), and two explicit submit buttons: “I did not buy it” (`saved`) and “I bought it” (`purchased`). Do not preselect an outcome. Announce success, invalidate dashboard/stats/detail, and return to the dashboard. On `early_check_in` or another conflict, refresh the entry and show the server message.

### Comment update

Saved and purchased detail screens expose only the comment editor. Submit `null` for blank/whitespace-only content. Updating a comment invalidates detail and dashboard but not stats because the calculation is unchanged.

## Statistics and Opportunity Costs

The range select values exactly match the API enum. Default to `this_month`. The selected range may be encoded as `?range=` so refresh/back navigation preserves it; unknown values fall back safely.

- Format `total_saved_cents` with `Intl.NumberFormat('en-US', {style: 'currency', currency: 'USD'})`.
- Display counts with locale number formatting.
- Render `equivalent_units` exactly as returned; do not recalculate.
- Keep previous summary visible with an updating indicator during range changes.

Opportunity-cost settings provide create, edit, and delete forms. Dollar-value parsing uses the same cents utility. Required lengths mirror backend constraints. Delete requires confirmation. Empty state explains how examples affect the dashboard.

## State and Component Rules

- TanStack Query owns server state; form libraries own transient form state; component state owns disclosure/modal state.
- Do not introduce Redux or a global state library for V1.
- Avoid copying query data into component state.
- All lists use stable entity IDs as keys.
- Components receive the narrowest useful typed props and expose event callbacks rather than API knowledge.
- Use an error boundary for unexpected render errors and route error elements for loader/import failures.

## Loading, Error, and Empty States

- First page load uses a labeled skeleton or spinner without layout shift.
- Background refresh retains content and indicates updating.
- Recoverable query errors show a message and retry button.
- Form field errors appear beside their fields and a summary receives focus after failed submission.
- Global network failure never masquerades as an empty list.
- Auth expiration redirects to login with “Your session expired. Please sign in again.”

## Accessibility and Responsive Design

- Meet WCAG 2.2 AA for keyboard operation, semantics, contrast, and focus visibility.
- Use headings in order and landmarks (`header`, `nav`, `main`).
- Every field has a programmatic label, description, and associated error.
- Status messages use an appropriate `aria-live` region without excessive announcements.
- Modals handle focus correctly; prefer native elements such as `<button>` and `<details>`.
- Minimum touch target is 44×44 CSS pixels.
- Mobile layout begins at 320px; cards stack in one column, actions remain reachable, and no horizontal page scrolling occurs.
- At wider breakpoints, stats may form a grid while content retains a readable maximum width.
- Respect reduced-motion preferences.

## Frontend Security

- Render text through React; never inject API HTML.
- Do not put secrets, session values, or sensitive data in URLs or browser storage.
- Use same-origin API requests in production. Development proxy forwards `/api` to FastAPI.
- Treat backend messages as plain text.
- Frontend route guards do not replace backend authorization.

## Testing

Unit tests:

- USD string-to-cents and cents-to-display edge cases.
- UTC timestamp formatting and invalid inputs.
- Query-key helpers and API error parsing.

Component/integration tests with Testing Library and MSW:

- Auth bootstrap, guest/protected redirects, signup/login/logout.
- Every form's field and backend errors, pending state, and success navigation.
- Four dashboard sections without client regrouping.
- Purchased disclosure starts closed and is keyboard usable.
- Check-in sends each exact result and handles `409`.
- Range changes request/cache the correct summary.
- CRUD invalidates the required queries.
- `401`, network failure, empty state, and retry behavior.

Add accessibility assertions with `jest-axe` where useful, but also test keyboard behavior directly. Coverage targets are guidance (80% lines/branches for domain utilities and feature code), not a substitute for behavior-focused cases.

## Build and Acceptance

Required scripts:

```text
npm run dev
npm run build
npm run preview
npm run test
npm run test:coverage
npm run lint
npm run typecheck
npm run format
```

Acceptance requires a production build with no TypeScript errors, green component tests, keyboard-complete primary flows, correct behavior at mobile and desktop widths, and no duplicated backend business calculations.
