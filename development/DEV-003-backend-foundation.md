# DEV-003 — Backend Application Foundation

## Objective

Establish the shared FastAPI infrastructure required by later backend features, with typed configuration, managed database resources, deterministic time dependencies, safe API errors, and request-correlated structured logs.

## Overview

DEV-003 added a FastAPI application factory and process lifespan. Startup creates one async SQLAlchemy engine and session factory; shutdown disposes the engine. Request dependencies can obtain a scoped async session that rolls back unfinished work during cleanup.

### Database engine and session factory

The SQLAlchemy engine manages the backend's pool of connections to PostgreSQL. One engine is normally created when the backend process starts and reused until the process shuts down.

The session factory creates temporary database sessions from that engine. Each API request that needs database access receives its own session for reading or changing data:

```text
API request
    ↓
Session factory creates a session
    ↓
The session reads or changes data
    ↓
Successful changes are committed
    ↓
The session closes
```

If a request fails or leaves a transaction unfinished, cleanup rolls back that unfinished work before closing the session. This prevents incomplete changes from accidentally remaining active.

The engine and sessions are asynchronous. When a request is waiting for PostgreSQL, the backend can continue handling other requests instead of blocking the entire server.

### Typed backend settings

Pydantic reads the backend's configuration and checks that every setting has the expected type and an acceptable value. These settings tell the backend which environment it is running in, how to connect to PostgreSQL, which frontend may send browser requests, how login cookies behave, how long sessions last, and how much information to log.

For local development, the values are stored in the ignored `backend/.env` file. It is created from the committed `backend/.env.example` template by running `make env-setup`. A local file looks like this:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://penny_saved:local-password@localhost:5432/penny_saved
FRONTEND_ORIGIN=http://localhost:5173
SESSION_COOKIE_NAME=penny_saved_session
SESSION_TTL_SECONDS=2592000
SESSION_COOKIE_SECURE=false
LOG_LEVEL=INFO
```

The actual `backend/.env` file is not committed because it can contain credentials that are specific to one developer's computer. Tests provide their own explicit settings. A process explicitly started as production ignores the local dotenv file and reads values from the production environment instead. Production validation requires HTTPS, secure cookies, and a database URL without the documented placeholder credential.

The HTTP foundation now includes:

- `GET /api/health` with the explicit `{"status":"ok"}` response contract.
- A UUID request ID returned through `X-Request-ID`.
- JSON request-completion logs containing the request ID, method, route, status, and duration.
- Credentialed CORS restricted to the single configured frontend origin.
- Standard envelopes for expected, validation, malformed JSON, HTTP, and unexpected errors.
- Safe unexpected-error responses correlated with server logs through the request ID.
- An injectable UTC clock for deterministic lifecycle and statistics tests.

### Request IDs and `X-Request-ID`

For every API request, the backend generates a UUID request ID. A UUID is a long, practically unique identifier, such as:

```text
7d9f80a4-6df4-4cc7-b95c-a285efbf61c8
```

Think of it as a tracking label for one request. The backend includes it in the HTTP response header named `X-Request-ID`:

```text
X-Request-ID: 7d9f80a4-6df4-4cc7-b95c-a285efbf61c8
```

The same ID is added to the server log for that request. If a user receives an error, a developer can use the response's request ID to find the matching log entry and investigate what happened.

Each request receives a new ID, even when several requests come from the same user. A request ID is only for logging and troubleshooting—it is not a login token, session ID, password, or authorization mechanism.

### Standard API error envelopes

A standard error envelope means every API error uses the same basic JSON structure:

```json
{
  "error": {
    "code": "error_type",
    "message": "A safe explanation."
  }
}
```

This gives the frontend one predictable place to find the machine-readable error code and safe user-facing message.

The backend handles these error categories:

- **Expected errors:** Known application problems, such as invalid login credentials or attempting an action that is not allowed for an entry's current state.
- **Validation errors:** One or more submitted fields are missing or invalid. These errors may include a `fields` object so the frontend can display a message beside the affected input.
- **Malformed JSON:** The request body is not valid JSON, such as a body with a missing closing brace.
- **HTTP errors:** General request problems, such as requesting a route that does not exist or using an unsupported request method.
- **Unexpected errors:** Unplanned server or programming failures. The response contains a generic message instead of internal exception details.

An example validation response is:

```json
{
  "error": {
    "code": "validation_error",
    "message": "One or more fields are invalid.",
    "fields": {
      "email": "Invalid value."
    }
  }
}
```

An unexpected failure returns a safe response:

```json
{
  "error": {
    "code": "internal_server_error",
    "message": "An unexpected error occurred."
  }
}
```

The full unexpected error is recorded in the server logs with the request ID. This lets a developer investigate the failure without exposing sensitive implementation details to the user.

## Important Files

```text
backend/app/main.py
backend/app/api/router.py
backend/app/api/errors.py
backend/app/api/routes/health.py
backend/app/core/config.py
backend/app/core/logging.py
backend/app/core/time.py
backend/app/db/session.py
backend/app/schemas/common.py
```

## What It Achieved

- Backend applications can be created with isolated settings for tests or runtime configuration.
- Invalid configuration fails during application creation with actionable validation errors.
- Application-owned database resources have explicit startup and shutdown boundaries.
- Health checks prove process liveness without coupling liveness to PostgreSQL availability.
- API failures no longer expose framework validation details or unexpected exception messages.
- Requests and unexpected failures share a safe correlation identifier.
- Logs record operational request metadata without recording cookie or credential headers.

## Verification

Thirteen backend tests cover:

- Application startup and resource initialization.
- Health response shape and request IDs.
- Allowed and rejected CORS origins.
- Cookie-value omission from request logs.
- Development defaults and production configuration failures.
- PostgreSQL driver and exact-origin validation.
- Standard 404, validation, malformed JSON, and unexpected-error envelopes.
- Safe unexpected-error responses with request correlation.
- UTC-aware clock output.

The implementation passed:

```text
ruff format --check .
ruff check .
pytest
```

API tests use the async HTTPX2 ASGI transport required by the current FastAPI/Starlette stack. They exercise application lifespan without opening a network port or requiring a live database connection.

## Boundaries and Follow-up

DEV-003 does not add database models, migrations, authentication, business services, or feature routes. DEV-005 adds the initial schema and Alembic migration. Later hardening work will add readiness checks, trusted-host/proxy deployment settings, and further security controls.

## Next Steps

You can now start the backend server and confirm that its basic health endpoint works.

From the repository root, make sure the local environment files and backend dependencies exist:

```bash
make env-setup
make backend-install
```

Review `backend/.env`, then start the server from the repository root:

```bash
make backend-dev
```

This Makefile target runs the equivalent of `cd backend && ../.venv/bin/python -m uvicorn app.main:app --reload --port 8000`. It also checks that the virtual environment and `backend/.env` exist before starting the server.

Open `http://localhost:8000/api/health` in a browser, or run:

```bash
curl http://localhost:8000/api/health
```

The expected response is:

```json
{"status":"ok"}
```

You can also open `http://localhost:8000/docs` to view FastAPI's generated API documentation. At this stage, it contains only the health endpoint.

The health endpoint does not query PostgreSQL, so it can respond before database tables and migrations exist. You may start the local PostgreSQL container with `make db-up`, but database-backed application features will not work until DEV-005 adds the models and initial migration.

After confirming the backend starts successfully, the next independent foundation task is DEV-004, which builds the frontend application foundation. DEV-005 can begin after the backend foundation and database workflow are available.
