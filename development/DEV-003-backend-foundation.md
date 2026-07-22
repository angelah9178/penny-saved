# DEV-003 — Backend Application Foundation

## Objective

Establish the shared FastAPI infrastructure required by later backend features, with typed configuration, managed database resources, deterministic time dependencies, safe API errors, and request-correlated structured logs.

## Overview

DEV-003 added a FastAPI application factory and process lifespan. Startup creates one async SQLAlchemy engine and session factory; shutdown disposes the engine. Request dependencies can obtain a scoped async session that rolls back unfinished work during cleanup.

Typed Pydantic settings cover the application environment, PostgreSQL URL, frontend origin, session-cookie behavior, session lifetime, and log level. Local development and tests may load `backend/.env`, while a process explicitly started as production ignores the local dotenv file. Production validation requires HTTPS, secure cookies, and a database URL without the documented placeholder credential.

The HTTP foundation now includes:

- `GET /api/health` with the explicit `{"status":"ok"}` response contract.
- A UUID request ID returned through `X-Request-ID`.
- JSON request-completion logs containing the request ID, method, route, status, and duration.
- Credentialed CORS restricted to the single configured frontend origin.
- Standard envelopes for expected, validation, malformed JSON, HTTP, and unexpected errors.
- Safe unexpected-error responses correlated with server logs through the request ID.
- An injectable UTC clock for deterministic lifecycle and statistics tests.

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
