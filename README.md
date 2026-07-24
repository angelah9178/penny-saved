# A Penny Saved

A Penny Saved is a React and FastAPI application for tracking impulse purchases that were avoided or completed after a waiting period.

## Prerequisites

- Node.js 22 LTS (the exact project version is in `.nvmrc`)
- Python 3.12 or newer (the baseline is in `.python-version`)
- Docker Engine with Docker Compose v2
- GNU Make

## First-time setup

Create local configuration files without overwriting any existing configuration:

```bash
make env-setup
```

Before continuing, replace `change-me-for-local-development` with the same local-only password in `.env` and `backend/.env`. Never commit these files.

Install the locked frontend and pinned backend development dependencies:

```bash
make install
```

Start PostgreSQL 16 and wait for its health check:

```bash
make db-up
```

`compose.yaml` binds PostgreSQL only to `127.0.0.1` and stores its data in the named `penny_saved_postgres_data` volume. `make db-down` stops PostgreSQL while preserving that volume.

## Backend development server

Start PostgreSQL first, then run the FastAPI application factory from `backend/`:

```bash
cd backend
../.venv/bin/uvicorn app.main:create_app --factory --reload
```

The development server listens on `http://127.0.0.1:8000` by default. Stop it with
`Ctrl+C`.

Development API endpoints:

| URL | Purpose |
|---|---|
| `http://127.0.0.1:8000/api/health` | Confirms that the FastAPI process is alive and responding. |
| `http://127.0.0.1:8000/api/ready` | Runs a bounded PostgreSQL connectivity check. |
| `http://127.0.0.1:8000/docs` | Interactive Swagger API documentation. |
| `http://127.0.0.1:8000/redoc` | Alternative API reference. |
| `http://127.0.0.1:8000/openapi.json` | Machine-readable OpenAPI contract. |

`/api/health` can return `200` while `/api/ready` returns `503`. That means the backend
process is running but PostgreSQL is unavailable. Production disables the documentation
and OpenAPI endpoints.

Every response contains an `X-Request-ID` header. Backend request logs contain the same
ID along with the method, route template, status, and duration. Use the ID to correlate a
frontend failure with its backend logs. Logs intentionally omit request bodies, query
strings, cookies, authorization values, database credentials, and session material.

### Backend startup troubleshooting

- A settings validation error means `backend/.env` is missing or contains an invalid
  value. Run `make env-setup`, compare it with `backend/.env.example`, and keep real
  credentials out of Git.
- A `503` from `/api/ready` means PostgreSQL did not answer the readiness probe. Run
  `make db-up`, check `make db-logs`, and confirm `DATABASE_URL` matches the local
  PostgreSQL configuration.
- `Address already in use` means another process is using port `8000`. Stop that process
  or pass a different local port to Uvicorn.
- Run the Uvicorn command from `backend/`; running it from another directory without the
  correct application path can produce an import error.

Migration commands become usable when DEV-005 adds the Alembic configuration:

```bash
make db-upgrade
make db-revision message="describe_change"
```

Run `make help` to list all available commands.

## Database safety

`make db-reset` permanently deletes only the named local development volume after requiring the exact confirmation word `reset`. It refuses to run in CI, production mode, or against a non-local database URL.

`make db-downgrade` also requires confirmation and is restricted to a local database with `APP_ENV=development`. Never downgrade a shared, test, staging, or production database. Tests must supply an explicit `TEST_DATABASE_URL`; they must not derive it from `DATABASE_URL`.

## Baseline checks

Frontend commands are run from `frontend/`:

```bash
npm run format:check
npm run lint
npm run typecheck
npm test
npm run build
```

Backend commands are run from `backend/` with the virtual environment active:

```bash
ruff format --check .
ruff check .
pytest
```

Combined application development commands are added in later foundation work.
