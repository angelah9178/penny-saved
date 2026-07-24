# DEV-006 — Add Quality Commands and Continuous Integration

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Commit 1 — Add the Root Quality Command Interface](#commit-1--add-the-root-quality-command-interface)
- [Commit 2 — Add Guarded Generated-Artifact Cleanup](#commit-2--add-guarded-generated-artifact-cleanup)
- [Commit 3 — Add the Coordinated Local Development Command](#commit-3--add-the-coordinated-local-development-command)
- [Commit 4 — Add Frontend and Backend Continuous Integration](#commit-4--add-frontend-and-backend-continuous-integration)
- [Commit 5 — Add PostgreSQL Migration Continuous Integration](#commit-5--add-postgresql-migration-continuous-integration)
- [Commit 6 — Document and Verify the Completed Quality Workflow](#commit-6--document-and-verify-the-completed-quality-workflow)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)
  - [Overview](#overview)
  - [What It Achieved](#what-it-achieved)
  - [Local and CI Equivalence](#local-and-ci-equivalence)
  - [Verification](#verification)
  - [Limitations and Follow-up](#limitations-and-follow-up)

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|  | Commit | Title | Depends on |
|---|---|---|---|
| &#91;x&#93; | [1](#commit-1--add-the-root-quality-command-interface) | Add root quality commands | — |
| &#91; &#93; | [2](#commit-2--add-guarded-generated-artifact-cleanup) | Add safe generated-artifact cleanup | Commit 1 |
| &#91; &#93; | [3](#commit-3--add-the-coordinated-local-development-command) | Add coordinated local development | Commit 1 |
| &#91; &#93; | [4](#commit-4--add-frontend-and-backend-continuous-integration) | Add frontend and backend CI jobs | Commit 1 |
| &#91; &#93; | [5](#commit-5--add-postgresql-migration-continuous-integration) | Add PostgreSQL migration CI | Commit 4 |
| &#91; &#93; | [6](#commit-6--document-and-verify-the-completed-quality-workflow) | Document DEV-006 quality and CI workflow | Commits 1–5 |

## Objective

Give contributors and continuous integration one clear, reproducible interface for
installing, running, checking, building, and safely cleaning the application. DEV-006
completes the root Makefile with focused frontend and backend targets, combines the
required checks behind `make check`, adds a coordinated development command that cleans
up both servers correctly, and runs the equivalent quality and migration checks in
GitHub Actions.

The local commands and CI jobs must enforce the same standards:

```text
format check
    ↓
lint
    ↓
typecheck
    ↓
tests
    ↓
production build and backend startup validation
```

Migration verification adds a separate PostgreSQL-backed sequence:

```text
empty PostgreSQL database
    ↓
upgrade to Alembic head
    ↓
downgrade to base
    ↓
re-upgrade to head
    ↓
verify model and migration metadata do not drift
```

Complete and commit each section in order. Every commit must preserve the existing
frontend, backend, and database checks before work begins on the next commit. Run the
new combined commands from the repository root. CI must use only ephemeral test
configuration and must not require production secrets.

## Commit 1 — Add the Root Quality Command Interface

The repository already has working quality tools in each application workspace, but a
contributor currently needs to remember which commands run from `frontend/`, which run
from `backend/`, and which Python executable belongs to the root virtual environment.
This commit makes the root Makefile the stable interface for those operations.

In plain language, Commit 1 creates one `make check` command that validates both the
frontend and backend. This simplifies the complete project-quality check into one
command run from the repository root.

The Make targets remain small wrappers around the tools that own each check:

```text
Root Make target       Frontend or backend tool
────────────────────   ──────────────────────────
frontend-format-check  Prettier check
backend-format-check   Ruff format check
frontend-lint          ESLint
backend-lint           Ruff lint
frontend-typecheck     TypeScript compiler
frontend-test          Vitest
backend-test           Pytest
build                  Vite build + backend validation
```

Keeping focused targets makes failures easy to reproduce. A developer can run
`make frontend-lint` after an ESLint failure without repeating unrelated work, while
`make lint`, `make test`, and `make check` provide progressively broader gates.

`make check` is the complete local acceptance command. Its order is deliberate: quick,
non-mutating formatting and lint failures appear before longer tests and builds. The
command must stop at the first failure and return that failure to the caller.

Backend tests include the PostgreSQL integration suite and therefore require an explicit
`TEST_DATABASE_URL`. The Makefile must not invent a test database URL from
`DATABASE_URL`, silently switch to SQLite, or point integration tests at the development
database. The existing test-database safety checks remain the enforcement boundary.

Suggested commit message:

```text
Add root quality commands
```

Implement:

- Extend `.PHONY` to cover every new public and supporting target.
- Add `frontend-test`, `backend-test`, and combined `test` targets.
- Add `frontend-lint`, `backend-lint`, and combined `lint` targets.
- Add `frontend-format`, `backend-format`, and combined `format` targets.
- Add `frontend-format-check`, `backend-format-check`, and combined
  `format-check` targets.
- Add `frontend-typecheck` and combined `typecheck` targets; do not claim a backend type
  checker exists unless one is deliberately configured.
- Add a root `build` target that runs the production frontend build and validates that
  the backend application can be imported and constructed with explicit safe test
  configuration without starting a long-running server.
- Add `check` in the documented order: `format-check`, `lint`, `typecheck`, `test`, then
  `build`.
- Reuse the pinned root virtual environment and the locked frontend installation; do not
  download dependencies as a side effect of a quality target.
- Give each public target a concise `make help` description.
- Add focused Makefile contract tests or a lightweight validation script for target
  presence, ordering, working directories, and failure propagation where shell-level
  behavior cannot be proven reliably by inspection.

Commit gate:

```text
make format-check
make lint
make typecheck
make test
make build
make check
git diff --check
```

## Commit 2 — Add Guarded Generated-Artifact Cleanup

Cleanup is useful when stale build output or caches affect a local result, but a broad
recursive deletion command can destroy source code, local configuration, dependencies,
migrations, or database data. This commit adds a deliberately narrow `make clean`
contract.

Only known generated application artifacts are eligible for removal. Typical targets
include frontend build and coverage output, Python bytecode, Pytest and Ruff caches,
TypeScript incremental build metadata, and tool caches owned by this repository.

The command must preserve:

- All application source and tests.
- Alembic configuration and every migration revision.
- `.env` files and committed `.env.example` templates.
- The root `.venv` and `frontend/node_modules`.
- Dependency manifests and lock files.
- Docker containers, networks, named volumes, and database contents.
- Git metadata and development documentation.

The implementation must use explicit repository-relative paths and narrowly matched
generated directory names. It must not use an unresolved environment variable, a broad
workspace wildcard, or a recursive deletion rooted at the repository, home directory,
or filesystem root.

Suggested commit message:

```text
Add safe generated artifact cleanup
```

Implement:

- Add `make clean` with a `make help` description that states it removes generated
  artifacts only.
- Prefer a small versioned cleanup script if the safe path validation and cache
  traversal would be unreadable in the Makefile.
- Resolve the repository root before deletion and reject targets outside it.
- Remove only enumerated build, coverage, bytecode, and tool-cache artifacts.
- Make repeated cleanup safe when none of the artifacts exist.
- Add automated tests that create disposable representative artifacts and prove cleanup
  removes them.
- Add negative tests proving source, tests, migrations, environment files, `.venv`,
  `node_modules`, and a sentinel representing database data remain untouched.

Commit gate:

```text
make clean
make clean
make check
git diff --check
git status --short
```

## Commit 3 — Add the Coordinated Local Development Command

The frontend and backend are separate long-running processes. A root `make dev` command
must start the required local database, apply migrations, and run both servers without
leaving one behind when the other exits or the developer presses `Ctrl+C`.

The intended startup flow is:

```text
make dev
    ├── verify local prerequisites and configuration
    ├── start and health-check PostgreSQL
    ├── apply migrations to the local development database
    └── supervise
        ├── FastAPI/Uvicorn on 127.0.0.1:8000
        └── Vite on localhost:5173
```

Process supervision is the critical behavior in this commit. The coordinator owns both
child processes, forwards `SIGINT` and `SIGTERM`, terminates the remaining child if
either server exits, waits for cleanup, and returns a useful nonzero status when startup
or a server fails. PostgreSQL data remains persistent; stopping `make dev` must not
delete its volume.

The focused `frontend-dev` and `backend-dev` targets remain available when a contributor
wants to run the servers in separate terminals. They must use the repository's pinned
tooling and documented application factory.

Suggested commit message:

```text
Add coordinated local development command
```

Implement:

- Add `frontend-dev` using the frontend Vite development script.
- Add `backend-dev` using the root virtual environment's Uvicorn executable, the FastAPI
  application factory, reload mode, and the documented backend working directory.
- Add a small committed process-supervision script for `make dev`.
- Have `make dev` run the guarded database startup and migration workflow before
  launching application servers.
- Fail before launching servers when dependencies, configuration, PostgreSQL health, or
  migrations are unavailable.
- Forward `SIGINT` and `SIGTERM` to both server process groups.
- Stop and reap the remaining server when either child exits.
- Preserve the PostgreSQL container and named data volume when the application processes
  stop.
- Add process-level tests with short-lived fake children that verify normal startup,
  early failure, signal forwarding, sibling termination, exit-status propagation, and
  the absence of orphan processes without opening real development servers.

Commit gate:

```text
make help
pytest tests/tooling
make check
git diff --check
```

Manually verify `make dev` with local PostgreSQL available:

```text
make dev
# Wait for both servers, then press Ctrl+C.
# Confirm neither Uvicorn nor Vite remains running.
```

## Commit 4 — Add Frontend and Backend Continuous Integration

Continuous integration runs the repository's quality gates in a clean environment on
every pull request and every push to the default branch. Separate frontend and backend
jobs make ownership and failures obvious while allowing independent checks to run in
parallel.

The jobs reproduce the checked-in runtime baselines:

| Job | Environment | Checks |
|---|---|---|
| `frontend` | Node.js from `.nvmrc` with npm cache | locked install, format check, lint, typecheck, tests, production build |
| `backend` | Python from `.python-version` with pip cache and PostgreSQL service | pinned development install, Ruff format check, Ruff lint, Pytest |

The backend suite now contains PostgreSQL integration tests, so its CI job needs an
ephemeral PostgreSQL service and an explicit `_test` database URL. It must never use
SQLite as a substitute. Service health checks must establish readiness rather than
depending on a fixed sleep.

Caching may accelerate dependency installation, but lock files remain authoritative.
The frontend always uses `npm ci`; the backend installs the pinned requirement files.
Caches must not contain repository secrets or replace installation and validation.

Suggested commit message:

```text
Add frontend and backend CI jobs
```

Implement:

- Add one GitHub Actions quality workflow triggered by pull requests and pushes to the
  default branch.
- Grant only the read permissions required to check out and test repository contents.
- Add concurrency cancellation for an older in-progress run of the same pull request or
  branch without coupling unrelated refs.
- Add a `frontend` job using the exact supported Node.js version and npm's
  `frontend/package-lock.json` cache dependency.
- Run `npm ci`, Prettier check, ESLint, TypeScript checking, Vitest, and the production
  build in the frontend job.
- Add a `backend` job using the supported Python baseline and pip caching keyed by the
  pinned backend requirement files.
- Provide an ephemeral PostgreSQL 16 service with dedicated non-production test
  credentials and a health check.
- Install the pinned backend development requirements and run Ruff formatting, Ruff
  lint, and the complete Pytest suite with explicit `APP_ENV=test`, `DATABASE_URL`, and
  `TEST_DATABASE_URL` values.
- Keep all test configuration inside the workflow; do not require repository,
  environment, cloud, email, or production database secrets.
- Set reasonable job timeouts and use readable job and step names so they can become
  required branch checks.
- Validate the workflow syntax and add static contract coverage for triggers,
  permissions, versions, locked installs, caches, PostgreSQL, and required commands.

Commit gate:

```text
make check
git diff --check
git status --short
```

After pushing the commit, verify both GitHub Actions jobs complete successfully on the
branch before marking this commit complete.

## Commit 5 — Add PostgreSQL Migration Continuous Integration

Application tests prove behavior at the current schema, while the migration job proves
that a database can be constructed and moved through the committed Alembic history. It
is kept separate from the backend job so migration failures are visible as their own
required merge check.

This job starts from a fresh PostgreSQL 16 service and verifies:

1. `alembic upgrade head` constructs the current schema.
2. `alembic downgrade base` reverses the complete migration history.
3. A second `alembic upgrade head` reconstructs the schema.
4. `alembic check` reports no model-to-migration drift.
5. The PostgreSQL migration integration tests pass against the ephemeral test database.

The reverse cycle is a CI verification technique, not authorization to downgrade a
shared or production database. The workflow calls Alembic directly with explicit test
configuration rather than using the interactive, local-development-only
`make db-downgrade` target.

Suggested commit message:

```text
Add PostgreSQL migration CI
```

Implement:

- Add a separate `migrations` job to the quality workflow.
- Use the same supported Python version, pinned dependencies, pip caching, PostgreSQL 16
  service configuration, and service health check as the backend job.
- Supply explicit test-only `APP_ENV`, `DATABASE_URL`, and `TEST_DATABASE_URL` values;
  ensure database names satisfy the existing integration-test safety guards.
- Start from an empty database and run upgrade, downgrade, re-upgrade, and drift checks
  in explicit visible steps.
- Run the focused migration and schema integration tests needed to verify constraint,
  index, cascade, revision-cycle, and metadata behavior.
- Confirm no step depends on a developer `.env` file or any GitHub secret.
- Extend workflow contract tests to protect the PostgreSQL version, migration sequence,
  drift check, and absence of SQLite.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/integration/test_database_schema.py tests/integration/test_migrations.py
../.venv/bin/python -m alembic downgrade base
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic check
cd ..
make check
git diff --check
```

After pushing the commit, verify the frontend, backend, and migrations jobs all complete
successfully before marking this commit complete.

## Commit 6 — Document and Verify the Completed Quality Workflow

This final commit makes the new command surface discoverable and records the equivalence
between local checks and required CI jobs. It does not add another quality tool. It
verifies that the earlier commits form one understandable development and merge
workflow.

Suggested commit message:

```text
Document DEV-006 quality and CI workflow
```

Implement:

- Update the root README with the root install, development, focused quality, complete
  check, cleanup, and troubleshooting commands.
- Document which commands need PostgreSQL and the explicit dedicated test-database
  configuration.
- Document how `make dev` starts dependencies and migrations, how it handles
  termination, and how to run the two servers separately.
- Document exactly what `make clean` removes and the source, environment, dependency,
  migration, and database data it preserves.
- Add or update the Make command reference so every public target matches `make help`
  and its implemented behavior.
- Map `make check` stages to the frontend, backend, and migrations GitHub Actions jobs.
- Identify the exact stable job names intended to be required merge checks; note that
  repository branch-protection configuration is an administrator action outside the
  code change.
- Record the completed DEV-006 implementation, verification results, limitations, and
  follow-up work in this document.
- Mark DEV-006 complete in `development/0-development-plan.md` only after all local
  checks and all three CI jobs pass.
- Update this table of contents if any section is added, removed, or renamed.
- Confirm no local environment file, credential, database dump, coverage report, build
  output, dependency directory, or cache artifact is tracked.

Commit gate:

```text
make clean
make install
make check
cd backend
../.venv/bin/python -m alembic downgrade base
../.venv/bin/python -m alembic upgrade head
../.venv/bin/python -m alembic check
cd ..
make help
git diff --check
git status --short
```

Final remote gate:

```text
frontend
backend
migrations
```

All three GitHub Actions jobs must pass for the final DEV-006 commit before the
development-plan tracker and this commit tracker are marked complete.

## Out of Scope

DEV-006 establishes local quality orchestration and baseline continuous integration. It
does not implement:

- Deterministic development demo data or `make seed-demo`; those belong to DEV-007.
- Authentication, entries, statistics, opportunity-cost features, or other product
  behavior added by later DEV tasks.
- Dependency vulnerability scanning, license policy, automated dependency updates, or
  software-bill-of-materials generation; those can be added after the foundation is
  stable and must include a documented severity policy.
- End-to-end browser journeys, screenshot artifacts, accessibility audits, or the
  release smoke suite; those belong to later feature and release work.
- Production deployment, cloud infrastructure, secrets, database backups, or rollback
  operations.
- Automatic database migration during PostgreSQL container startup.
- Downgrades of shared, staging, or production databases.
- Changes to repository branch-protection settings; DEV-006 documents the required job
  names for an administrator to configure.
- Removal of virtual environments, installed dependencies, local environment files,
  Docker volumes, or database contents through `make clean`.

## Implementation Record

Complete this section during Commit 6. Keep the table of contents synchronized if its
headings change or more sections are added.

### Overview

Record the final Makefile command surface, development process supervision, and GitHub
Actions workflow structure implemented by DEV-006.

### What It Achieved

Record the verified contributor outcomes, failure behavior, cleanup protections,
PostgreSQL enforcement, and required CI jobs.

### Local and CI Equivalence

Record the final mapping between each stage of `make check` and the frontend, backend,
and migrations jobs, including any intentional difference such as CI's isolated
migration cycle.

### Verification

Record the exact local commands, test counts, migration results, clean-install result,
workflow validation, and passing GitHub Actions runs used to complete DEV-006.

### Limitations and Follow-up

Record deferred security scanning, end-to-end testing, release automation, production
operations, and any quality checks that later DEV tasks must add to both `make check`
and CI.
