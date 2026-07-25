# DEV-009 — Implement Authentication UI and Route Guards

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Commit 1 — Add Frontend Authentication Types and API Requests](#commit-1--add-frontend-authentication-types-and-api-requests)
- [Commit 2 — Bootstrap and Cache the Current Session](#commit-2--bootstrap-and-cache-the-current-session)
- [Commit 3 — Add Protected and Guest-Only Route Guards](#commit-3--add-protected-and-guest-only-route-guards)
- [Commit 4 — Build Accessible Signup and Login Flows](#commit-4--build-accessible-signup-and-login-flows)
- [Commit 5 — Add Logout and Session-Expiry Recovery](#commit-5--add-logout-and-session-expiry-recovery)
- [Commit 6 — Complete Auth UX, Security, and Verification](#commit-6--complete-auth-ux-security-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)
  - [Overview](#overview)
  - [What It Achieved](#what-it-achieved)
  - [Routes and Session Behavior](#routes-and-session-behavior)
  - [Accessibility and Security](#accessibility-and-security)
  - [Verification](#verification)
  - [Limitations and Follow-up](#limitations-and-follow-up)

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are
complete.

|                  | Commit                                                             | Title                             | Depends on  |
| ---------------- | ------------------------------------------------------------------ | --------------------------------- | ----------- |
| &#91;x&#93;      | [1](#commit-1--add-frontend-authentication-types-and-api-requests) | Add auth types and API requests   | —           |
| &#91;&#160;&#93; | [2](#commit-2--bootstrap-and-cache-the-current-session)            | Bootstrap the current session     | Commit 1    |
| &#91;&#160;&#93; | [3](#commit-3--add-protected-and-guest-only-route-guards)          | Add route guards                  | Commit 2    |
| &#91;&#160;&#93; | [4](#commit-4--build-accessible-signup-and-login-flows)            | Build signup and login flows      | Commit 3    |
| &#91;&#160;&#93; | [5](#commit-5--add-logout-and-session-expiry-recovery)             | Add logout and expiry recovery    | Commit 4    |
| &#91;&#160;&#93; | [6](#commit-6--complete-auth-ux-security-and-verification)         | Complete auth UX and verification | Commits 1–5 |

## Objective

Implement the browser-facing account boundary on top of the DEV-008 authentication
API. DEV-009 adds signup, login, session restoration, logout, and route access behavior
without storing passwords or session tokens in JavaScript-readable browser storage:

```text
initial page load
    ↓
GET /api/auth/me with the HttpOnly cookie
    ↓
authenticated → render or redirect to protected content
guest         → render or redirect to login/signup
```

The frontend must wait for this bootstrap request before deciding whether a route is
available. This prevents a valid refreshed session from briefly seeing the login page
and prevents guest users from briefly seeing protected content. React route guards
improve navigation and presentation only; the backend remains responsible for
authorization and ownership.

The route boundary introduced by this task is:

| Route        | Access    | DEV-009 behavior                                     |
| ------------ | --------- | ---------------------------------------------------- |
| `/`          | Public    | Redirect based on the resolved authentication state  |
| `/signup`    | Guest     | Render signup or redirect an authenticated user      |
| `/login`     | Guest     | Render login or redirect an authenticated user       |
| `/dashboard` | Protected | Render the temporary protected destination or log in |
| `*`          | Any       | Preserve the not-found route                         |

DEV-011 owns the complete dashboard. Until then, DEV-009 may use a small authenticated
landing page at `/dashboard` that proves the guard, current-user display, and logout
flow without implementing entries or statistics.

Complete and commit each section in order. Every commit must preserve `make check`.
Component and router tests must use MSW at the HTTP boundary and assert user-observable
behavior rather than component implementation details.

## Commit 1 — Add Frontend Authentication Types and API Requests

**Status:** Complete.

Commit 1 establishes one typed frontend boundary for all four DEV-008 endpoints before
pages or route guards depend on them. TanStack Query owns the authenticated user as
server state; no parallel auth store, context copy, or browser-storage record is
introduced.

In plain language, the authentication types define the data exchanged with the
backend. Signup and login send an email and password, while a successful authentication
response contains only the public user ID and email. The API request functions perform
the actual `signup`, `login`, `getCurrentUser`, and `logout` HTTP requests.

These frontend types and functions do not decide whether a user is allowed to log in.
The backend remains responsible for account lookup, password verification, session
creation, and the final validation rules. The frontend checks only the basic input
shape for helpful feedback, sends credentials securely, interprets the backend
response, and updates the displayed authentication state.

The operations are:

```text
POST /auth/signup  ← normalized email + password
POST /auth/login   ← normalized email + password
GET  /auth/me      → current public user
POST /auth/logout  → no response data required by the UI
```

All requests must use the shared `apiFetch` client so `credentials: "include"`,
standard error parsing, base URL behavior, and abort signals remain consistent.
Successful responses expose only the public `User` shape. The frontend must never
model, inspect, or attempt to read the `HttpOnly` cookie.

Suggested commit message:

```text
Add frontend authentication API operations
```

Implement:

- Confirm the existing `User`, `AuthRequest`, and `AuthResponse` types exactly match
  the DEV-008 public schemas; add a logout response type only if the API returns JSON.
- Add focused signup, login, current-user, and logout API functions under
  `frontend/src/features/auth/`.
- Keep endpoint strings and response parsing out of page components.
- Pass the TanStack Query `AbortSignal` through the current-user request.
- Add an auth query-options factory using `queryKeys.auth.me()`, a five-minute
  `staleTime`, and no retry for `401`.
- Allow at most two backoff retries for retryable network and `5xx` bootstrap failures.
- Do not retry auth mutations or any `4xx` response.
- Add unit tests for method, path, payload, credentials inherited from `apiFetch`,
  successful public-user parsing, abort propagation, and standard API errors.
- Add negative tests proving the auth layer does not use `localStorage`,
  `sessionStorage`, cookies, console logging, or token-shaped response fields.

Commit gate:

```text
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run test -- src/features/auth
cd ..
make check
git diff --check
```

## Commit 2 — Bootstrap and Cache the Current Session

Commit 2 makes `/auth/me` the only source of truth for the initial browser
authentication state. A missing, invalid, or expired session is a normal guest result;
a network or server failure is not. The latter must offer recovery instead of silently
pretending the user is signed out.

The state model is:

```text
pending             → neutral full-page auth loading state
success with user   → authenticated
401                 → guest
network/5xx failure → recoverable bootstrap error with retry
```

The bootstrap must run high enough in the application tree that the index route,
guest-only routes, protected routes, and logout control all observe the same query
cache entry. Do not copy the returned user into component state or a second global
store.

Suggested commit message:

```text
Bootstrap authentication from the current session
```

Implement:

- Add a focused auth-session hook that reads `queryKeys.auth.me()` and represents the
  four states above without losing the original query controls.
- Convert only an `/auth/me` `401` into the expected guest state.
- Keep network, invalid-response, and `5xx` errors visible as bootstrap failures.
- Add a stable, labeled loading view that does not reveal either guest or protected
  content while the request is pending.
- Add a recoverable error view with a retry button and appropriate focus behavior.
- Ensure one bootstrap request is shared across consumers during a render/navigation.
- Preserve the configured five-minute freshness behavior while allowing explicit
  invalidation after auth mutations.
- Add MSW-backed tests for authenticated bootstrap, guest bootstrap, delayed response,
  network failure, `5xx`, retry success, and request cancellation.
- Prove a valid refreshed session reaches authenticated content without rendering the
  login page first.

Commit gate:

```text
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run test -- src/features/auth
cd ..
make check
git diff --check
```

## Commit 3 — Add Protected and Guest-Only Route Guards

Commit 3 connects the resolved session state to React Router. Guard decisions happen
only after bootstrap settles. Redirects use replacement navigation so the browser Back
button does not bounce between a route and the guard that rejected it.

Route outcomes are:

| Current state   | Guest route (`/login`, `/signup`) | Protected route (`/dashboard`) |
| --------------- | --------------------------------- | ------------------------------ |
| Pending         | Auth loading view                 | Auth loading view              |
| Authenticated   | Redirect to safe destination      | Render child route             |
| Guest           | Render child route                | Redirect to `/login`           |
| Bootstrap error | Retryable error view              | Retryable error view           |

When a guest is redirected from a protected route, preserve only an internal path as
the intended return destination. The value may come from router state or a validated
query parameter, but it must never permit an absolute URL, protocol-relative URL,
foreign origin, executable scheme, or login/signup redirect loop.

Suggested commit message:

```text
Add authentication route guards
```

Implement:

- Add focused `ProtectedRoute` and `GuestRoute` components under `frontend/src/routes`.
- Add a safe-return-path helper that accepts only intended internal application paths
  and falls back to `/dashboard`.
- Make `/` redirect to `/dashboard` for authenticated users and `/login` for guests
  only after bootstrap resolves.
- Add lazy guest routes for `/login` and `/signup`.
- Add the protected `/dashboard` route with a minimal authenticated placeholder until
  DEV-011 replaces it.
- Keep the wildcard not-found route reachable without requiring authentication.
- Use replacement navigation for all guard redirects.
- Ensure direct navigation, refresh, Back/Forward navigation, and nested route state
  use the same guard rules.
- Add router tests for every row of the outcome table and both index-route outcomes.
- Add malicious redirect tests covering external URLs, `//` URLs, encoded variants,
  auth-route loops, and malformed values.
- State in code comments or route documentation that these guards do not replace
  backend authorization.

Commit gate:

```text
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run test -- src/routes src/features/auth
npm run build
cd ..
make check
git diff --check
```

## Commit 4 — Build Accessible Signup and Login Flows

Commit 4 adds the two guest forms and reconciles successful authentication directly
into the existing current-user cache. Both forms use React Hook Form and Zod for
immediate usability feedback, while DEV-008 remains authoritative for normalization,
validation, duplicate email detection, and credential verification.

Shared input behavior:

- Email has a visible programmatic label and `autocomplete="email"`.
- Signup uses `autocomplete="new-password"`; login uses
  `autocomplete="current-password"`.
- Email is trimmed for submission, while the password is sent exactly as entered.
- Client validation mirrors the documented 3–320 character email and 8–128 Unicode
  character password boundaries without lowercasing or mutating passwords.
- Unknown backend field keys remain safe and are presented through the global error
  summary rather than attached to an unrelated input.
- Submit is disabled while pending and duplicate submission produces one request.

Error mapping is deliberately contextual:

| API result                  | Signup presentation                | Login presentation          |
| --------------------------- | ---------------------------------- | --------------------------- |
| `422` with known fields     | Associated field messages          | Associated field messages   |
| `duplicate_email` `409`     | Email-associated duplicate message | Generic safe failure        |
| `invalid_credentials` `401` | Generic safe failure               | Generic credentials message |
| Network or `5xx`            | Retryable global message           | Retryable global message    |

After a successful signup or login, write the returned public user into
`queryKeys.auth.me()`, remove obsolete auth errors, and replace-navigate to the
validated return path or `/dashboard`. Do not issue a redundant `/auth/me` request
before navigation.

Suggested commit message:

```text
Build signup and login flows
```

Implement:

- Add shared auth validation and form-field primitives without merging the distinct
  signup and login error semantics.
- Build lazy `SignupPage` and `LoginPage` route modules with concise reciprocal links.
- Render field errors beside their inputs and connect labels, descriptions, and errors
  with stable IDs and ARIA attributes.
- Add a global error summary or alert for non-field failures and focus it after a
  failed submission.
- Preserve passwords only in transient form state; clear them when the form unmounts
  or authentication succeeds.
- Prevent duplicate requests while a mutation is pending and expose the pending state
  in the button text or an accessible status.
- Reconcile a successful `AuthResponse.user` into the current-user query cache before
  protected navigation.
- Use the safe-return-path helper for post-auth navigation.
- Add MSW-backed tests for client validation, exact trimmed-email/unmodified-password
  payloads, successful signup/login, duplicate email, invalid credentials, backend
  field errors, network/`5xx` errors, focus movement, keyboard submission, and
  duplicate-submit prevention.
- Verify password input values and request payloads never appear in rendered error
  output, URLs, browser storage, or console calls.

Commit gate:

```text
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run test -- src/features/auth src/routes
npm run build
cd ..
make check
git diff --check
```

## Commit 5 — Add Logout and Session-Expiry Recovery

Commit 5 completes the session lifecycle after initial authentication. Logout calls
the server, clears the entire TanStack Query cache, and replace-navigates to `/login`.
The local cleanup and navigation must occur even when the server reports an already
expired session or the logout request fails, because the browser must not continue to
present stale private data as authenticated.

Unexpected `401` responses from protected application requests represent session
expiry. They must converge through one handler:

```text
protected request returns 401
    ↓
clear auth-dependent cached data
    ↓
replace-navigate to /login with a validated internal return path
    ↓
announce “Your session expired. Please sign in again.”
```

Expected `401` responses from `/auth/me` bootstrap and invalid login must not trigger
the expiry flow. The API layer should report typed errors; navigation-aware auth
coordination decides which `401` is an expired authenticated session.

Suggested commit message:

```text
Add logout and session expiry recovery
```

Implement:

- Add an authenticated header or account control showing the public user email and a
  semantic logout button.
- Add a logout mutation that calls DEV-008 and performs local cleanup in a settled
  path for success, expired session, network failure, and `5xx`.
- Clear the entire query cache on logout so later feature caches cannot leak between
  accounts.
- Replace-navigate to `/login`; do not preserve a return path for intentional logout.
- Disable repeated logout activation while the request is pending.
- Add a single navigation-aware protected-request `401` coordinator without coupling
  the low-level API client to React hooks.
- Preserve a validated return path for unexpected session expiry and display the
  approved expiry message once on the login page.
- Avoid redirect loops, duplicate notifications, and repeated cache clearing when
  concurrent protected requests all return `401`.
- Add tests for successful logout, idempotent/expired logout, network/`5xx` logout,
  cache clearing, navigation replacement, and duplicate-click prevention.
- Add tests distinguishing bootstrap `401`, invalid-login `401`, and protected-request
  expiry, including concurrent `401` responses and safe return navigation after login.

Commit gate:

```text
cd frontend
npm run format:check
npm run lint
npm run typecheck
npm run test -- src/features/auth src/routes src/api
npm run build
cd ..
make check
git diff --check
```

## Commit 6 — Complete Auth UX, Security, and Verification

Commit 6 verifies the feature as a complete browser workflow and closes usability,
accessibility, responsive, and documentation gaps. It must validate behavior at the
HTTP and router boundaries rather than merely recording planned coverage.

The final verification must demonstrate:

```text
password          → transient form state and HTTPS request body only
raw session token → HttpOnly cookie managed by the browser only
public user       → TanStack Query memory cache only
return path       → validated same-application route only
```

Suggested commit message:

```text
Complete authentication UI and route guards
```

Implement:

- Ensure auth pages work at a 320px viewport without horizontal page scrolling and
  retain readable line lengths at wider sizes.
- Confirm visible focus, logical heading order, landmarks, 44×44 CSS pixel interactive
  targets, reduced-motion behavior, and sufficient loading/error status semantics.
- Verify keyboard-only use for navigation, form correction, submission, retry, and
  logout.
- Keep layout stable while auth bootstrap is pending and prevent protected or guest
  content from flashing in the wrong state.
- Confirm API-provided text is rendered as text and no auth component uses injected
  HTML.
- Confirm no password, cookie, session value, or auth response is written to
  local/session storage, a URL, analytics, or logs.
- Update the root/frontend documentation with the signup, login, refresh restoration,
  logout, demo-login, and protected-route behavior.
- Add a complete MSW-backed router integration flow for signup → dashboard → refresh
  restoration → logout → protected redirect and login → intended protected route.
- Add accessibility assertions where useful, backed by direct semantic, focus, and
  keyboard behavior tests.
- Run the complete frontend and root quality gates.
- Fill in the Implementation Record below with actual files, commands, counts, and
  remaining limitations; do not mark work complete based on planned verification.

Commit gate:

```text
make clean
make install
make check
cd frontend
npm run test:coverage
npm run build
cd ..
git diff --check
git status --short
```

## Out of Scope

- Backend authentication schemas, persistence, cookie issuance, session resolution,
  origin enforcement, and endpoint authorization; DEV-008 owns these.
- The complete dashboard, entry lists, entry forms, check-in experience, statistics,
  and opportunity-cost settings; DEV-010 onward own those features.
- Treating frontend guards as a security or authorization boundary.
- Storing tokens, cookies, passwords, or persistent user records in local storage,
  session storage, IndexedDB, URLs, service-worker caches, or application logs.
- Password reset, email verification, email delivery, social login, passkeys,
  multi-factor authentication, account deletion, and profile management.
- “Remember me,” all-device logout, session-management screens, or client-controlled
  session expiry.
- Production rate limiting and broader abuse protections; DEV-021 owns those.
- Full browser end-to-end coverage against a live backend; DEV-023 owns the release
  smoke suite. DEV-009 uses router/component integration tests with MSW.

## Implementation Record

Complete this section during Commit 6 with verified results.

### Overview

Not implemented yet.

### What It Achieved

Not implemented yet.

### Routes and Session Behavior

Not implemented yet.

### Accessibility and Security

Not implemented yet.

### Verification

Not run yet.

### Limitations and Follow-up

DEV-011 will replace the temporary protected dashboard destination with the complete
dashboard and entry lists. DEV-020 will complete shared application-wide UX,
accessibility, and responsive hardening. DEV-021 will add production authentication
rate limiting and remaining abuse protections, and DEV-023 will add live end-to-end
smoke coverage.
