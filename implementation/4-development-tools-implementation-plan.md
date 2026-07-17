# Development Tools Implementation Plan

## Purpose

This document defines the repeatable developer and operational workflow for A Penny Saved. It turns the tooling choices in `SYS-006` into exact commands and boundaries. The Makefile is the primary cross-platform entry point: contributors should not need to remember long npm, Python, Alembic, Docker, or deployment commands.

This plan covers local development, automated quality checks, database migrations, CI, and the operational handoff to the Oracle Cloud VPS. It does not provision cloud infrastructure or deploy the application.

## Toolchain Baseline

| Concern | Tool |
|---|---|
| JavaScript runtime/package manager | Node.js 22 LTS and npm |
| Python runtime/environment | Python 3.12+ and `.venv` |
| Frontend | Vite, TypeScript, ESLint, Prettier, Vitest |
| Backend | FastAPI, Ruff, Pytest, Alembic |
| Local database | PostgreSQL 16 in Docker Compose |
| Containers | Docker Engine with Docker Compose v2 |
| CI | GitHub Actions |
| Production compute | Oracle Cloud VPS |
| Transactional email | Amazon Web Services |

Exact dependency versions are pinned through `frontend/package-lock.json` and backend requirements files. Keep Node and Python version declarations in `.nvmrc` and `.python-version` respectively, or document their versions in the root README if those version-manager files are not adopted.

## Repository Files

```text
Makefile
.env.example
.gitignore
compose.yaml
frontend/
  package.json
  package-lock.json
  .env.example
backend/
  requirements.txt
  requirements-dev.txt
  pyproject.toml
  .env.example
  alembic.ini
.github/workflows/ci.yml
scripts/
  deploy.sh                 # added only when production deployment is implemented
```

Use `compose.yaml`, not a deprecated `docker-compose.yml`. It supplies only local development dependencies—initially PostgreSQL—not frontend or backend application containers. Running the applications directly preserves fast Vite reload and simple Python debugging.

## Environment Configuration

Never commit real `.env` files, credentials, database dumps, or generated TLS keys. Commit examples with non-secret placeholders.

### Root `.env.example`

```dotenv
POSTGRES_DB=penny_saved
POSTGRES_USER=penny_saved
POSTGRES_PASSWORD=change-me-for-local-development
POSTGRES_PORT=5432
```

Docker Compose reads these values. A developer copies the file to `.env` and changes the local password before first use.

### `backend/.env.example`

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://penny_saved:change-me-for-local-development@localhost:5432/penny_saved
FRONTEND_ORIGIN=http://localhost:5173
SESSION_COOKIE_NAME=penny_saved_session
SESSION_TTL_SECONDS=2592000
SESSION_COOKIE_SECURE=false
LOG_LEVEL=INFO
```

The backend settings loader reads `backend/.env` only in local development. Tests override all database and security settings rather than using a developer's `.env`.

### `frontend/.env.example`

```dotenv
VITE_API_BASE_URL=/api
```

Vite's development proxy forwards `/api` to `http://localhost:8000`. This preserves cookie behavior and avoids CORS complexity locally. Browser-exposed `VITE_*` values are public configuration; never put a secret in them.

### Production configuration

Production values are supplied through the Oracle VPS service manager or a root-readable environment file outside the repository. At minimum:

```dotenv
APP_ENV=production
DATABASE_URL=postgresql+psycopg://...
FRONTEND_ORIGIN=https://stopimpulsebuying.us
SESSION_COOKIE_SECURE=true
```

AWS email credentials, sender address, and AWS region are added only when email functionality is implemented. Use a narrowly scoped IAM identity, store credentials outside Git, and rotate them according to the AWS account policy.

## Local Database Workflow

`compose.yaml` defines one `postgres` service:

- Image: `postgres:16`.
- Persistent named volume: `penny_saved_postgres_data`.
- Port bound to `127.0.0.1:\${POSTGRES_PORT:-5432}`; do not expose it on all network interfaces.
- Health check uses `pg_isready`.
- Database, user, and password come from root `.env`.

The application starts only after the database health check succeeds. Migrations are run from the backend virtual environment, never automatically by the PostgreSQL container.

Use a separate test database such as `penny_saved_test`. Test setup creates/drops or transaction-isolates this database under an explicit `TEST_DATABASE_URL`; it must never infer or reuse the development/production URL.

## Makefile Contract

The Makefile must use `.DEFAULT_GOAL := help`, declare every target `.PHONY`, and fail fast with Bash strict mode where shell recipes are needed. Keep recipes short; move multi-step logic into versioned scripts only when it cannot be read comfortably in the Makefile.

Target behavior:

| Target | Behavior |
|---|---|
| `make help` | Lists documented targets and one-line descriptions. |
| `make install` | Creates `.venv`, installs backend dev dependencies, and runs `npm ci` in `frontend/`. |
| `make frontend-install` | Runs `npm ci` in `frontend/`. |
| `make backend-install` | Creates/reuses `.venv` and installs backend dev dependencies. |
| `make db-up` | Starts local PostgreSQL with `docker compose up -d postgres` and waits for health. |
| `make db-down` | Stops the local PostgreSQL container without deleting its volume. |
| `make db-logs` | Follows PostgreSQL logs. |
| `make db-reset` | Stops the database and deletes only the named local development volume after an explicit confirmation prompt. Never run this in CI or production. |
| `make db-upgrade` | Runs `alembic upgrade head` using backend configuration. |
| `make db-downgrade` | Runs `alembic downgrade -1`; it is a local-development command only. |
| `make db-revision message=\"...\"` | Creates an Alembic revision; autogeneration is reviewed, never blindly accepted. |
| `make frontend-dev` | Runs the Vite development server. |
| `make backend-dev` | Runs the FastAPI development server on port 8000 with reload enabled. |
| `make dev` | Starts local dependencies, applies migrations, then runs frontend and backend dev servers concurrently with signal cleanup. |
| `make frontend-test` | Runs the Vitest suite once. |
| `make backend-test` | Runs Pytest against the explicit test database. |
| `make test` | Runs frontend and backend tests. |
| `make frontend-lint` | Runs ESLint. |
| `make backend-lint` | Runs `ruff check`. |
| `make lint` | Runs both lint targets. |
| `make frontend-format-check` | Runs Prettier in check mode. |
| `make backend-format-check` | Runs `ruff format --check`. |
| `make format-check` | Runs both formatting checks. |
| `make format` | Applies Prettier and Ruff formatting. |
| `make frontend-typecheck` | Runs `tsc --noEmit`. |
| `make typecheck` | Runs frontend type checking and backend static checks if configured. |
| `make build` | Builds the production frontend and validates backend import/startup configuration without launching a server. |
| `make check` | Runs format check, lint, typecheck, tests, and build in that order. |
| `make clean` | Removes only generated frontend build/test artifacts and Python cache directories. It must not remove `.venv`, `.env`, Docker volumes, migrations, or source files. |

`make dev` requires a process runner such as `concurrently` or a small committed shell script. It must forward Ctrl-C/SIGTERM to both child processes and wait for them to exit, so it never leaves a server listening in the background.

The Makefile must check for required commands (`docker`, `node`, `npm`, and Python) and provide actionable errors. It must not install Docker, Node, system Python, or operating-system packages automatically.

## First-Run Workflow

```text
1. Install Docker, Node.js 22 LTS, Python 3.12+, and GNU Make.
2. Copy .env.example to .env; backend/.env.example to backend/.env; frontend/.env.example to frontend/.env.
3. Change local database password placeholders.
4. Run make install.
5. Run make db-up.
6. Run make db-upgrade.
7. Run make dev.
8. Open http://localhost:5173.
```

`make dev` may perform steps 5–6 automatically after the developer has completed installation and configuration, but it must show which commands it runs and stop if migration fails.

## Quality Configuration

### Frontend

- TypeScript uses strict mode, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.
- ESLint checks TypeScript, React hooks, and import hygiene.
- Prettier owns source formatting; ESLint must not duplicate formatting rules.
- Vitest runs in a browser-like environment with React Testing Library and MSW.
- `npm ci` is mandatory in CI; use `npm install` only when intentionally changing dependencies and lockfile.

### Backend

- `pyproject.toml` owns Ruff and Pytest configuration.
- Ruff checks lint rules and formats Python; CI uses `ruff check .` and `ruff format --check .`.
- Pytest uses `asyncio_mode = auto` or explicit async markers consistently.
- Alembic migration tests run against PostgreSQL, not SQLite.
- Dependency constraints are reviewed and pinned; production installs runtime requirements only.

## Continuous Integration

GitHub Actions runs on pull requests and pushes to the default branch. Use separate jobs so failures are easy to identify:

| Job | Required checks |
|---|---|
| `frontend` | npm cache, `npm ci`, format check, lint, typecheck, test, production build |
| `backend` | Python dependency cache, install, Ruff format check, Ruff lint, Pytest |
| `migrations` | PostgreSQL service container, Alembic upgrade head, downgrade/re-upgrade test, Alembic drift check |

CI uses an ephemeral PostgreSQL service with dedicated test credentials. Repository secrets are not available to pull requests from forks, and CI never needs production Oracle, AWS, or SMTP credentials.

The required merge gate is `make check` behavior distributed across the above jobs. Add dependency scanning and a scheduled dependency-update workflow after the initial application foundation is stable.

## Migration Workflow

1. Change SQLAlchemy models and any required repository/schema behavior.
2. Run `make db-revision message=\"describe_change\"`.
3. Review the migration SQL, names, downgrade, data safety, and indexes.
4. Run `make db-upgrade`.
5. Run relevant tests and the migration CI sequence.
6. Commit the model, migration, and tests together.

Never modify an applied migration. Do not run `db-downgrade` against shared staging/production databases. Production deployment only runs forward migrations after a verified backup.

## Oracle VPS Operations Boundary

Production runs on the Oracle Cloud VPS behind a reverse proxy that terminates TLS for `stopimpulsebuying.us`. The reverse proxy serves the built frontend assets and proxies `/api` to the FastAPI process over the VPS loopback network. PostgreSQL listens only on localhost or a private container/network interface and is never publicly exposed.

The eventual deployment workflow must:

1. Create a database backup and verify available disk space.
2. Fetch a specific, reviewed Git revision or immutable artifact.
3. Install locked dependencies/build frontend assets.
4. Run `alembic upgrade head`.
5. Restart the application service with a health check.
6. Verify `https://stopimpulsebuying.us/api/health` and browser access.
7. Retain the prior release artifact for rollback; database rollback is a separate, reviewed decision.

Use a non-root deployment account. Application processes run under `systemd` or an equivalent supervisor and restart on failure. Firewall rules expose only SSH (restricted where possible), HTTP, and HTTPS. SSH uses keys, not passwords.

No `make deploy` target is included initially: deployment changes production state and require an explicit, reviewed release procedure. Add a deployment target only after the server configuration, backup/rollback procedure, and secret delivery mechanism are implemented and tested.

## AWS Transactional Email Boundary

Amazon AWS is the transactional email provider when an email-dependent feature exists, such as password reset or account notifications. The application will use Amazon SES through its supported AWS SDK/client library.

- Verify `stopimpulsebuying.us` and configure DKIM/SPF/DMARC before sending production email.
- Keep SES credentials in Oracle VPS secret configuration, never frontend variables or the repository.
- Use a restricted IAM policy that permits only required SES actions and identities.
- Log message correlation IDs and delivery failures without logging email bodies, reset tokens, or credentials.
- Add a sandbox/development email strategy before writing integration tests; tests must mock the provider.

## Documentation and Support Rules

- Root README explains prerequisites, first-run steps, common commands, and troubleshooting links.
- Each Make target shown to contributors has a concise `make help` description.
- `.env.example` files document every variable, default, and whether it is secret.
- Production runbook documents backup, restore, deploy, rollback, log access, TLS renewal, and incident contacts separately from source-controlled application code.
- Tooling changes that alter commands or prerequisites update this document, the README, and CI together.

## Acceptance Checklist

- A new developer can start the application from a clean machine using the documented workflow.
- `make check` succeeds locally and CI executes its equivalent checks.
- The test suite cannot connect to development or production databases by accident.
- Local database data persists across `db-down`/`db-up` and only `db-reset` can remove it.
- No development command writes secrets into tracked files.
- Migrations are forward-only in shared environments and are tested with PostgreSQL.
- Production design keeps the database private, uses HTTPS, and has a documented backup-before-migration sequence.
- AWS email credentials and production deployment actions remain outside normal local Make targets.
