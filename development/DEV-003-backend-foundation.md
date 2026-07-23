# DEV-003 — Establish Backend Application Foundation

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|  | Commit | Title | Depends on |
|---|---|---|---|
| &#91;x&#93; | [1](#commit-1--add-typed-backend-configuration) | Add typed backend settings | — |
| &#91;x&#93; | [2](#commit-2--add-an-injectable-utc-clock) | Add injectable UTC clock | Commit 1 |
| &#91;&#160;&#93; | [3](#commit-3--add-async-database-session-and-application-lifespan) | Add async database lifecycle | Commit 1 |
| &#91;&#160;&#93; | [4](#commit-4--create-the-fastapi-factory-and-health-api) | Add FastAPI factory and health routes | Commits 1, 3 |
| &#91;&#160;&#93; | [5](#commit-5--add-request-ids-and-structured-request-logging) | Add request-correlated structured logging | Commit 4 |
| &#91;&#160;&#93; | [6](#commit-6--add-the-standard-error-envelope) | Add safe API error handling | Commits 4, 5 |
| &#91;&#160;&#93; | [7](#commit-7--document-and-verify-the-completed-foundation) | Document DEV-003 backend foundation | Commits 1–6 |

## Objective

Build the smallest production-aware FastAPI foundation that later backend features can
extend. The completed work must provide validated settings, deterministic time, async
database lifecycle management, a versioned API, health endpoints, request-correlated
structured logs, safe error responses, and focused tests.

This document is an implementation runbook. Complete and commit each section in order.
Do not combine the commits: every commit should leave the backend checks green and create
one reviewable step in the history.

## Starting Point

DEV-003 starts from the merged DEV-002 state. Before beginning:

- Confirm `git status --short` is empty.
- Confirm the local backend environment was created with `make env-setup`.
- Install the pinned backend dependencies with `make backend-install`.
- Do not add database models, Alembic migrations, authentication, or product endpoints.
  Those belong to later DEV tasks.

## Commit 1 — Add Typed Backend Configuration

Typed settings define the expected type and validation rules for each configuration
value. Pydantic converts environment-variable text into values such as integers, booleans,
and environment enums, then stops the application early if required configuration is
missing, malformed, or unsafe. This gives the rest of the backend one reliable
`Settings` object instead of repeatedly reading and converting raw environment strings.

Suggested commit message:

```text
Add typed backend settings
```

Implement:

- Add `backend/app/core/config.py` using `pydantic-settings`.
- Define typed values for `APP_ENV`, `DATABASE_URL`, `FRONTEND_ORIGIN`,
  `SESSION_COOKIE_NAME`, `SESSION_TTL_SECONDS`, `SESSION_COOKIE_SECURE`, and
  `LOG_LEVEL`.
- Load `backend/.env` only for local development; production configuration must come from
  the process environment.
- Validate allowed environments, positive session lifetime, supported log levels, an
  exact frontend origin, and a PostgreSQL SQLAlchemy URL.
- Reject wildcard CORS when credentials are enabled.
- Require secure cookies and all production-required values in production.
- Expose a cached `get_settings()` function and a cache-clear seam for tests.
- Add configuration tests for defaults, environment overrides, malformed values, and
  production-only failures. Tests must not depend on a developer's real `.env`.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_config.py
```

## Commit 2 — Add an Injectable UTC Clock

UTC gives the backend one unambiguous time standard regardless of the server's location,
user time zones, or daylight-saving changes. This is especially important for exact
time-based rules such as the 48-hour check-in boundary.

Injectable means application code receives a clock dependency instead of calling
`datetime.now()` directly. Production uses the real system UTC clock, while tests can
replace it with a fixed clock. This makes boundary tests deterministic, avoids waiting or
time-sensitive test failures, and lets an operation use a consistent definition of
“now.”

Suggested commit message:

```text
Add injectable UTC clock
```

Implement:

- Add `backend/app/core/time.py`.
- Define the application clock abstraction and its production UTC implementation.
- Ensure returned datetimes are timezone-aware and normalized to UTC.
- Expose `get_clock()` as a FastAPI dependency that can be overridden by tests.
- Add deterministic clock tests, including rejection or normalization of naive/non-UTC
  values as required by the chosen interface.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_time.py
```

## Commit 3 — Add Async Database Session and Application Lifespan

Suggested commit message:

```text
Add async database lifecycle
```

Implement:

- Add `backend/app/db/session.py`.
- Build one SQLAlchemy async engine and one async session factory per application
  lifespan from the validated database URL.
- Store application-owned database resources on FastAPI application state rather than in
  import-time mutable globals.
- Add `get_db_session()` to yield one `AsyncSession` per request.
- Roll back any open transaction during dependency cleanup; services added later remain
  responsible for committing successful work.
- Dispose the engine during lifespan shutdown.
- Make engine/session construction replaceable in tests so this commit does not require
  the DEV-005 schema.
- Add tests proving one startup/shutdown lifecycle, session cleanup, rollback on failure,
  and engine disposal.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_db_session.py
```

## Commit 4 — Create the FastAPI Factory and Health API

Suggested commit message:

```text
Add FastAPI factory and health routes
```

Implement:

- Add `backend/app/main.py`, `backend/app/api/router.py`, and
  `backend/app/api/routes/health.py`.
- Implement `create_app(settings=...)` so tests can construct isolated applications.
- Register the versioned `/api` router and the database lifespan.
- Configure credentialed CORS for the single validated frontend origin.
- Add `GET /api/health` as process liveness with an explicit Pydantic response model and
  stable operation ID.
- Add `GET /api/ready` as bounded database readiness using `SELECT 1`; return a safe
  unavailable response when the database cannot be reached.
- Keep non-production OpenAPI enabled and make the production behavior explicit.
- Add API tests for the health contract, readiness success/failure, API prefix, OpenAPI
  behavior, and exact CORS allow-list.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/api/test_health.py
```

## Commit 5 — Add Request IDs and Structured Request Logging

Suggested commit message:

```text
Add request-correlated structured logging
```

Implement:

- Add `backend/app/core/logging.py` and request middleware.
- Accept a valid inbound request ID or generate one when it is absent/invalid.
- Return the request ID in the response and make it available to handlers and error
  reporting for the lifetime of the request.
- Emit structured request-completion logs containing timestamp, level, environment,
  request ID, method, route template, status, and duration.
- Configure logging from `LOG_LEVEL` without logging configuration at module import.
- Redact or omit `Cookie`, `Set-Cookie`, authorization values, passwords, database
  credentials, and session material.
- Add tests for generated and propagated IDs, concurrent request isolation, required log
  fields, route templates, and sensitive-value omission.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_logging.py tests/api/test_request_context.py
```

## Commit 6 — Add the Standard Error Envelope

Suggested commit message:

```text
Add safe API error handling
```

Implement:

- Add the shared error schemas in `backend/app/schemas/common.py`.
- Add `backend/app/api/errors.py` with a typed application error and centralized FastAPI
  handlers.
- Return every handled error as:

  ```json
  {
    "error": {
      "code": "machine_readable_code",
      "message": "Safe user-facing summary.",
      "fields": {
        "optional_field": "Optional field error."
      }
    }
  }
  ```

- Translate request validation failures to a safe `422 validation_error` response with
  stable field keys.
- Translate malformed JSON to the designed safe `400` response.
- Translate database availability failures to a generic `503`.
- Translate unexpected exceptions to a generic `500` containing the response request ID;
  log the traceback server-side with the same request ID.
- Never expose Pydantic internals, SQL statements, credentials, exception text, or
  tracebacks in responses.
- Add tests for each error class, exact response shapes/statuses, optional `fields`,
  request correlation, and secret/exception-detail omission.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/api/test_errors.py
```

## Commit 7 — Document and Verify the Completed Foundation

Suggested commit message:

```text
Document DEV-003 backend foundation
```

Complete:

- Update the backend/root setup documentation with the application start command,
  required configuration, liveness/readiness behavior, and safe troubleshooting notes.
- Convert this runbook into the DEV-003 implementation record by adding concise
  `Overview`, `What It Achieved`, `Verification`, and `Boundaries and Follow-up`
  sections. Preserve this commit history and note any accepted deviations.
- Mark DEV-003 complete in `development/0-development-plan.md` only after all acceptance
  checks pass.
- Confirm no `.env`, credentials, cookies, connection strings, caches, or generated
  artifacts are tracked.

Final gate:

```text
ruff format --check .
ruff check .
pytest
git diff --check
git status --short
```

Also start the application with development configuration and manually confirm:

- `/api/health` returns its documented success contract.
- `/api/ready` reports the local PostgreSQL state without leaking connection details.
- Responses contain request IDs.
- Request logs are structured and contain no credentials or cookies.

## DEV-003 Acceptance Checklist

- [ ] Typed configuration fails early with actionable, secret-free errors.
- [ ] Production requires an explicit frontend origin and secure session cookies.
- [ ] The application owns one async engine per lifespan and disposes it at shutdown.
- [ ] Request database sessions roll back unfinished work during cleanup.
- [ ] The application clock is UTC-aware, request-consistent, and test-injectable.
- [ ] `/api/health` has an explicit successful response contract.
- [ ] `/api/ready` checks PostgreSQL with a bounded, safe response.
- [ ] Credentialed CORS permits only the configured frontend origin.
- [ ] Request IDs correlate responses, logs, and unexpected errors.
- [ ] Structured logs omit credentials, cookies, authorization, and session material.
- [ ] Validation, database, and unexpected errors use the standard safe envelope.
- [ ] Backend formatting, linting, and the complete test suite pass.
- [ ] Documentation reflects actual startup and operational behavior.
- [ ] The master tracker is updated only after the completed implementation is verified.

## Out of Scope

DEV-003 does not add:

- SQLAlchemy models, Alembic configuration, or migrations (DEV-005).
- Authentication, session persistence, or current-user dependencies (DEV-008).
- Product repositories, services, or API routes (DEV-008 and later).
- Rate limiting, trusted-proxy deployment policy, or the complete security-header set
  (DEV-021/DEV-022).
- CI workflows or the final combined quality command (DEV-006).
