# DEV-003 — Establish Backend Application Foundation

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|  | Commit | Title | Depends on |
|---|---|---|---|
| &#91;x&#93; | [1](#commit-1--add-typed-backend-configuration) | Add typed backend settings | — |
| &#91;x&#93; | [2](#commit-2--add-an-injectable-utc-clock) | Add injectable UTC clock | Commit 1 |
| &#91;x&#93; | [3](#commit-3--add-async-database-session-and-application-lifespan) | Add async database lifecycle | Commit 1 |
| &#91;x&#93; | [4](#commit-4--create-the-fastapi-factory-and-health-api) | Add FastAPI factory and health routes | Commits 1, 3 |
| &#91;x&#93; | [5](#commit-5--add-request-ids-and-structured-request-logging) | Add request-correlated structured logging | Commit 4 |
| &#91;x&#93; | [6](#commit-6--add-the-standard-error-envelope) | Add safe API error handling | Commits 4, 5 |
| &#91;&#160;&#93; | [7](#commit-7--document-and-verify-the-completed-foundation) | Document DEV-003 backend foundation | Commits 1–6 |

## Objective

Build the backend foundation in small, independently testable commits. DEV-003 provides
validated configuration, deterministic UTC time, async database lifecycle management, a
FastAPI application factory, health endpoints, request-correlated logs, and safe error
responses.

Complete and commit each section in order. Every commit must leave the backend checks
green before work begins on the next commit.

## Commit 1 — Add Typed Backend Configuration

`backend/app/core/config.py` is the backend's central configuration module. It reads
environment variables, converts them into typed Python values, validates them, and
provides the resulting settings to the application. This gives the application one
validated place to read its configuration.

The module provides seven settings:

| Setting | Type | Purpose |
|---|---|---|
| `app_env` | `AppEnvironment` | Identifies whether the backend is running in development, testing, or production. |
| `database_url` | `str` | Tells SQLAlchemy how to connect to PostgreSQL. |
| `frontend_origin` | `str \| None` | Identifies the frontend allowed to make credentialed browser requests. |
| `session_cookie_name` | `str` | Sets the name of the authentication cookie. |
| `session_ttl_seconds` | `int` | Controls how long a login session remains valid. |
| `session_cookie_secure` | `bool` | Determines whether browsers send the session cookie only over HTTPS. |
| `log_level` | `LogLevel` | Controls how much information the backend writes to its logs. |

Environment variables begin as plain text, and Pydantic converts them into the Python
types the backend expects, such as environment enums, integers, and booleans.

For this project, the settings validate that:

- `APP_ENV` is `development`, `test`, or `production`.
- `DATABASE_URL` uses the required PostgreSQL driver.
- `FRONTEND_ORIGIN` is one exact HTTP or HTTPS origin, not a wildcard.
- `SESSION_TTL_SECONDS` is positive.
- `SESSION_COOKIE_SECURE` is enabled in production.
- `LOG_LEVEL` is supported.
- Required production configuration is present.

If configuration is missing, malformed, or unsafe, the application fails immediately
with an actionable error instead of starting and failing unpredictably later. The rest of
the backend can use one reliable `Settings` object rather than repeatedly reading
`os.environ`, converting strings, and duplicating validation.

Suggested commit message:

```text
Add typed backend settings
```

Implement:

- Add `backend/app/core/config.py` using `pydantic-settings`.
- Define and validate `APP_ENV`, `DATABASE_URL`, `FRONTEND_ORIGIN`,
  `SESSION_COOKIE_NAME`, `SESSION_TTL_SECONDS`, `SESSION_COOKIE_SECURE`, and
  `LOG_LEVEL`.
- Load `backend/.env` only in development.
- Require valid PostgreSQL configuration, an exact frontend origin, and secure production
  cookies.
- Add cached settings access and a cache-clear seam for tests.
- Add tests for defaults, overrides, malformed values, and production requirements.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_config.py
```

## Commit 2 — Add an Injectable UTC Clock

UTC gives the backend one consistent and unambiguous source of time. The server and users
may operate in different time zones, and daylight-saving changes can repeat or skip local
times. Using UTC keeps PostgreSQL timestamps, API timestamps, and comparisons predictable
regardless of where the application runs. This is especially important for exact
time-based rules such as the 48-hour check-in boundary.

Injectable means backend code receives a clock dependency instead of calling
`datetime.now()` directly. Production receives the real system UTC clock, while tests can
replace it with a fixed clock. A fixed clock makes it possible to test behavior just
before, exactly at, and just after 48 hours without waiting or depending on the computer's
current time.

In short:

- UTC makes time consistent.
- Injection makes time controllable.
- A fixed clock makes tests deterministic.
- Production still uses the real current time.

Suggested commit message:

```text
Add injectable UTC clock
```

Implement:

- Add `backend/app/core/time.py`.
- Define the clock abstraction and production UTC implementation.
- Reject naive datetimes and normalize aware non-UTC datetimes to UTC.
- Expose `get_clock()` as an overrideable FastAPI dependency.
- Add deterministic system-clock, fixed-clock, normalization, and dependency tests.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_time.py
```

## Commit 3 — Add Async Database Session and Application Lifespan

Commit 3 builds the bridge between FastAPI and PostgreSQL. Commit 1 gives the backend the
validated database address; Commit 3 uses that address to connect to PostgreSQL and manage
database work safely.

When FastAPI starts, it creates one async SQLAlchemy engine and one session factory. The
engine manages a reusable pool of PostgreSQL connections, while the factory creates a
separate session for each request that needs database access.

For each database-backed request, the application:

1. Creates an isolated session.
2. Gives the session to the route or service.
3. Uses it for that request's queries and changes.
4. Rolls back unfinished work if the request fails.
5. Closes the session when the request finishes.

When FastAPI shuts down, it disposes the engine and closes the pooled connections. The
application shares one engine instead of creating an expensive new engine for every
request. Database operations are asynchronous, so FastAPI can continue handling other
requests while one request waits for PostgreSQL.

Without this shared foundation, future features would need to create and clean up their
own connections. That could cause leaked connections, shared transaction state, partial
changes after failures, too many PostgreSQL connections, and duplicated setup code.
Commit 3 does not add tables or product data; it provides the safe, reusable database
infrastructure that later backend features will use.

Suggested commit message:

```text
Add async database lifecycle
```

Implement:

- Add `backend/app/db/session.py`.
- Create one async SQLAlchemy engine and session factory per application lifespan.
- Store application-owned database resources on FastAPI application state.
- Yield one isolated `AsyncSession` per request.
- Roll back unfinished transactions during dependency cleanup.
- Dispose the engine during application shutdown.
- Add lifecycle, session cleanup, rollback, and disposal tests.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_db_session.py
```

## Commit 4 — Create the FastAPI Factory and Health API

The FastAPI factory is a function that creates and configures the FastAPI application
object. It assembles the validated settings, database lifecycle, API routes, CORS rules,
middleware, and error handlers into one runnable backend application. The application
object receives HTTP requests, sends each request to its matching API route, and returns
the route's response.

In simpler terms, the factory is the backend's initial setup function. A new FastAPI
object does not know anything about this project's routes, database, allowed frontend,
logging, or error-handling rules. The factory creates the object and attaches those
project-specific pieces before the server begins accepting requests.

An empty FastAPI object is like an empty restaurant building. The factory initially
equips and configures the building with what this particular restaurant needs:

- API routes are the menu and service counters.
- Database access is the storage and supply system.
- CORS rules are the entrance policy.
- Logging is the activity record.
- Error handlers are the procedures for handling problems.
- Application settings are the restaurant's operating rules.

FastAPI provides the generic building, while this project's `create_app()` factory turns
it into an A Penny Saved backend that is ready to serve requests. The factory performs
the initial setup; it does not perform all the ongoing work after the application starts.
Routes, services, and database sessions handle that work.

Using a factory keeps application setup in one place. Production can create an app with
real environment settings, while tests can create fresh, isolated apps with controlled
settings and dependency overrides.

Commit 4 also adds two health endpoints with different purposes:

- `GET /api/health` checks whether the FastAPI process is alive and responding. It does
  not need to contact PostgreSQL.
- `GET /api/ready` checks whether the application can reach PostgreSQL and is ready to
  serve database-backed requests.

The backend process can be alive while PostgreSQL is unavailable. In that case,
`/api/health` can succeed while `/api/ready` reports that the application is unavailable.
Monitoring and deployment tools can use this distinction to avoid sending normal traffic
to an application that cannot currently complete database work.

Suggested commit message:

```text
Add FastAPI factory and health routes
```

Implement:

- Add the FastAPI factory, versioned API router, and health routes.
- Register the database lifespan.
- Configure credentialed CORS for the validated frontend origin.
- Add `GET /api/health` for liveness.
- Add `GET /api/ready` for bounded PostgreSQL readiness.
- Add tests for response contracts, readiness, routing, OpenAPI behavior, and CORS.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/api/test_health.py
```

## Commit 5 — Add Request IDs and Structured Request Logging

Commit 5 defines the consistent messages written to the backend logs while the server
handles requests. Instead of relying on differently formatted text messages, every
request log uses predictable fields that are easier to read, search, filter, and send to
a logging service.

A request log will follow a structure similar to:

```json
{
  "timestamp": "2026-07-23T16:30:00Z",
  "level": "INFO",
  "environment": "production",
  "request_id": "7db27c85-3e75-4c5e-8138-cff47f96f77b",
  "method": "GET",
  "route": "/api/health",
  "status": 200,
  "duration_ms": 4.2
}
```

This structure shows which endpoint was called, when it happened, whether it succeeded,
how long it took, and which environment produced the log. It is especially useful for
debugging failures.

Every request receives a unique request ID. The backend returns that ID in the response
and includes it in matching server logs. If the frontend reports an error with a request
ID, the same ID can be searched in the backend logs to find the related request details.
Concurrent requests must keep separate IDs so their logs cannot be mixed together.

Logs must provide useful debugging information without exposing passwords, cookies,
authorization headers, database credentials, or raw session material.

Suggested commit message:

```text
Add request-correlated structured logging
```

Implement:

- Add request ID middleware and structured logging configuration.
- Validate or generate request IDs and return them in responses.
- Log environment, request ID, method, route template, status, and duration.
- Keep concurrent request context isolated.
- Omit credentials, cookies, authorization values, and session material from logs.
- Add request ID, log-field, concurrency, and redaction tests.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/test_logging.py tests/api/test_request_context.py
```

## Commit 6 — Add the Standard Error Envelope

Commit 5 creates backend request logs and request IDs for both successful and failed
requests. Commit 6 defines the safe, predictable HTTP error response that the frontend
receives when a request fails.

Every API error uses this standard envelope:

```json
{
  "error": {
    "code": "machine_readable_code",
    "message": "Safe user-facing summary.",
    "fields": {
      "optional_field": "Optional field-specific error."
    }
  }
}
```

The fields have distinct purposes:

- `code` is a stable value the frontend can use for error-handling logic.
- `message` is a safe summary that can be shown to the user.
- `fields` is optional and maps specific input fields to validation messages.

Validation errors, malformed JSON, database availability failures, and unexpected
exceptions are translated into this same shape with the appropriate HTTP status. Internal
exception text, tracebacks, SQL, and credentials are never returned to the frontend.
Unexpected failures are correlated through the `X-Request-ID` response header and the
matching backend log from Commit 5.

Suggested commit message:

```text
Add safe API error handling
```

Implement:

- Add shared error schemas and centralized FastAPI error handlers.
- Translate validation failures into safe `422` responses.
- Translate malformed JSON into safe `400` responses.
- Translate database unavailability into generic `503` responses.
- Translate unexpected exceptions into generic request-correlated `500` responses.
- Prevent validation internals, SQL, credentials, and tracebacks from reaching clients.
- Add exact status, response-shape, correlation, and secret-omission tests.

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

- Document application startup, configuration, health checks, and troubleshooting.
- Record what DEV-003 achieved, how it was verified, and what remains out of scope.
- Mark DEV-003 complete in `development/0-development-plan.md` only after every check
  passes.
- Confirm secrets, local environments, caches, and generated artifacts are not tracked.

Final gate:

```text
ruff format --check .
ruff check .
pytest
git diff --check
git status --short
```

## Out of Scope

- Database models and Alembic migrations (DEV-005).
- Authentication and session persistence (DEV-008).
- Product repositories, services, and routes (DEV-008 and later).
- Complete deployment hardening and observability (DEV-021/DEV-022).
- CI workflows and the combined quality command (DEV-006).
