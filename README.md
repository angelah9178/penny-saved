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

| URL                                  | Purpose                                                    |
| ------------------------------------ | ---------------------------------------------------------- |
| `http://127.0.0.1:8000/api/health`   | Confirms that the FastAPI process is alive and responding. |
| `http://127.0.0.1:8000/api/ready`    | Runs a bounded PostgreSQL connectivity check.              |
| `http://127.0.0.1:8000/docs`         | Interactive Swagger API documentation.                     |
| `http://127.0.0.1:8000/redoc`        | Alternative API reference.                                 |
| `http://127.0.0.1:8000/openapi.json` | Machine-readable OpenAPI contract.                         |

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

## Authentication API

The backend provides four cookie-session endpoints:

| Method | Endpoint           | Purpose                                             |
| ------ | ------------------ | --------------------------------------------------- |
| `POST` | `/api/auth/signup` | Create an account and its first login session.      |
| `POST` | `/api/auth/login`  | Verify credentials and create another session.      |
| `GET`  | `/api/auth/me`     | Restore the user represented by the current cookie. |
| `POST` | `/api/auth/logout` | Revoke the current session and clear its cookie.    |

Signup and login accept `email` and `password`. Email is trimmed and lowercased;
passwords must contain 8–128 Unicode characters and are never trimmed. Successful
responses contain only the user's ID and normalized email.

The raw session token exists only in an `HttpOnly`, `SameSite=Lax`, path `/` browser
cookie. PostgreSQL stores only its SHA-256 digest. Frontend code must not copy the token
into local storage, session storage, JavaScript state, logs, or URLs. Sessions expire
after 30 days by default; activity does not extend that absolute deadline.

The following local-only curl flow uses a temporary cookie jar so curl behaves like a
browser. Run it from a shell where the backend is available on port `8000`:

```bash
curl -i -c /tmp/penny-saved-cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"email":"demo@penny-saved.local","password":"PennySavedDemo!2026"}' \
  http://127.0.0.1:8000/api/auth/login

curl -i -b /tmp/penny-saved-cookies.txt \
  http://127.0.0.1:8000/api/auth/me

curl -i -b /tmp/penny-saved-cookies.txt -c /tmp/penny-saved-cookies.txt \
  -X POST http://127.0.0.1:8000/api/auth/logout
```

The demo credentials are intentionally local-only. Delete the temporary cookie jar
when finished. Browser state-changing requests must have an `Origin` header that
exactly matches `FRONTEND_ORIGIN`; authenticated non-browser requests without an
`Origin` remain supported. Production requires an HTTPS frontend origin and secure
cookies.

### Frontend authentication workflow

Open `/signup` to create a local account or `/login` to use an existing account. Both
forms provide client-side usability checks, while the backend remains authoritative
for validation and credential verification. The password exists only in temporary
form state and the credentialed request body; the frontend does not write passwords,
session tokens, or user records to browser storage.

On every initial load or refresh, the frontend calls `/api/auth/me`. The browser sends
the `HttpOnly` session cookie automatically. A valid session restores the user directly
to protected content without requiring another login or briefly flashing the login
screen. A missing, invalid, or expired session is treated as a guest session.

The frontend route behavior is:

| Route        | Guest behavior       | Authenticated behavior |
| ------------ | -------------------- | ---------------------- |
| `/`          | Redirect to `/login` | Redirect to dashboard  |
| `/login`     | Show login form      | Redirect to dashboard  |
| `/signup`    | Show signup form     | Redirect to dashboard  |
| `/dashboard` | Redirect to `/login` | Show protected content |

When login is required for a protected route, the frontend preserves only a validated
internal return path and navigates there after successful authentication. Frontend
guards are a navigation convenience; every protected backend endpoint must still
authenticate and authorize the request.

The protected header displays the current public email and a Logout button. Logout
revokes the presented server session, clears all frontend query data, and returns to
`/login`. If a protected request discovers that the session expired, the frontend
clears private cached data, displays “Your session expired. Please sign in again,” and
returns the user to the safe original route after login.

For a ready-made local account, run `make seed-demo` and use:

```text
Email:    demo@penny-saved.local
Password: PennySavedDemo!2026
```

## Entry CRUD, Dashboard, and Check-In API

The backend provides six authenticated entry endpoints:

| Method   | Endpoint                           | Purpose                                                  |
| -------- | ---------------------------------- | -------------------------------------------------------- |
| `POST`   | `/api/entries`                     | Create a new waiting entry for the current user.         |
| `GET`    | `/api/entries`                     | Return the current user's four dashboard buckets.        |
| `GET`    | `/api/entries/{entry_id}`          | Return one entry owned by the current user.              |
| `PATCH`  | `/api/entries/{entry_id}`          | Edit an owned entry whose stored status is `waiting`.    |
| `DELETE` | `/api/entries/{entry_id}`          | Delete an owned entry whose stored status is `waiting`.  |
| `POST`   | `/api/entries/{entry_id}/check-in` | Resolve an eligible waiting entry as saved or purchased. |

Create and update bodies use `item_name`, `price_cents`, and `reason_wanted`.
`price_cents` must be a positive integer from 1 through 999,999,999,999; decimal
currency values, numeric strings, and booleans are rejected. The backend trims outer
whitespace from the two text fields and rejects blank, oversized, and unknown fields.

The list response always includes `needs_check_in`, `waiting`, `saved`, and
`purchased` arrays. `needs_check_in` is a derived dashboard bucket, not a stored
status. A waiting entry enters that bucket exactly 48 hours after creation. One
request-scoped UTC clock is used to classify the complete response.

All entry operations derive ownership from the authenticated session. A client cannot
select a trusted `user_id`, and knowing another entry's UUID does not grant access.
The API returns `403` for a known entry owned by another user and `404` for an unknown
UUID without revealing owner identity or entry fields.

Only entries whose stored status is `waiting` may be edited or deleted, including
entries displayed in `needs_check_in`. Saved and purchased entries are retained as
history and return `409 invalid_entry_status`. Successful deletion returns `204 No
Content` with an empty body. Browser POST, PATCH, and DELETE requests must also pass
the configured exact-origin check.

### Entry check-in

After the complete 48-hour waiting period, check in an entry with:

```json
{
  "result": "saved",
  "comment": "I waited and realized I did not need it."
}
```

`result` accepts only `saved` or `purchased`. `comment` is optional, is trimmed, and
is stored as `null` when omitted, empty, or whitespace-only.

The server—not the browser—checks eligibility using `created_at + 48 hours`. One
microsecond before that time returns `409 early_check_in`; exactly at the boundary
succeeds. A successful check-in changes only the status, normalized comment,
`checked_in_at`, and `updated_at`. The two timestamps use the same UTC clock value,
and later statistics use `checked_in_at` as the decision date.

Check-in locks the owned database row inside one transaction. If two requests race,
exactly one can resolve the entry; the other returns `409 invalid_entry_status`.
Already saved or purchased entries return the same lifecycle conflict and cannot be
checked in, edited, or deleted again.

The endpoint returns `403` for another user's known entry, `404` for an unknown entry,
and `422` for an invalid UUID or request body. These responses use the standard safe
error envelope without revealing owner data. Browser requests must be authenticated
and pass the configured exact-origin check.

The protected frontend route `/entries/{entry_id}/check-in` displays the original
item, price, reason, and server-provided timing context. The user must explicitly
choose “I did not buy it” or “I bought it” and may add an optional reflection. The
frontend does not calculate eligibility. It waits for the server response, shows the
confirmed saved or purchased result, and refreshes entry, dashboard, and statistics
caches. Early or stale conflicts refresh server truth, retryable failures preserve
the form values, and expired sessions retain the complete check-in return path.

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
- Login, signup, dashboard entry lists, entry management, and the complete check-in
  experience are implemented. Statistics screens arrive in later development tasks.

### Browser smoke tests

Vitest and MSW test frontend units and components in a simulated browser and may mock
HTTP responses. Playwright smoke tests use a real pinned Chromium browser. The
completed smoke suite will connect the built frontend to live FastAPI and PostgreSQL;
its initial contract test deliberately uses a controlled in-browser fixture and does
not start or contact the product stack.

Install the pinned browser runtime after `npm ci`, then inspect or run the contract:

```bash
npm --prefix frontend exec playwright install chromium
npm --prefix frontend run e2e:list
npm --prefix frontend run e2e:contract
```

Browser-test URLs default to loopback addresses and can be set with
`E2E_FRONTEND_URL` and `E2E_BACKEND_URL`. The runner rejects non-loopback targets and
the production origin. Later live-stack commits will also require an isolated
`E2E_DATABASE_URL`, unique `E2E_RUN_ID`, `E2E_EMAIL_DOMAIN`, and ephemeral
`E2E_PASSWORD`. Failure screenshots and traces go under `frontend/test-results/` and
are ignored by Git.

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

## Deterministic local demo data

After first-time installation, start PostgreSQL, apply migrations, seed the local demo
dataset, and start the application:

```bash
make db-up
make db-upgrade
make seed-demo
make dev
```

The local-only demo credentials are:

```text
Email:    demo@penny-saved.local
Password: PennySavedDemo!2026
```

Never reuse these credentials in staging, production, a shared environment, or a real
account. After DEV-008, they can be used with the local authentication API and the
frontend authentication screens added by DEV-009.

`make seed-demo` creates or restores one known demo user, nine representative
impulse-purchase entries, and three opportunity-cost examples. It is safe to repeat:
stable UUIDs identify the known records, repeated runs reconcile them instead of
creating duplicates, and manually created or unrelated-user records are preserved. The
entire seed runs in one transaction, so a failure rolls back all of its changes.

After a successful run, the command prints a summary of the safety and migration checks
it completed, the records and edge-case states it reconciled, its repeat behavior, and
the UTC seed time. It also repeats the clearly labeled local-only demo email and
password for convenience; it never prints a password hash or database credential.
Seeding does not execute the automated test suite; run `make check` separately when
code-quality and test verification are required.

The command intentionally does not start PostgreSQL, apply migrations, install
dependencies, or reset data. Before connecting, it refuses production and permits only
a loopback development PostgreSQL target or an explicit test database ending in
`_test`. Before writing, it requires the database's applied Alembic heads to exactly
match the checked-out migration heads.

### Demo-seed troubleshooting

- `Missing backend/.env` or a settings validation error means local backend
  configuration is unavailable. Run `make env-setup` and review the placeholders.
- A connection failure means PostgreSQL is stopped or `DATABASE_URL` has the wrong
  host, port, username, password, or database. Run `make db-up`, inspect
  `docker compose ps`, and compare the environment files.
- A loopback, `_test`, or production refusal means the configured target does not meet
  the seed safety rules. Do not bypass the guard; correct the intended local
  configuration.
- `database is not at the current Alembic head` means migrations are missing or differ
  from the checked-out code. Run `make db-upgrade` and retry.
- A demo UUID or email collision means a stable demo identity belongs to an unrelated
  record. The command stops instead of taking it over. Inspect the local database and
  deliberately resolve the collision or reset disposable local data with
  `make db-reset`.

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

| Required job | Local equivalent                    | Additional CI responsibility                                  |
| ------------ | ----------------------------------- | ------------------------------------------------------------- |
| `frontend`   | Frontend stages of `make check`     | Clean Node.js install and production build                    |
| `backend`    | Backend stages of `make check`      | Clean Python install and ephemeral PostgreSQL tests           |
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
