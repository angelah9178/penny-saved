# DEV-009 — Implement Authentication UI and Route Guards

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Frontend-to-Backend Login Flow](#frontend-to-backend-login-flow)
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

|             | Commit                                                             | Title                             | Depends on  |
| ----------- | ------------------------------------------------------------------ | --------------------------------- | ----------- |
| &#91;x&#93; | [1](#commit-1--add-frontend-authentication-types-and-api-requests) | Add auth types and API requests   | —           |
| &#91;x&#93; | [2](#commit-2--bootstrap-and-cache-the-current-session)            | Bootstrap the current session     | Commit 1    |
| &#91;x&#93; | [3](#commit-3--add-protected-and-guest-only-route-guards)          | Add route guards                  | Commit 2    |
| &#91;x&#93; | [4](#commit-4--build-accessible-signup-and-login-flows)            | Build signup and login flows      | Commit 3    |
| &#91;x&#93; | [5](#commit-5--add-logout-and-session-expiry-recovery)             | Add logout and expiry recovery    | Commit 4    |
| &#91;x&#93; | [6](#commit-6--complete-auth-ux-security-and-verification)         | Complete auth UX and verification | Commits 1–5 |

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

## Frontend-to-Backend Login Flow

The login process begins in the frontend, but the backend performs the actual
credential comparison. The frontend checks only whether the input has a usable shape;
it cannot determine whether the email exists or whether the password is correct.

The complete successful flow is:

```text
LoginPage renders AuthForm in login mode
    ↓
user enters email and password
    ↓
frontend validates basic email/password shape
    ↓
frontend sends POST /api/auth/login with credentials included
    ↓
backend validates and normalizes the request schema
    ↓
backend looks up the normalized email in PostgreSQL
    ↓
backend verifies the entered password against the stored Argon2id hash
    ↓
backend creates and commits a server-side session
    ↓
backend sets the raw session token in an HttpOnly cookie
    ↓
backend returns only the public user ID and normalized email
    ↓
frontend writes the public user into the in-memory auth query cache
    ↓
frontend safely navigates to the requested protected page or /dashboard
```

### 1. Render and collect the credentials

[`frontend/src/pages/LoginPage.tsx`](../frontend/src/pages/LoginPage.tsx) renders:

```tsx
<AuthForm mode="login" />
```

[`frontend/src/features/auth/AuthForm.tsx`](../frontend/src/features/auth/AuthForm.tsx)
owns the email and password inputs through React Hook Form. When submitted, it passes the values to
`authFormSchema.safeParse(...)`.

### 2. Perform frontend usability validation

[`frontend/src/features/auth/validation.ts`](../frontend/src/features/auth/validation.ts)
trims the email and checks its basic shape and 3–320 character boundary. It checks that
the password contains 8–128 Unicode characters without trimming, lowercasing,
truncating, or otherwise modifying it.

These are usability checks only:

```text
frontend can answer: “Is this shaped like acceptable input?”
frontend cannot answer: “Does this password belong to this account?”
```

If the basic checks fail, `AuthForm` displays associated field errors and does not send
a request.

### 3. Send the login API request

For a valid form, the login-mode TanStack mutation calls `login(...)` from
[`frontend/src/features/auth/api.ts`](../frontend/src/features/auth/api.ts):

```tsx
export function login(credentials: AuthRequest): Promise<AuthResponse> {
  return apiFetch<AuthResponse>("/auth/login", {
    method: "POST",
    body: credentials,
  });
}
```

[`frontend/src/api/client.ts`](../frontend/src/api/client.ts) turns that into
`POST /api/auth/login`, serializes the credentials as JSON, and uses
`credentials: "include"` so the browser can accept and later send the session cookie.

### 4. Validate the backend request

[`backend/app/api/routes/auth.py`](../backend/app/api/routes/auth.py) receives the
request as the backend `AuthRequest` schema. The schema in
[`backend/app/schemas/auth.py`](../backend/app/schemas/auth.py) normalizes the email
consistently, enforces the backend email/password rules, rejects unknown properties,
and keeps the password wrapped as a secret value.

The route then calls the `login(...)` service. The route itself does not query the
database or compare passwords.

### 5. Look up the account and verify the password

The actual credential check happens in
[`backend/app/services/auth.py`](../backend/app/services/auth.py):

```python
user = await get_user_by_email(db, credentials.email)
password = credentials.password.get_secret_value()
password_hash = user.password_hash if user is not None else DUMMY_PASSWORD_HASH
valid, replacement_hash = verify_and_update_password(password, password_hash)

if user is None or not valid:
    raise _invalid_credentials_error()
```

`get_user_by_email(...)` in
[`backend/app/repositories/users.py`](../backend/app/repositories/users.py) queries
PostgreSQL using the normalized email. The database stores an Argon2id password hash
rather than the plaintext password.

`verify_and_update_password(...)` in
[`backend/app/core/security.py`](../backend/app/core/security.py) performs the
cryptographic comparison:

```python
_PASSWORD_HASH.verify_and_update(password, password_hash)
```

A missing account is checked against a fixed dummy Argon2id hash so it follows the same
expensive verification path as an incorrect password. Missing email and wrong password
therefore return the same generic `invalid_credentials` response and do not disclose
which value was incorrect.

### 6. Create the session and return the public user

After successful verification, the login service stages a new session and commits the
transaction. PostgreSQL stores only the SHA-256 digest of the random session token.
[`backend/app/api/routes/auth.py`](../backend/app/api/routes/auth.py) places the raw
token in the configured `HttpOnly`, `SameSite=Lax` cookie and returns:

```json
{
  "user": {
    "id": "user-id",
    "email": "person@example.com"
  }
}
```

The password, password hash, raw session token, and token digest are not included in
the response.

### 7. Update frontend authentication state

Back in
[`frontend/src/features/auth/AuthForm.tsx`](../frontend/src/features/auth/AuthForm.tsx),
a successful response is written to `queryKeys.auth.me()` in TanStack Query's in-memory
cache. The form clears its transient password state, resets any previous expiry event,
and replace-navigates through the safe return-path validator.

If the backend rejects the credentials,
[`frontend/src/api/errors.ts`](../frontend/src/api/errors.ts) converts the standard
error envelope into `ApiError`. The login form displays the generic “The email or
password is incorrect” message and remains on `/login`.

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

**Status:** Complete.

Commit 2 makes `/auth/me` the only source of truth for the initial browser
authentication state. A missing, invalid, or expired session is a normal guest result;
a network or server failure is not. The latter must offer recovery instead of silently
pretending the user is signed out.

In plain language, **bootstrap authentication** means initializing the frontend's
authentication state when the application first opens or refreshes. JavaScript cannot
read the secure `HttpOnly` session cookie directly, so the frontend asks the backend
whether the browser's automatically supplied cookie represents a valid session:

Commit 2 therefore determines whether the browser already has a valid login session
when the application first loads. If the session is still valid, the user does not
have to go through login every time they open or refresh the application. This does not
bypass authentication: the backend validates the existing session before the frontend
treats the user as logged in. If the session is missing, invalid, or expired, the user
must log in again.

```text
browser opens Penny Saved
    ↓
frontend calls GET /api/auth/me
    ↓
browser automatically sends the HttpOnly session cookie
    ↓
backend validates the session and returns the public user or 401
```

This answers one question before the application chooses what to show: “Has this
browser already logged in, and is that session still valid?” The neutral pending state
prevents authentication flicker:

```text
incorrect: refresh → login page flashes → session found → dashboard
correct:   refresh → neutral loading state → session found → dashboard
```

Commit 2 does not decide route redirects; Commit 3 owns those rules. It provides one
reliable, shared session result that every later route guard and authentication control
can use.

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

**Status:** Complete.

Commit 3 decides which pages a user may see based on the authentication result from
Commit 2. It adds two kinds of navigation gates:

- **Protected routes** require the user to be logged in, such as `/dashboard`.
- **Guest-only routes** are intended for logged-out users, such as `/login` and
  `/signup`.

In plain language, the behavior is:

```text
logged-in user opens /dashboard  → show the dashboard
logged-out user opens /dashboard → send them to /login
logged-out user opens /login     → show the login page
logged-in user opens /login      → send them to /dashboard
```

The guards wait until the session check from Commit 2 finishes. This prevents the
application from redirecting someone while it is still determining whether their
existing session is valid. Redirects use replacement navigation so the browser Back
button does not bounce between a route and the guard that rejected it.

Route outcomes are:

| Current state   | Guest route (`/login`, `/signup`) | Protected route (`/dashboard`) |
| --------------- | --------------------------------- | ------------------------------ |
| Pending         | Auth loading view                 | Auth loading view              |
| Authenticated   | Redirect to safe destination      | Render child route             |
| Guest           | Render child route                | Redirect to `/login`           |
| Bootstrap error | Retryable error view              | Retryable error view           |

When a logged-out user asks for a protected page, Commit 3 remembers where they
originally wanted to go:

```text
user opens /entries/new
    ↓
no valid session, so redirect to /login
    ↓
user logs in
    ↓
return safely to /entries/new
```

That return location must be a safe internal Penny Saved path. It must never permit an
absolute URL, protocol-relative URL, foreign origin, executable scheme, malformed
value, or login/signup redirect loop.

This commit also makes `/` choose `/dashboard` or `/login`, adds the guest-only login
and signup routes, adds a small protected dashboard placeholder for DEV-011 to replace,
and preserves the not-found page.

Most importantly, route guards are a frontend navigation convenience rather than the
security boundary. They prevent inappropriate screens from being displayed
accidentally, but the backend must still validate the session and authorize every
protected API request.

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

**Status:** Complete.

Commit 4 adds the two guest forms and reconciles successful authentication directly
into the existing current-user cache. Both forms use React Hook Form and Zod for
immediate usability feedback, while DEV-008 remains authoritative for normalization,
validation, duplicate email detection, and credential verification.

In plain language, Commit 4 builds the actual signup and login forms. The signup form
asks for:

```text
Email
Password
Create account
```

The login form asks for:

```text
Email
Password
Log in
```

Before either form contacts the backend, the frontend performs basic checks so it can
quickly identify a missing or malformed email and a password that is too short or too
long. These checks make the form easier to use, but they do not decide whether an
account may be created or whether credentials are correct. The backend remains the
authority and performs the final validation, account lookup, password verification,
and session creation.

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

**Status:** Complete.

Commit 5 completes the session lifecycle after initial authentication. Logout calls
the server, clears the entire TanStack Query cache, and replace-navigates to `/login`.
The local cleanup and navigation must occur even when the server reports an already
expired session or the logout request fails, because the browser must not continue to
present stale private data as authenticated.

In plain language, Commit 5 gives users a reliable way to log out and handles sessions
that become invalid while the application is open. The protected application header
shows the logged-in user's email and a Logout button.

Intentional logout follows this flow:

```text
user selects Logout
    ↓
frontend calls POST /api/auth/logout
    ↓
backend deletes the active session and clears its cookie
    ↓
frontend clears all cached account data
    ↓
user is sent to /login
```

Clearing the entire frontend cache prevents entries, statistics, settings, or other
private data from the previous account appearing if another person later logs in on
the same browser. The frontend still clears its cache and goes to `/login` when the
session already expired, the logout request is unauthorized, the network fails, or the
server temporarily fails. Repeated Logout clicks produce only one active request.

A session can also expire while the application remains open:

```text
user leaves the application open
    ↓
the server-side session expires
    ↓
the user later requests protected data
    ↓
the backend returns 401 Unauthorized
```

In that situation, the frontend clears cached authentication and account data,
redirects to `/login`, remembers the safe internal page the user was visiting, and
displays “Your session expired. Please sign in again.” After a successful login, the
user returns safely to that page:

```text
session expires on /entries/new
    ↓
redirect to /login with the expiration message
    ↓
user logs in again
    ↓
return safely to /entries/new
```

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
coordination decides which `401` is an expired authenticated session. If several
protected requests return `401` together, they are handled as one expiration event
rather than repeatedly clearing the cache, redirecting, or showing duplicate messages.

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

**Status:** Complete.

Commit 6 verifies the feature as a complete browser workflow and closes usability,
accessibility, responsive, and documentation gaps. It must validate behavior at the
HTTP and router boundaries rather than merely recording planned coverage.

In plain language, Commits 1–5 build the authentication functionality, while Commit 6
checks that everything works together as a secure, accessible, responsive browser
experience. It tests the complete user journey:

```text
create an account
    ↓
reach the protected dashboard
    ↓
refresh and restore the existing session
    ↓
log out
    ↓
request protected content and return to login
```

It also proves that a guest who originally requested a protected page can log in and
return safely to that page. The review covers keyboard and assistive-technology use,
visible focus, labels and error associations, loading announcements, 44×44 pixel
targets, reduced motion, and layouts down to 320 CSS pixels without horizontal page
scrolling.

Commit 6 reviews the security boundaries to confirm that passwords remain only in
temporary form state and the request body, raw session tokens remain only in
browser-managed `HttpOnly` cookies, public user data remains only in the in-memory
query cache, and return paths remain validated internal routes. It also updates the
project documentation and replaces the planned Implementation Record with actual
files, commands, test counts, and remaining limitations.

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

### Overview

DEV-009 added the complete browser authentication experience on top of the DEV-008
cookie-session API. The frontend now provides typed auth requests, current-session
bootstrap, protected and guest-only route guards, accessible signup and login forms,
logout, expired-session recovery, safe return navigation, and a protected dashboard
placeholder for DEV-011.

### What It Achieved

Users can create an account, log in, refresh without losing a valid session, log out,
and recover safely when a protected request discovers an expired session. TanStack
Query owns the public user as in-memory server state. React Hook Form and Zod provide
immediate form feedback while the backend remains authoritative for validation,
credential verification, session creation, and authorization.

Signup and login reconcile the returned public user directly into the current-session
cache before replace-navigation, avoiding a redundant `/auth/me` request. Logout
revokes the presented server session when reachable, clears private frontend query
data for every outcome, records a guest cache state, and navigates to `/login`.

### Routes and Session Behavior

`/` resolves to `/dashboard` for an authenticated user and `/login` for a guest.
`/login` and `/signup` are guest-only, while `/dashboard` is protected. All decisions
wait for `/api/auth/me`, so a valid refreshed session does not flash the login screen
and a guest does not see protected content. Network and server bootstrap failures show
a focused retry state rather than masquerading as logout.

Protected redirects preserve the path, query, and fragment in router state. Only
validated internal paths are accepted; absolute URLs, protocol-relative URLs,
backslashes, malformed or repeatedly encoded paths, control characters, and auth-route
loops fall back to `/dashboard`. Concurrent protected-request `401` responses converge
into one cache clear, redirect, and expiry message. Bootstrap and invalid-login `401`
responses do not enter this expiry flow.

### Accessibility and Security

Signup and login have visible programmatic labels, correct autocomplete values,
associated field errors, keyboard submission, disabled pending actions, and focused
global error summaries. Loading, expiry, and failure states use live status or alert
semantics. Shared controls retain visible focus and minimum 44×44 CSS pixel targets.
The layout supports a 320 CSS pixel viewport with bounded content, wrapping header
controls, full-width shrinkable inputs, and reduced-motion behavior.

Passwords remain in transient form state and credential request bodies, are preserved
exactly as entered, and are cleared after success or unmount. The frontend neither
reads the `HttpOnly` cookie nor writes passwords, session values, or public users to
local/session storage or URLs. API messages render through React as plain text.
Return-path validation prevents external post-login navigation. Route guards remain a
navigation convenience; backend authentication and authorization remain mandatory.

### Verification

The completed verification ran:

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

The clean locked installation completed successfully. `make check` passed formatting,
ESLint, strict TypeScript, 135 frontend tests, 232 backend tests using the explicit
PostgreSQL test database, frontend production build, and backend construction. The
frontend suite includes complete MSW-backed signup → dashboard → refresh restoration →
logout → protected redirect and protected route → login → safe return flows.

Coverage completed at 96.63% statements, 94% branches, 97.64% functions, and 96.58%
lines overall. Authentication feature coverage was 96.77% statements, 92.15% branches,
100% functions, and 96.71% lines. The production build emitted separate lazy chunks
for login, signup, dashboard, and the shared authentication form. Markdown/Prettier
formatting and `git diff --check` passed.

### Limitations and Follow-up

DEV-011 will replace the temporary protected dashboard destination with the complete
dashboard and entry lists. DEV-020 will complete shared application-wide UX,
accessibility, and responsive hardening. DEV-021 will add production authentication
rate limiting and remaining abuse protections, and DEV-023 will add live end-to-end
smoke coverage against a real browser and backend. Commit 6 used behavior-focused
Testing Library/MSW integration coverage rather than the live-browser suite owned by
DEV-023.

The locked frontend installation reported seven high-severity dependency audit
findings. No dependency versions were changed within DEV-009; they require a separate
review of available compatible upgrades rather than an automatic breaking
`npm audit fix --force`.
