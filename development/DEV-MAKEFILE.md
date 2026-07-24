# Make Command Reference

Run these commands from the repository root:

```text
make <target>
```

Running `make` without a target is the same as running `make help`.

## Setup and Installation

### `make help`

Prints the usage message and lists the user-facing Make targets with a short description
of each one. This is also the default target.

**When to run it:** Run it whenever you need to look up an available command. It is safe
to run repeatedly and is not a one-time command.

### `make env-setup`

Creates missing local environment files by copying the committed examples:

| Source | Destination |
|---|---|
| `.env.example` | `.env` |
| `backend/.env.example` | `backend/.env` |
| `frontend/.env.example` | `frontend/.env` |

Existing destination files are preserved and never overwritten. Review any placeholder
values after the files are created.

**When to run it:** Run it once when setting up a new checkout, or later if one of the
three local environment files is missing. It is safe to run repeatedly because it keeps
existing files unchanged.

### `make install`

Installs all backend and frontend dependencies by running `make backend-install` and
`make frontend-install`.

**When to run it:** Run it during initial project setup. Run it again after pulling
changes to either dependency file, after deleting `.venv` or `frontend/node_modules`, or
when dependencies appear out of date. It is not limited to one run.

### `make backend-install`

Checks that Python 3.12 or newer is available, creates the root `.venv` virtual
environment if it does not already exist, upgrades `pip`, and installs the pinned
development dependencies from `backend/requirements-dev.txt`.

Set `PYTHON` to select a different Python executable:

```text
make backend-install PYTHON=python3.12
```

**When to run it:** Run it during initial backend setup, after
`backend/requirements-dev.txt` changes, or after deleting or recreating `.venv`. It can
be run repeatedly; an existing virtual environment is reused and its packages are
brought in line with the requirements file.

### `make frontend-install`

Checks that Node.js 22 and `npm` are available, then runs `npm ci` in the `frontend`
directory. `npm ci` installs the exact dependency versions recorded in
`frontend/package-lock.json`.

**When to run it:** Run it during initial frontend setup, whenever
`frontend/package-lock.json` changes, or when a clean reinstall of frontend dependencies
is needed. It is safe to run repeatedly; `npm ci` recreates the installed dependency
tree from the lockfile.

## Quality Commands and Continuous Integration

These commands provide one root interface for frontend and backend development and
quality checks.

GitHub Actions continuous-integration jobs are added later in DEV-006. As those jobs and
any additional Make commands are completed, this section must be updated to keep the
local and CI workflows aligned.

### `make check`

Validates both the frontend and backend through one command. It runs:

```text
format-check → lint → typecheck → test → build
```

The command stops at the first failing stage. It does not install or update
dependencies. The backend test stage requires the dedicated PostgreSQL test database.

**When to run it:** Run it before committing, pushing, or opening a pull request. Run it
again after resolving a failure. It is the primary local quality gate and is safe to run
repeatedly.

### `make clean`

Removes only known generated build, coverage, bytecode, TypeScript metadata, Pytest
cache, and Ruff cache artifacts. It preserves source code, tests, migrations, `.env`
files, `.venv`, `frontend/node_modules`, Docker resources, and PostgreSQL data.

**When to run it:** Run it when generated output or caches may be stale, before testing
a clean rebuild, or when reclaiming space used by replaceable artifacts. It is safe to
run repeatedly and is not required during every development session.

### `make dev`

Checks prerequisites, starts and health-checks PostgreSQL, applies pending Alembic
migrations, then supervises the Vite frontend and FastAPI backend concurrently.
Pressing `Ctrl+C` stops both application servers and waits for them to exit. PostgreSQL
continues running and its named volume remains intact; use `make db-down` separately
when you want to stop it.

**When to run it:** Run it at the start of a normal full-application development session
after completing first-time installation and environment configuration. It can be run
for every development session and is not limited to one use.

## Local PostgreSQL

These commands require Docker Engine, Docker Compose v2, and a root `.env` file. Run
`make env-setup` first if the environment file is missing.

### `make db-up`

Starts the PostgreSQL service in the background and waits up to 60 seconds for its health
check to pass.

**When to run it:** Run it at the start of a development session before using backend
features or tests that need PostgreSQL. It can be run again if the service is already
running; it is a routine command, not a one-time setup step.

### `make db-down`

Stops and removes the Docker Compose containers and network. It preserves the named
PostgreSQL data volume, so the database data remains available the next time
`make db-up` runs.

**When to run it:** Run it when you finish database-backed development, want to free the
container's resources, or need to stop and recreate the container. It may be used after
every development session, but stopping the database is optional.

### `make db-logs`

Follows the PostgreSQL container logs. The command continues running and displaying new
log entries until it is interrupted, usually with `Ctrl+C`.

**When to run it:** Run it while diagnosing startup, connection, health-check, or query
problems, or whenever you want to observe database activity. It is an on-demand
diagnostic command and can be run as often as needed.

### `make db-reset`

Deletes and recreates the local PostgreSQL data volume. This permanently removes the
data stored in that local database.

The command:

1. Refuses to run in CI.
2. Verifies that the configuration points to a local development database.
3. Requires the exact confirmation word `reset`.
4. Stops the Compose services.
5. Deletes only the `penny_saved_postgres_data` volume.
6. Starts a fresh PostgreSQL service with `make db-up`.

**When to run it:** Run it only when you intentionally need a completely empty local
database, such as after disposable test data becomes unusable or local schema state
cannot be repaired normally. It is not an initial-setup requirement or a routine
command. Avoid it when the local data must be preserved.

## Database Migrations

Migration commands require the root `.venv`, `backend/.env`, and
`backend/alembic.ini`. Run `make backend-install` and `make env-setup` first. If the
Alembic configuration has not yet been added, these commands stop with an explanatory
message.

### `make db-upgrade`

Runs `alembic upgrade head` from the `backend` directory to apply every pending database
migration.

**When to run it:** Run it after `make db-up` during initial database setup, after pulling
new migration files, or after creating and reviewing a new migration. It is safe to run
repeatedly; when the database is already at the latest revision, Alembic has no pending
migrations to apply.

### `make db-downgrade`

Runs `alembic downgrade -1` to revert one migration.

Before changing the database, it verifies that the configuration points to a local
development database and requires the exact confirmation word `downgrade`.

**When to run it:** Run it only when testing a migration's rollback or intentionally
returning the local schema to the immediately previous revision. It is not part of
normal startup and may discard schema or data changes made by the reverted migration.

### `make db-revision message="description"`

Autogenerates a new Alembic migration using the supplied description as its revision
message. For example:

```text
make db-revision message="add_savings_goals"
```

The command verifies that the configuration points to a local development database and
fails if `message` is empty. Autogenerated migrations must be reviewed before they are
applied or committed.

**When to run it:** Run it once for each intentional database-model or schema change that
needs a new migration. Do not run it during routine startup, and do not generate a second
revision for the same change unless the first revision is deliberately being replaced.

## Internal Prerequisite Targets

The following targets support the commands above. They can be invoked directly, but are
normally run automatically as prerequisites.

### `make check-docker`

Checks that Docker, Docker Compose v2, and the root `.env` file are available. It is a
prerequisite of `db-up`, `db-down`, `db-logs`, and `db-reset`.

**When to run it:** Usually never run it directly because the database targets invoke it
automatically every time. Run it manually only to verify the Docker prerequisites
without starting or stopping anything.

### `make check-alembic`

Checks that the virtual environment's Python executable, `backend/.env`, and
`backend/alembic.ini` are available. It is a prerequisite of `db-upgrade`,
`db-downgrade`, and `db-revision`.

**When to run it:** Usually never run it directly because the migration targets invoke
it automatically every time. Run it manually only to check migration prerequisites
without changing the database.
