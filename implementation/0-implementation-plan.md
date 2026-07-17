# Implementation Design Plan

## Purpose

This document is the control document for implementing **A Penny Saved**. The `SYS-*` documents define product behavior and system boundaries; the documents in this folder define the concrete code, schema, interfaces, tests, and delivery sequence.

The implementation documents are:

1. `1-database-implementation-plan.md` — PostgreSQL schema, constraints, indexes, migrations, query design, and database testing.
2. `2-frontend-implementation-plan.md` — React application structure, routes, components, API integration, state, validation, accessibility, and frontend testing.
3. `3-backend-implementation-plan.md` — FastAPI structure, configuration, authentication, services, transactions, API behavior, security, and backend testing.

If an implementation detail conflicts with a `SYS-*` product rule, the `SYS-*` rule wins and the implementation document must be corrected. Intentional changes require updating both layers of documentation.

## Implementation Objectives

- Deliver the complete V1 scope in `SYS-001`.
- Keep lifecycle and statistics rules in the backend, not duplicated in the browser.
- Store all money as integer cents and all timestamps as UTC-aware values.
- Protect every user-owned resource with authenticated ownership checks.
- Make schema changes reproducible with Alembic migrations.
- Make each delivery phase independently testable.
- Prefer explicit, typed contracts over implicit object shapes.

## Fixed Technology Baseline

Use current compatible stable releases when the project is initialized and lock exact versions in dependency lock files.

| Layer | Decision |
|---|---|
| Runtime | Python 3.12+, Node.js 22 LTS+ |
| Frontend | React, TypeScript in strict mode, Vite, React Router, TanStack Query |
| Backend | FastAPI, Pydantic v2, SQLAlchemy 2.x async API, Alembic |
| Database | PostgreSQL 16+ with `timestamptz` and native UUID values |
| DB driver | `psycopg` v3 async driver |
| Authentication | Argon2id password hashes and opaque server-side cookie sessions |
| Frontend tests | Vitest, React Testing Library, MSW |
| Backend tests | Pytest, pytest-asyncio, HTTPX |
| Quality | Ruff for Python; ESLint and Prettier for TypeScript |

## Repository Target

```text
frontend/
  src/
    api/
    app/
    components/
    features/
    hooks/
    lib/
    pages/
    routes/
    test/
    types/
backend/
  app/
    api/
    core/
    db/
    models/
    repositories/
    schemas/
    services/
  alembic/
  tests/
implementation/
planning/
Makefile
.env.example
```

Feature-specific frontend code belongs under `features/auth`, `features/entries`, `features/stats`, and `features/opportunity-costs`. Backend routers translate HTTP; services enforce use cases; repositories contain database access. Routers must not contain SQL or lifecycle calculations.

## Cross-Layer Contracts

### Identifiers, time, and money

- IDs are UUIDs serialized as lowercase hyphenated strings.
- API timestamps are RFC 3339 UTC strings using `Z` on output.
- The database uses `timestamptz`; application code uses timezone-aware UTC `datetime` values.
- Money is a positive integer number of cents. No floating-point value may cross an API or database boundary.
- Display currency is USD in V1 and is formatted only in the frontend.

### Naming and serialization

- JSON and Python schema fields use `snake_case` to match the existing API contract.
- TypeScript types preserve the API's `snake_case`; do not silently remap keys.
- Database tables and columns use `snake_case` and plural table names.
- Empty optional comments are normalized to `null`; required text is trimmed and may not become empty.

### Error behavior

Every error response must use:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Safe user-facing summary.",
    "fields": { "optional_field": "Optional field error." }
  }
}
```

`fields` is optional. Validation errors use `422`; malformed JSON uses `400`; missing/invalid sessions use `401`; an absent resource uses `404`; and a known resource owned by another user uses `403`, as specified by `SYS-004`. Error messages must not disclose the other owner’s identity or data.

### Business invariants

- `needs_check_in` is derived from `status = waiting` and `created_at <= now - 48 hours`; it is never stored.
- Only waiting entries can have core details edited or be deleted.
- Only eligible waiting entries can transition once to `saved` or `purchased`.
- Statistics use `checked_in_at`, not `created_at`.
- Saved entries contribute to total saved and avoided count; purchased entries contribute only to purchased count.
- The backend clock is authoritative. Tests inject/freeze time rather than waiting.

## Delivery Sequence and Gates

### Phase 1: Foundation

- Scaffold frontend and backend directories and locked dependencies.
- Add environment parsing, database connection, CORS/cookie configuration, structured logging, and `/api/health`.
- Add Make targets: `install`, `dev`, `test`, `lint`, `format`, `db-upgrade`, `db-downgrade`, and `db-revision`.
- Add CI jobs for frontend checks, backend checks, and migration application.

Gate: clean installs work; health endpoint passes; lint, type checks, and empty test suites run in CI.

### Phase 2: Database and authentication

- Implement the initial schema and migration.
- Implement signup, login, logout, and session restoration.
- Implement auth pages, auth bootstrap, and protected/guest route guards.

Gate: auth API integration tests pass, passwords and raw tokens are absent from the database, and a browser refresh restores the session.

### Phase 3: Entry management

- Implement entry create, list, detail, edit, and delete operations.
- Implement backend grouping into all four dashboard buckets.
- Implement dashboard, add-entry, and waiting-entry edit flows.

Gate: ownership and lifecycle tests pass; newly created entries appear in Waiting without a full reload.

### Phase 4: Check-in lifecycle

- Implement eligibility calculation and atomic status transition.
- Implement the check-in screen and saved/purchased confirmations.
- Implement comment-only updates for resolved entries.

Gate: boundary tests at one microsecond before and exactly at 48 hours pass; concurrent check-in cannot transition twice.

### Phase 5: Statistics and opportunity costs

- Implement range boundaries, aggregate queries, opportunity-cost CRUD, and equivalents.
- Implement statistics cards, filter control, opportunity-cost display, and settings management.

Gate: date-boundary and aggregate tests pass, and frontend views refresh after relevant mutations.

### Phase 6: Hardening and release

- Complete responsive behavior, accessibility checks, empty/error/loading states, rate limiting, logging, and security headers.
- Run all automated tests against a real PostgreSQL test database.
- Apply migrations to a clean database and verify downgrade/upgrade behavior.

Gate: CI is green, no high-severity dependency findings remain, and the release checklist is complete.

## Definition of Done for Every Feature

A feature is complete only when:

- Its API and UI behavior match the system contracts.
- Database constraints and indexes support its invariants and queries.
- Backend authorization is enforced independently of the UI.
- Success, loading, empty, validation, authentication-expired, and server-error states are handled.
- Unit/integration tests cover normal, boundary, unauthorized, and conflict cases.
- Type checking, linting, formatting, and tests pass.
- Environment variables and operational behavior are documented.
- No sensitive value is logged or returned.

## Testing Strategy

Use the test pyramid:

- Unit tests: pure time-range, eligibility, normalization, and formatting functions.
- Service tests: lifecycle transitions, stats calculations, and auth behavior with a test database.
- API integration tests: HTTP status, response schema, cookies, ownership, and transaction results.
- Frontend component tests: user-visible behavior with MSW rather than implementation details.
- A small end-to-end smoke suite: signup, create item, eligible check-in with seeded data, statistics, logout.

Tests must use deterministic factories, explicit UTC timestamps, and isolated database transactions or truncated schemas. SQLite is not a substitute for PostgreSQL because constraints, UUIDs, locking, and timestamp behavior differ.

## Operational and Security Baseline

- Secrets come only from environment variables; commit `.env.example`, never `.env`.
- Production requires HTTPS, secure cookies, an explicit frontend origin, and trusted proxy configuration.
- Log request ID, method, route template, status, duration, and authenticated user ID when available; never log passwords, cookies, or raw tokens.
- Return generic `500` responses and capture stack traces only in server logs.
- Add login/signup throttling before public deployment.
- Back up PostgreSQL and test restoration before production use.

## Decision Log

Record material implementation decisions at the end of the relevant implementation document with date, decision, rationale, and consequences. Decisions that change product behavior also require a `SYS-*` update.

## Open Items to Resolve Before Production

- Deploy the application and PostgreSQL database on an Oracle Cloud VPS. Use `https://stop-impulse-buying.us` as the production origin, subject to final domain registration and DNS confirmation.
- Use Amazon Web Services for transactional email. The specific AWS email service, sender-domain verification, credentials, templates, delivery monitoring, and password-reset flow must be finalized before email-dependent features are implemented.
- Session lifetime and retention policy should be confirmed; this design defaults to 30 days.
- Whether V1 supports only USD or adds a stored currency code. This design fixes USD to avoid implying unsupported multi-currency totals.
