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

Migration commands become usable when DEV-005 adds the Alembic configuration:

```bash
make db-upgrade
make db-revision message="describe_change"
```

Run `make help` to list all available commands.

## Database safety

`make db-reset` permanently deletes only the named local development volume after requiring the exact confirmation word `reset`. It refuses to run in CI, production mode, or against a non-local database URL.

`make db-downgrade` also requires confirmation and is restricted to a local database with `APP_ENV=development`. Never downgrade a shared, test, staging, or production database. Tests must supply an explicit `TEST_DATABASE_URL`; they must not derive it from `DATABASE_URL`.

## Backend foundation

After creating `backend/.env` and installing dependencies, run the backend from the repository root with:

```bash
cd backend
../.venv/bin/python -m uvicorn app.main:app --reload --port 8000
```

The process-liveness endpoint is available at `http://localhost:8000/api/health`. It returns `{"status":"ok"}` and does not require a database connection. Startup still requires valid configuration and creates the database engine used by later API work.

Production startup requires an HTTPS frontend origin, secure session cookies, a non-placeholder PostgreSQL URL, and environment-provided values rather than the local dotenv file.

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
