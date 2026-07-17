# Authentication Development

## Category Tracker

| ID | Outcome | Depends on | Status | PR |
|---|---|---|---|---|
| DEV-008 | Secure signup, login, logout, and current-session API | DEV-005 | Not started | — |
| DEV-009 | Accessible auth pages, bootstrap, and route protection | DEV-004, DEV-008 | Not started | — |

## DEV-008 — Implement authentication and session API

Scope:

- Implement auth schemas, repository operations, service transactions, and the exact `SYS-004` endpoints.
- Normalize emails, hash passwords with Argon2id, generate opaque random session tokens, and store only SHA-256 digests.
- Issue the configured `HttpOnly`, `SameSite=Lax` session cookie with environment-appropriate `Secure` behavior.
- Resolve, expire, refresh `last_used_at` as designed, and revoke sessions; expose the authenticated-user dependency.
- Translate duplicate email, invalid credentials, validation, and missing/expired session cases into standard safe errors.
- Add service and API integration tests for cookie attributes, persistence, expiry boundaries, logout, and secret non-disclosure.

Acceptance:

- Signup/login return the documented user and session behavior; refresh can resolve `/me` without credentials in browser storage.
- Logout invalidates the server record and clears the cookie idempotently as designed.
- The database and logs contain neither raw tokens nor plaintext passwords.

## DEV-009 — Implement authentication UI and route guards

Scope:

- Build signup and login pages with accessible labels, client-side usability validation, and server field/global errors.
- Bootstrap auth from the current-session endpoint before deciding routes.
- Add protected and guest-only route guards without treating frontend guards as authorization.
- Add logout behavior, auth-expiry handling, focus management, pending-state duplicate-submit prevention, and safe redirect rules.
- Add MSW-backed component/router tests for success, invalid credentials, duplicate email, expiry, refresh restoration, and logout.

Acceptance:

- A valid session survives reload and reaches protected content without UI flicker to the wrong route.
- Guest users cannot remain on protected routes; authenticated users do not remain on guest-only auth routes.
- Passwords and session values are never stored in local/session storage or logged.

## Design Traceability

- `implementation/2-frontend-implementation-plan.md`: authentication UI, routes, state, security, and tests.
- `implementation/3-backend-implementation-plan.md`: authentication/session lifecycle, validation, errors, and tests.
- `implementation/1-database-implementation-plan.md`: users and sessions constraints/indexes.
