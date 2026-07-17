# Foundation and Tooling Development

## Category Tracker

| ID | Outcome | Depends on | Status | PR |
|---|---|---|---|---|
| DEV-001 | Runnable, locked frontend and backend workspaces | — | Not started | — |
| DEV-002 | Safe, documented local PostgreSQL and environment workflow | DEV-001 | Not started | — |
| DEV-003 | Configured FastAPI application with health and infrastructure concerns | DEV-001, DEV-002 | Not started | — |
| DEV-004 | Typed React shell with routing, API, and test foundations | DEV-001 | Not started | — |
| DEV-005 | Reproducible initial PostgreSQL schema | DEV-002, DEV-003 | Not started | — |
| DEV-006 | One-command quality checks enforced by CI | DEV-001, DEV-003, DEV-004, DEV-005 | Not started | — |
| DEV-007 | Safe, deterministic demo dataset | DEV-005 | Not started | — |

## DEV-001 — Scaffold frontend and backend workspaces

Create the target repository structure and pin compatible stable dependencies for Python 3.12+ and Node.js 22 LTS.

Scope:

- Scaffold Vite React/TypeScript and FastAPI package/test directories from the implementation structure.
- Enable strict TypeScript, `noUncheckedIndexedAccess`, and `exactOptionalPropertyTypes`.
- Add backend runtime/dev requirement files and `pyproject.toml` configuration anchors.
- Add `.nvmrc`, `.python-version`, root ignore rules, and minimal root README setup notes.
- Commit `package-lock.json`; do not add application features yet.

Acceptance:

- Clean frontend and backend dependency installation succeeds.
- Empty/minimal lint, typecheck, test, and production build commands execute.
- No generated build products, virtual environments, or secrets are tracked.

## DEV-002 — Add local environment and PostgreSQL workflow

Scope:

- Add root, backend, and frontend `.env.example` files exactly aligned with the implementation design.
- Add `compose.yaml` with PostgreSQL 16, a named volume, loopback-only port, and health check.
- Implement Make targets for environment/database install, up, down, logs, reset, upgrade, downgrade, and revision workflows.
- Ensure destructive reset requires confirmation and test/prod database URLs cannot be inferred from development settings.
- Document first-run prerequisites and commands.

Acceptance:

- A new contributor can start a healthy local database from documented examples.
- The database is not exposed on all interfaces and `db-down` preserves its volume.
- Unsafe reset/downgrade behavior is clearly guarded and documented.

## DEV-003 — Establish backend application foundation

Scope:

- Add typed Pydantic settings, async SQLAlchemy engine/session factory, injectable UTC clock, and application lifespan.
- Add the FastAPI factory, `/api/health`, request IDs, structured logging, CORS/cookie settings, and standard error envelope handlers.
- Validate production-only configuration requirements without embedding secrets.
- Add backend startup, configuration, health, and error-shape tests.

Acceptance:

- Health returns successfully with an explicit response contract.
- Invalid configuration fails early with actionable errors.
- Logs omit credentials/cookies and unexpected errors return a safe request-correlated response.

## DEV-004 — Establish frontend application foundation

Scope:

- Add the app provider tree, React Router shell, TanStack Query client, and feature-oriented directories.
- Add the credentialed API client with base URL configuration and standard error parsing.
- Define stable query-key factories, common request states, API contract types, and test setup with Vitest, RTL, and MSW.
- Add the Vite `/api` development proxy and a minimal accessible application shell.

Acceptance:

- The application renders through the router and builds in strict mode.
- API tests prove credentials and the standard error envelope are handled.
- Tests can mock API behavior through MSW without implementation-detail assertions.

## DEV-005 — Add initial database models and migration

Scope:

- Implement separate SQLAlchemy models for users, sessions, entries, and opportunity-cost examples.
- Add all named keys, checks, indexes, lifecycle constraints, timestamp rules, and bounded cent values from the database design.
- Configure Alembic and create the initial migration without importing mutable models from the revision.
- Add PostgreSQL constraint, cascade, index/metadata drift, and migration-cycle tests.

Acceptance:

- Empty database upgrade, downgrade to base, and re-upgrade succeed.
- Model metadata and migration head do not drift.
- Raw session tokens/plaintext passwords have no persistence columns.

## DEV-006 — Add quality commands and continuous integration

Scope:

- Complete Make targets for install, dev, test, lint, format, format-check, typecheck, build, check, and safe clean behavior.
- Ensure the dev process forwards termination signals and does not leave servers running.
- Add GitHub Actions frontend, backend, and PostgreSQL migration jobs with dependency caching.
- Run locked installs, formatting, lint, typing, tests, builds, upgrade/downgrade/re-upgrade, and drift checks.
- Document the local/CI equivalence and required merge checks.

Acceptance:

- `make check` is green from a clean supported environment.
- CI needs no production secrets and uses PostgreSQL rather than SQLite.
- `make clean` cannot delete source, migrations, environments, or database volumes.

## DEV-007 — Add deterministic development demo data

Scope:

- Add an idempotent backend seeder and `make seed-demo`.
- Create a labeled demo user plus waiting, eligible, saved, purchased, commented, and opportunity-cost records covering statistics ranges.
- Use stable identifiers/keys and timestamps relative to an injected UTC clock.
- Refuse production/non-disposable targets and verify Alembic head before mutation.
- Publish local-only credentials and the exact seed workflow in the README.

Acceptance:

- Repeated runs do not duplicate records or change non-demo data.
- Every dashboard bucket and whole/fractional equivalent has demo coverage.
- Production and unsafe-host guards are tested.

## Design Traceability

- `implementation/0-implementation-plan.md`: foundation phase, repository target, contracts, test strategy.
- `implementation/1-database-implementation-plan.md`: complete schema, migration plan, and database tests.
- `implementation/2-frontend-implementation-plan.md`: structure, API client, query keys, testing, build.
- `implementation/3-backend-implementation-plan.md`: structure, configuration, lifecycle, errors, quality.
- `implementation/4-development-tools-implementation-plan.md`: environment, Makefile, demo data, CI, migrations.
