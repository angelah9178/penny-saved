# DEV-008 — Implement Authentication and Session API

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Commit 1 — Define Authentication Contracts and Security Primitives](#commit-1--define-authentication-contracts-and-security-primitives)
- [Commit 2 — Add Session Persistence and Lifecycle Services](#commit-2--add-session-persistence-and-lifecycle-services)
- [Commit 3 — Implement Signup and Concurrent Duplicate Protection](#commit-3--implement-signup-and-concurrent-duplicate-protection)
- [Commit 4 — Implement Login and Credential Verification](#commit-4--implement-login-and-credential-verification)
- [Commit 5 — Add Session Resolution, Current User, and Logout](#commit-5--add-session-resolution-current-user-and-logout)
- [Commit 6 — Complete Browser Security, Documentation, and Verification](#commit-6--complete-browser-security-documentation-and-verification)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)
  - [Overview](#overview)
  - [What It Achieved](#what-it-achieved)
  - [API and Session Behavior](#api-and-session-behavior)
  - [Security and Privacy](#security-and-privacy)
  - [Verification](#verification)
  - [Limitations and Follow-up](#limitations-and-follow-up)

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|                  | Commit                                                                   | Title                                    | Depends on  |
| ---------------- | ------------------------------------------------------------------------ | ---------------------------------------- | ----------- |
| &#91;x&#93;      | [1](#commit-1--define-authentication-contracts-and-security-primitives)  | Define auth contracts and primitives     | —           |
| &#91;x&#93;      | [2](#commit-2--add-session-persistence-and-lifecycle-services)           | Add session lifecycle services           | Commit 1    |
| &#91;x&#93;      | [3](#commit-3--implement-signup-and-concurrent-duplicate-protection)     | Implement signup                         | Commit 2    |
| &#91;x&#93;      | [4](#commit-4--implement-login-and-credential-verification)              | Implement login                          | Commit 3    |
| &#91;x&#93;      | [5](#commit-5--add-session-resolution-current-user-and-logout)           | Add current-user resolution and logout   | Commit 4    |
| &#91;&#160;&#93; | [6](#commit-6--complete-browser-security-documentation-and-verification) | Complete auth security and documentation | Commits 1–5 |

## Objective

Implement the backend account boundary used by every protected product feature. DEV-008
adds signup, login, logout, and current-user endpoints backed by revocable PostgreSQL
sessions:

```text
POST /api/auth/signup  → create user + session + cookie
POST /api/auth/login   → verify password + session + cookie
GET  /api/auth/me      → resolve cookie + return current user
POST /api/auth/logout  → revoke session + clear cookie
```

The browser receives one opaque random token in an `HttpOnly` cookie. PostgreSQL stores
only its SHA-256 digest. Passwords are hashed with Argon2id, invalid login attempts do
not disclose whether an email exists, and session expiry is absolute rather than
sliding.

The completed request path is:

```text
credential or cookie input
    ↓
strict schema and normalization
    ↓
repository lookup inside a service-owned transaction
    ↓
password or session verification
    ↓
standard response or safe error envelope
```

Complete and commit each section in order. Every commit must preserve `make check`.
Database integration tests must use only the explicit disposable `TEST_DATABASE_URL`,
and time-sensitive tests must inject a fixed UTC clock rather than sleep or depend on
wall-clock time.

## Commit 1 — Define Authentication Contracts and Security Primitives

**Status:** Complete.

Commit 1 establishes the types and cryptographic helpers used by every later auth
operation. Keeping these rules in one place prevents signup, login, and session
resolution from developing subtly different normalization or token behavior.

In plain language, this commit establishes the authentication rules before building
the endpoints that use them. It defines what a user may enter, what the backend must
reject, what an authenticated user response may contain, and how passwords and session
tokens must be protected. This application uses an email address as the account
identifier rather than a separate username.

For example, these rules decide:

- What counts as a valid email and how it is normalized.
- The allowed password length and which invalid inputs are rejected.
- Which fields signup and login accept.
- Which user fields are safe to return to the frontend.
- How passwords are securely hashed and verified.
- How session tokens are securely generated and prepared for database storage.

Commit 1 does not create signup or login behavior by itself. It creates one consistent
set of validation contracts and security utilities that the later endpoint commits
must follow.

### Email Rules

- Email is the account identifier; the application does not use a separate username.
- Input must be a string between 3 and 320 characters.
- Leading and trailing whitespace is removed.
- Uppercase letters are converted to lowercase.
- The normalized value must contain exactly one `@`.
- Text is required before and after the `@`.
- Whitespace is not allowed inside the normalized email.
- The same normalized value must be used for both database storage and account lookup.

For example:

```text
Input:      "  Person@Example.COM  "
Normalized: "person@example.com"
```

### Password Rules

- Input must be a string containing 8–128 Unicode characters.
- Leading and trailing whitespace is preserved because it may intentionally be part of
  the password.
- Passwords are not trimmed, lowercased, otherwise normalized, or silently truncated.
- Unknown request fields such as `username`, `role`, or `is_admin` are rejected.
- Plaintext passwords must never appear in an API response, log, validation error, or
  database column.
- Passwords must be hashed with the shared Argon2id primitive before persistence.
- Successful verification may replace an existing hash when its Argon2 parameters are
  outdated.

The public JSON contracts are:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

```json
{
  "user": {
    "id": "user_id",
    "email": "user@example.com"
  }
}
```

Auth inputs must forbid unknown properties. Email is stripped and lowercased before
lookup or persistence. Passwords accept 8–128 Unicode characters and must never be
trimmed, truncated, returned, or logged. Responses expose only the user identifier and
normalized email.

DEV-007 already introduced shared password hashing for the demo identity. Extend that
primitive rather than adding a second hasher or auth-only hash format. Successful login
must be able to detect and replace hashes whose Argon2 parameters are outdated.

Session token construction follows one exact boundary:

```text
secrets.token_urlsafe(32) → raw browser token
SHA-256(raw token)        → 64-character lowercase database digest
```

Tests may inject token generation, but production code must use a cryptographically
secure generator. The raw value and digest are sensitive and must not appear in logs,
errors, response JSON, or object representations.

Suggested commit message:

```text
Define authentication contracts and security primitives
```

Implement:

- Add strict signup/login request schemas and the frontend-ready auth response schema.
- Enforce the documented email and password constraints without mutating passwords.
- Centralize email normalization so insert and lookup use identical behavior.
- Extend the shared Argon2id helper with safe verify-and-update behavior.
- Add a secure opaque-token generator and a SHA-256 digest helper.
- Keep token generation injectable for deterministic collision and persistence tests.
- Add unit tests for schema rejection, normalization, password boundaries, malformed
  hashes, rehash detection, token entropy/shape, and deterministic digest output.
- Add negative tests proving schema serialization and errors do not expose passwords,
  hashes, raw tokens, or token digests.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/schemas tests/core/test_security.py
cd ..
make check
git diff --check
```

## Commit 2 — Add Session Persistence and Lifecycle Services

**Status:** Complete.

Commit 2 implements repository operations and the shared session lifecycle before any
route can issue a cookie. Repositories perform focused queries; services own transaction
boundaries and authentication policy.

In plain language, this commit defines how long a user stays logged in and what happens
to the login session throughout its lifetime. A successful signup or login creates a
session that lasts 30 days by default. That deadline is absolute: using the application
does not restart or extend the 30-day period.

The browser receives the raw session token in a secure `HttpOnly` cookie, while the
database stores only its SHA-256 digest. Recent activity is recorded in `last_used_at`,
but that timestamp is updated at most once per hour to avoid writing to the database on
every request. When a session expires, it is rejected immediately and removed when
encountered. Logout revokes the applicable session and clears its browser cookie.

Commit 2 builds these underlying storage and lifecycle services. Later commits connect
them to the signup, login, current-user, and logout API endpoints.

A newly created session must have:

```text
created_at   = injected UTC now
last_used_at = created_at
expires_at   = created_at + SESSION_TTL_SECONDS
```

The service stores only the token digest and returns the raw token just far enough for
the API layer to set the response cookie. It must commit user/session changes together,
roll back on failure, and handle the extremely unlikely unique-digest collision without
persisting a partial result.

Session resolution hashes the presented raw token, looks up the digest with its user,
and applies absolute expiry at `expires_at <= now`. An expired session is invalid
immediately even if physical cleanup has not previously run. Resolving a valid session
updates `last_used_at` at most once per hour; this write-throttling does not extend
`expires_at`.

The cookie helper must set and clear the same identity and scope:

| Attribute  | Issued cookie behavior                              |
| ---------- | --------------------------------------------------- |
| Name       | Configured `SESSION_COOKIE_NAME`                    |
| `HttpOnly` | Always true                                         |
| `Secure`   | Required in production; configured safely elsewhere |
| `SameSite` | `Lax`                                               |
| `Path`     | `/`                                                 |
| `Max-Age`  | Configured `SESSION_TTL_SECONDS`                    |

Suggested commit message:

```text
Add session lifecycle services
```

Implement:

- Add focused user and session repositories using async SQLAlchemy 2.x.
- Add normalized user lookup and session lookup by the unique token digest.
- Create sessions with injected UTC time and configured absolute expiry.
- Store only the lowercase SHA-256 digest; never pass the raw token to a model.
- Resolve a valid session and its user in one focused repository path.
- Treat `expires_at <= now` as expired and delete the expired session transactionally.
- Update `last_used_at` only when at least one hour has elapsed since its prior value.
- Add session revocation and cookie issue/clear helpers with matching attributes.
- Add PostgreSQL tests for creation, token uniqueness, exact expiry boundaries,
  throttled activity writes, absolute expiry, deletion, rollback, and secret
  non-persistence.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/repositories tests/services/test_sessions.py
cd ..
make check
git diff --check
```

## Commit 3 — Implement Signup and Concurrent Duplicate Protection

**Status:** Complete.

Commit 3 adds `POST /api/auth/signup`. A successful request creates the normalized user
and first session in one transaction, sets the session cookie, and returns `201` with
the public user response.

In plain language, this commit builds the signup process that turns a new user's email
and password into an account:

```text
receive email and password
    ↓
validate them using Commit 1's rules
    ↓
normalize the email and hash the password
    ↓
create the user and initial login session together
    ↓
set the session cookie
    ↓
return the safe user ID and normalized email
```

The user is logged in immediately after successful signup. The response never includes
the plaintext password, password hash, raw session token, or stored token digest.

This commit also handles duplicate emails safely. Email normalization means values such
as `Person@Example.com` and `person@example.com` identify the same account. If two
signup requests for that normalized email arrive at nearly the same time, the database
unique-email constraint allows only one account to be created. The other request is
rolled back and receives a safe `409 duplicate_email` response. The user and initial
session are created in one transaction, so either both are saved or neither is saved.

```text
valid new credentials
    ↓
normalize email + hash password
    ↓
insert user + create session in one transaction
    ↓
201 user response + Set-Cookie
```

Duplicate handling must be correct under concurrency. A friendly pre-check may avoid an
unnecessary password hash in the common case, but it is not the correctness boundary.
The service must catch the named unique-email violation raised by PostgreSQL, roll back,
and translate it to:

```json
{
  "error": {
    "code": "duplicate_email",
    "message": "An account with this email already exists."
  }
}
```

The conflict returns `409` without creating a session or changing the existing user.
Unrelated integrity or database errors must not be mislabeled as duplicate email.

Suggested commit message:

```text
Implement authentication signup
```

Implement:

- Add the auth router under the existing `/api` prefix.
- Add a signup service transaction that creates the user and session atomically.
- Normalize email before both duplicate lookup and insert.
- Hash the password before persistence and never retain or return plaintext.
- Return `201` with the exact public user envelope and configured session cookie.
- Translate only the unique-email constraint conflict to `duplicate_email` `409`.
- Preserve the standard `validation_error` envelope for malformed requests.
- Add service and API integration tests for success, normalization, cookie attributes,
  duplicate normalized email, concurrent duplicate insertion, rollback, response
  shape, and non-disclosure.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/services/test_auth_signup.py tests/api/test_auth_signup.py
cd ..
make check
git diff --check
```

## Commit 4 — Implement Login and Credential Verification

**Status:** Complete.

Commit 4 adds `POST /api/auth/login`. Login uses the same email normalization, session
creation, cookie, and public response paths as signup.

Both an unknown email and an incorrect password return the same status, error code, and
message:

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Email or password is incorrect."
  }
}
```

The response is `401` and must not reveal which credential failed through response
content or application logs. Implementations should also avoid a large timing
difference between the missing-user and wrong-password paths by verifying missing
users against a fixed valid dummy hash.

After a correct password is verified, outdated Argon2 parameters are upgraded inside
the same transaction that creates the new session. Each successful login creates a
separate revocable session; it does not invalidate the user's other valid sessions.

Suggested commit message:

```text
Implement authentication login
```

Implement:

- Add the login service and route using the shared normalized lookup.
- Return the same safe `invalid_credentials` `401` for absent email and wrong password.
- Use a fixed valid dummy hash for the missing-user verification path.
- Rehash a valid password when the configured Argon2 parameters require an upgrade.
- Create and commit the new session only after successful verification.
- Return `200` with the public user envelope and the same cookie policy as signup.
- Leave other valid sessions for the same user active.
- Add service and API tests for success, normalization, invalid email, invalid password,
  malformed stored hash, hash upgrade, multiple sessions, cookie attributes, rollback,
  equivalent public failures, and log/response non-disclosure.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/services/test_auth_login.py tests/api/test_auth_login.py
cd ..
make check
git diff --check
```

## Commit 5 — Add Session Resolution, Current User, and Logout

**Status:** Complete.

Commit 5 connects session resolution to FastAPI dependencies and completes the public
auth lifecycle.

In plain language, this commit lets the application answer “Who is currently logged
in?” and lets that user log out.

`GET /api/auth/me` reads the browser's session cookie, verifies the corresponding
server-side session, and returns the current user's safe public ID and email. The
frontend will use this endpoint after a page reload to restore the logged-in user
without storing an authentication token in JavaScript, local storage, or session
storage. A missing, malformed, unknown, or expired session always receives the same
safe `401 unauthorized` response.

`POST /api/auth/logout` deletes only the session represented by the current browser
cookie and clears that cookie. Sessions on the user's other browsers or devices remain
active. Logout is idempotent: calling it repeatedly, or calling it with a missing,
invalid, unknown, or expired cookie, is safe and still returns success.

This commit also creates the reusable `get_current_user` backend dependency. Future
protected endpoints use it to identify the authenticated user and scope database
operations to that user's records.

`GET /api/auth/me` is protected. It reads the configured cookie, resolves the session,
and returns the same public user envelope used by signup and login. Missing, malformed,
unknown, or expired cookies all return the standard `unauthorized` `401` without
revealing session state.

The authenticated-user dependency becomes the shared authorization entry point for
DEV-010 and later protected routes:

```text
request cookie
    ↓
get_current_user
    ├── valid session   → User
    └── otherwise       → unauthorized 401
```

`POST /api/auth/logout` is intentionally idempotent and does not require a valid
session. If the presented cookie resolves to a valid session, only that session is
deleted. Missing, malformed, unknown, or expired cookies still return `200`. Every
logout response clears the browser cookie with attributes matching issuance.

Suggested commit message:

```text
Add current session and logout endpoints
```

Implement:

- Add cookie extraction that treats missing and malformed input as authentication
  failures without leaking parser or database details.
- Add `get_current_user` using the shared session service and injected request clock.
- Add `GET /api/auth/me` with the exact auth response envelope.
- Return the standard `unauthorized` `401` for every invalid-session class.
- Delete expired session rows when encountered while keeping the public response safe.
- Add idempotent `POST /api/auth/logout`.
- Revoke only the presented valid session; preserve the user's other sessions.
- Clear the cookie on every logout result with matching name, path, `SameSite`, and
  environment-appropriate `Secure` behavior.
- Add fixed-clock service and API tests for missing, malformed, unknown, valid, and
  exactly expired sessions; last-used throttling; multiple sessions; repeated logout;
  and cookie clearing.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/services/test_session_resolution.py tests/api/test_auth_session.py
cd ..
make check
git diff --check
```

## Commit 6 — Complete Browser Security, Documentation, and Verification

Commit 6 verifies the auth boundary as a complete browser-facing feature and records
the result. Authenticated cookie requests rely on `SameSite=Lax` and same-origin
production deployment. State-changing authenticated requests must additionally reject
a browser `Origin` that does not exactly match `FRONTEND_ORIGIN`.

Requests with the configured origin are accepted. Requests without `Origin` remain
available to otherwise authenticated non-browser clients. A mismatched or malformed
origin is rejected before application mutation. This reusable protection must cover
logout now and the protected write routes added in later development tasks.

The final verification must demonstrate:

```text
raw session token  → cookie only
SHA-256 digest     → database only
plaintext password → request handling only
Argon2id hash      → database only
```

Suggested commit message:

```text
Complete authentication API documentation
```

Implement:

- Add reusable exact-origin enforcement for state-changing authenticated requests.
- Confirm production configuration requires secure cookies and an exact HTTPS frontend
  origin; do not weaken existing credentialed CORS rules.
- Redact `Cookie`, `Set-Cookie`, passwords, raw session tokens, and token digests from
  structured logs and exception detail.
- Confirm generated OpenAPI documents the four `/api/auth` endpoints, schemas, response
  statuses, and standard error envelopes without advertising secrets.
- Document the auth endpoints, cookie behavior, local demo login, and curl/browser
  usage without suggesting local or session storage for tokens.
- Add an end-to-end API integration test covering signup → me → logout → unauthorized
  me and login → me.
- Add security tests for allowed, missing, mismatched, and malformed origins.
- Run the complete clean quality and PostgreSQL migration gates.
- Fill in the Implementation Record below with actual files, commands, counts, and any
  remaining limitations; do not mark work complete based on planned verification.

Commit gate:

```text
make clean
make install
make db-up
make db-upgrade
make seed-demo
make check
cd backend
../.venv/bin/python -m alembic check
cd ..
git diff --check
git status --short
```

## Out of Scope

- Login and signup pages, client-side auth state, route guards, redirect behavior, and
  frontend session restoration; DEV-009 owns these.
- Entry, check-in, statistics, and opportunity-cost routes; DEV-010 onward own those
  product APIs.
- Password reset, email verification, email delivery, social login, passkeys,
  multi-factor authentication, account deletion, and account profile management.
- “Log out all devices,” session-management screens, sliding expiry, and refresh-token
  rotation.
- Shared-store signup/login rate limiting and broader abuse protection; DEV-021 owns
  production hardening.
- Scheduled physical cleanup of expired session rows. Expired sessions are still
  rejected and deleted when encountered in this task.
- Cross-site frontend/backend deployment. A CSRF token design is required before
  changing the approved same-origin and `SameSite=Lax` model.

## Implementation Record

Complete this section as the commit series is implemented. Replace planned language
with the actual result and include only verification that was run successfully.

### Overview

DEV-008 will add the backend authentication schemas, repositories, services,
dependencies, and routes for signup, login, logout, and current-session restoration.
It will build on the users and sessions schema from DEV-005 and the shared Argon2id
primitive introduced by DEV-007.

### What It Achieved

Pending implementation.

### API and Session Behavior

Pending implementation. Record the final endpoint statuses, cookie configuration,
expiry boundary, `last_used_at` throttle behavior, and logout idempotency here.

### Security and Privacy

Pending implementation. Record the final password hashing, token generation/digest,
origin validation, error-equivalence, logging redaction, and secret-persistence checks
here.

### Verification

Pending implementation. Record the exact commands, test counts, PostgreSQL target,
fixed clock values, migration result, and any environment limitations here.

### Limitations and Follow-up

DEV-009 must connect the frontend to these endpoints and implement route guards and
session restoration. DEV-010 and later backend tasks must use `get_current_user` and
scope owned-resource queries by its user ID. DEV-021 must add production rate limiting
and the remaining abuse protections.
