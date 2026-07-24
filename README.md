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

## Combined development workflow

After installation and environment setup, start the complete local application from the
repository root:

```bash
make dev
```

The command checks its prerequisites, starts PostgreSQL and waits for it to become
healthy, applies pending Alembic migrations, then starts the FastAPI backend and Vite
frontend concurrently:

```text
make dev
    ├── PostgreSQL 16
    ├── Alembic upgrade to head
    ├── FastAPI/Uvicorn on http://127.0.0.1:8000
    └── Vite on http://localhost:5173
```

Press `Ctrl+C` to stop both application servers. The process supervisor forwards the
termination signal, stops the sibling server if either process exits, and waits so
neither server is left running. PostgreSQL and its named data volume remain available.
Run `make db-down` separately when you want to stop PostgreSQL without deleting its
data.

Use `make frontend-dev` or `make backend-dev` when you intentionally want to run one
server in a separate terminal. Those focused targets do not start PostgreSQL or apply
migrations for you.

### Combined startup troubleshooting

- A missing dependency message means `make install` has not been run or dependencies
  are out of date.
- A missing environment message means `make env-setup` must be run and its placeholder
  values reviewed.
- A Docker or PostgreSQL health failure stops startup before either application server
  launches. Check Docker, then run `make db-logs`.
- A migration failure stops startup before the servers launch. Review the reported
  Alembic error; do not bypass or edit an already shared revision.
- If port `8000` or `5173` is already in use, stop the existing process before running
  `make dev` again.

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

## Frontend development server

Install the locked frontend dependencies during first-time setup or whenever
`frontend/package-lock.json` changes:

```bash
cd frontend
npm ci
```

Start the Vite development server from `frontend/`:

```bash
npm run dev
```

Open the URL printed by Vite, normally `http://localhost:5173`. Stop the server with
`Ctrl+C`.

The frontend API client uses `VITE_API_BASE_URL`, which defaults to `/api`. During local
development, Vite proxies `/api` requests to the FastAPI server at
`http://127.0.0.1:8000`. Start the backend separately before using a screen that needs
real API data:

```text
Browser → http://localhost:5173/api/... → Vite proxy
        → http://127.0.0.1:8000/api/... → FastAPI
```

The browser continues to request the same-origin `/api` path and includes the backend's
session cookie when one exists. Frontend JavaScript does not read or store the
`HttpOnly` session cookie.

Variables prefixed with `VITE_` are included in browser-visible frontend code. Never put
passwords, session values, database URLs, API secrets, or other credentials in a
`VITE_` variable. Keep `VITE_API_BASE_URL=/api` for the normal local proxy workflow.

### Frontend startup troubleshooting

- `npm: command not found` means Node.js 22 and npm are not available in the current
  shell. Install the supported Node version shown in `.nvmrc` and verify it with
  `node --version`.
- A missing-package error usually means frontend dependencies are not installed. Run
  `npm ci` from `frontend/`.
- If Vite reports that port `5173` is already in use, stop the other process or use the
  alternate URL Vite prints.
- A proxied `/api` request that returns `502` or a connection error usually means the
  FastAPI server is not running at `http://127.0.0.1:8000`.
- Run frontend commands from `frontend/`; running them from the repository root will not
  find the frontend `package.json`.
- The current DEV-004 home and not-found pages are foundation placeholders. Login,
  dashboard, entry, and statistics screens are added by later DEV tasks.

## Database migrations

Alembic migrations are the only supported way to change a shared database schema.
Start PostgreSQL and apply every pending migration from the repository root:

```bash
make db-up
make db-upgrade
```

The initial migration creates the users, sessions, impulse-purchase entries, and
opportunity-cost example tables. Alembic records the applied revision in its
`alembic_version` table.

When intentionally changing SQLAlchemy models, generate a new revision:

```bash
make db-revision message="describe_change"
```

Review the generated upgrade, downgrade, data types, constraint names, index order, and
data-safety implications before applying or committing it. A revision must contain
stable Alembic operations and SQLAlchemy types; it must not import mutable application
models. Never edit a migration that may already have been applied to a shared database.

Useful inspection commands run from `backend/`:

```bash
../.venv/bin/python -m alembic current
../.venv/bin/python -m alembic history
../.venv/bin/python -m alembic check
```

`alembic check` reports whether the current SQLAlchemy metadata would require another
migration. Production and shared environments should migrate forward only through
reviewed revisions. A downgrade is a separate destructive decision, not the normal
production rollback strategy.

### PostgreSQL test database

Database integration tests use a separate disposable PostgreSQL database and refuse to
reuse the development database. Create the standard local test database once:

```bash
docker compose exec postgres sh -c \
  'createdb --username="$POSTGRES_USER" penny_saved_test'
```

If PostgreSQL reports that the database already exists, no additional creation is
needed. Ensure `backend/.env` contains a matching explicit URL:

```text
TEST_DATABASE_URL=postgresql+psycopg://penny_saved:your-local-password@localhost:5432/penny_saved_test
```

Match the username, password, host, and port in `DATABASE_URL`; change only the database
name to the dedicated `_test` name. Export the backend environment and run the suite from
`backend/`:

```bash
set -a
source .env
set +a
../.venv/bin/pytest
```

The integration suite may migrate, empty, and rebuild only the database selected by
`TEST_DATABASE_URL`. Never point it at development, staging, production, or any database
whose contents need to be preserved.

### Migration troubleshooting

- `Missing backend/.env` or a settings error means local configuration is absent or
  invalid. Run `make env-setup` and replace its placeholders.
- `connection refused` means PostgreSQL is unavailable or the configured host/port is
  incorrect. Run `make db-up` and compare both environment files.
- `database "penny_saved_test" does not exist` means the one-time test-database creation
  command has not been run.
- `Integration tests require an explicit TEST_DATABASE_URL` means the variable has not
  been exported into the test process.
- `Target database is not up to date` means pending revisions must be applied before
  generating another migration.
- A nonempty `alembic check` result means model metadata and migration head have drifted;
  create and review a new migration rather than changing an applied revision.

Run `make help` to list all available commands.

## Database safety

`make db-reset` permanently deletes only the named local development volume after requiring the exact confirmation word `reset`. It refuses to run in CI, production mode, or against a non-local database URL.

`make db-downgrade` also requires confirmation and is restricted to a local database
with `APP_ENV=development`. Never downgrade a shared, test, staging, or production
database. Tests must supply an explicit `TEST_DATABASE_URL`; they must not derive it
from `DATABASE_URL`.

## Quality checks and continuous integration

Run the complete local quality gate from the repository root:

```bash
make check
```

It stops at the first failure and runs these stages in order:

```text
format-check → lint → typecheck → test → build
```

The command validates both workspaces: Prettier, ESLint, TypeScript, Vitest, Ruff,
Pytest, the production frontend build, and backend application construction. It does
not install dependencies. Run `make install` first, start PostgreSQL, and configure the
explicit `TEST_DATABASE_URL` described above. The backend integration suite may rebuild
only that dedicated `_test` database.

Run `make check` before committing, pushing, or opening a pull request. Focused
frontend/backend and individual-stage targets are listed by `make help` when a failure
needs to be reproduced without repeating the whole gate.

Remove replaceable generated artifacts with:

```bash
make clean
```

Cleanup removes known frontend build and coverage output, Python bytecode, Pytest and
Ruff caches, coverage data, and TypeScript incremental metadata. It preserves source,
tests, migrations, `.env` files, `.venv`, `frontend/node_modules`, dependency files,
Docker resources, and PostgreSQL data. It is safe to run repeatedly.

GitHub Actions runs the **Quality** workflow automatically for pull requests and pushes
to `main`. It uses clean environments, locked or pinned dependency installation, and
temporary PostgreSQL 16 services without production secrets.

| Required job | Local equivalent | Additional CI responsibility |
|---|---|---|
| `frontend` | Frontend stages of `make check` | Clean Node.js install and production build |
| `backend` | Backend stages of `make check` | Clean Python install and ephemeral PostgreSQL tests |
| `migrations` | Focused migration integration tests | Empty upgrade, downgrade to base, re-upgrade, and drift check |

All three stable job names—`frontend`, `backend`, and `migrations`—are intended required
merge checks. Configuring repository branch protection is a GitHub administrator action
and is not performed by the workflow itself.

### Quality and CI troubleshooting

- A local formatting, lint, typing, test, or build failure can be reproduced with the
  focused target shown by `make help`.
- `Missing TEST_DATABASE_URL` means `backend/.env` does not contain the explicit
  disposable PostgreSQL test URL.
- A PostgreSQL connection failure usually means the container is stopped or the host
  port in `backend/.env` does not match `docker compose ps`.
- On GitHub, open the first failing step in the relevant `frontend`, `backend`, or
  `migrations` job, reproduce its local equivalent, fix it, and push again. GitHub
  automatically starts a new workflow run for the pull request.
