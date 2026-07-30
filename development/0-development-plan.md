# Development Plan

## Purpose

This directory converts the approved `implementation/` design into reviewable development work. Each `DEV-xyz` item is intended to be one pull request (PR), with a narrow outcome, explicit dependencies, tests, and documentation updates.

The implementation design remains the technical source of truth. If development exposes a design conflict, update the relevant `implementation/` document (and the governing `planning/SYS-*` document when product behavior changes) in the same PR or in a prerequisite documentation PR.

## Tracking Rule

In the master tracker, use `[ ]` while a task is unfinished. Change it to `[x]` only after its PR is merged and its acceptance checks pass on the default branch.

## Implementation Record Rule

Every implemented task must add a matching `development/DEV-xyz.md` record. Keep it brief, but include the task's objective, what changed, what it achieved, important usage or safety information, verification performed, and any remaining limitations or follow-up work.

## Development Categories

| Category                         | Detailed tasks  |
| -------------------------------- | --------------- |
| Foundation and tooling           | DEV-001–DEV-007 |
| Authentication                   | DEV-008–DEV-009 |
| Entry management                 | DEV-010–DEV-012 |
| Check-in lifecycle               | DEV-013–DEV-015 |
| Statistics and opportunity costs | DEV-016–DEV-019 |
| Hardening and release            | DEV-020–DEV-024 |

## Master PR Tracker

Update this table as the canonical portfolio-level view. Detailed acceptance criteria live in the category documents.

|                  | ID                                                                              | PR title                                                   | Category       | Depends on                         |
| ---------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------- | -------------- | ---------------------------------- |
| &#91;x&#93;      | [DEV-001](#dev-001--scaffold-frontend-and-backend-workspaces)                   | Scaffold frontend and backend workspaces                   | Foundation     | —                                  |
| &#91;x&#93;      | [DEV-002](#dev-002--add-local-environment-and-postgresql-workflow)              | Add local environment and PostgreSQL workflow              | Foundation     | DEV-001                            |
| &#91;x&#93;      | [DEV-003](#dev-003--establish-backend-application-foundation)                   | Establish backend application foundation                   | Foundation     | DEV-001, DEV-002                   |
| &#91;x&#93;      | [DEV-004](#dev-004--establish-frontend-application-foundation)                  | Establish frontend application foundation                  | Foundation     | DEV-001                            |
| &#91;x&#93;      | [DEV-005](#dev-005--add-initial-database-models-and-migration)                  | Add initial database models and migration                  | Foundation     | DEV-002, DEV-003                   |
| &#91;x&#93;      | [DEV-006](#dev-006--add-quality-commands-and-continuous-integration)            | Add quality commands and continuous integration            | Foundation     | DEV-001, DEV-003, DEV-004, DEV-005 |
| &#91;x&#93;      | [DEV-007](#dev-007--add-deterministic-development-demo-data)                    | Add deterministic development demo data                    | Foundation     | DEV-005                            |
| &#91;x&#93;      | [DEV-008](#dev-008--implement-authentication-and-session-api)                   | Implement authentication and session API                   | Authentication | DEV-005                            |
| &#91;x&#93;      | [DEV-009](#dev-009--implement-authentication-ui-and-route-guards)               | Implement authentication UI and route guards               | Authentication | DEV-004, DEV-008                   |
| &#91;x&#93;      | [DEV-010](#dev-010--implement-entry-crud-and-dashboard-api)                     | Implement entry CRUD and dashboard API                     | Entries        | DEV-005, DEV-008                   |
| &#91;&#160;&#93; | [DEV-011](#dev-011--build-dashboard-entry-lists)                                | Build dashboard entry lists                                | Entries        | DEV-009, DEV-010                   |
| &#91;&#160;&#93; | [DEV-012](#dev-012--build-entry-create-edit-and-delete-flows)                   | Build entry create, edit, and delete flows                 | Entries        | DEV-010, DEV-011                   |
| &#91;&#160;&#93; | [DEV-013](#dev-013--implement-atomic-entry-check-in-api)                        | Implement atomic entry check-in API                        | Check-in       | DEV-010                            |
| &#91;&#160;&#93; | [DEV-014](#dev-014--build-the-check-in-experience)                              | Build the check-in experience                              | Check-in       | DEV-011, DEV-013                   |
| &#91;&#160;&#93; | [DEV-015](#dev-015--add-resolved-entry-comment-editing)                         | Add resolved-entry comment editing                         | Check-in       | DEV-013, DEV-014                   |
| &#91;&#160;&#93; | [DEV-016](#dev-016--implement-statistics-aggregate-api)                         | Implement statistics aggregate API                         | Statistics     | DEV-013                            |
| &#91;&#160;&#93; | [DEV-017](#dev-017--implement-opportunity-cost-example-api)                     | Implement opportunity-cost example API                     | Statistics     | DEV-005, DEV-008                   |
| &#91;&#160;&#93; | [DEV-018](#dev-018--build-statistics-and-equivalents-ui)                        | Build statistics and equivalents UI                        | Statistics     | DEV-016, DEV-017                   |
| &#91;&#160;&#93; | [DEV-019](#dev-019--build-opportunity-cost-settings-ui)                         | Build opportunity-cost settings UI                         | Statistics     | DEV-017, DEV-018                   |
| &#91;&#160;&#93; | [DEV-020](#dev-020--complete-shared-ux-accessibility-and-responsive-behavior)   | Complete shared UX, accessibility, and responsive behavior | Hardening      | DEV-012, DEV-015, DEV-018, DEV-019 |
| &#91;&#160;&#93; | [DEV-021](#dev-021--add-security-and-abuse-protections)                         | Add security and abuse protections                         | Hardening      | DEV-008, DEV-010, DEV-017          |
| &#91;&#160;&#93; | [DEV-022](#dev-022--add-production-observability-and-operational-configuration) | Add production observability and operational configuration | Release        | DEV-003, DEV-021                   |
| &#91;&#160;&#93; | [DEV-023](#dev-023--add-end-to-end-smoke-coverage)                              | Add end-to-end smoke coverage                              | Release        | DEV-007, DEV-020, DEV-021          |
| &#91;&#160;&#93; | [DEV-024](#dev-024--validate-release-and-document-operations)                   | Validate release and document operations                   | Release        | DEV-006, DEV-022, DEV-023          |

## Delivery Milestones

| Milestone              | Included PRs    | Exit gate                                                                            | Status      |
| ---------------------- | --------------- | ------------------------------------------------------------------------------------ | ----------- |
| M1 — Foundation        | DEV-001–DEV-007 | Clean install, healthy app, reproducible migration, seed data, and green baseline CI | Complete    |
| M2 — Accounts          | DEV-008–DEV-009 | Signup/login/logout/session restoration pass API and UI tests                        | Complete    |
| M3 — Entry management  | DEV-010–DEV-012 | Owned CRUD and all dashboard buckets work without full-page reloads                  | Not started |
| M4 — Check-in          | DEV-013–DEV-015 | Exact 48-hour and concurrent-transition tests pass; resolved comments are editable   | Not started |
| M5 — Insights          | DEV-016–DEV-019 | Date-boundary aggregates, equivalents, and example management pass                   | Not started |
| M6 — Release candidate | DEV-020–DEV-024 | Full CI and smoke suite pass; migration and release checklists are complete          | Not started |

## Recommended Merge Order

```text
DEV-001
├── DEV-002 ── DEV-003 ── DEV-005 ── DEV-007
│                         ├── DEV-008 ── DEV-009
│                         └── DEV-017
└── DEV-004

DEV-005 + DEV-008 ── DEV-010 ── DEV-011 ── DEV-012
                              └── DEV-013 ── DEV-014 ── DEV-015
                                               └── DEV-016
DEV-016 + DEV-017 ── DEV-018 ── DEV-019
Feature completion ── DEV-020/DEV-021 ── DEV-022/DEV-023 ── DEV-024
```

DEV-006 may begin once its four prerequisites exist and should be kept current as later PRs add checks. Parallel work is safe only where the dependency table permits it.

## Detailed PR Tasks

## Foundation and Tooling Development

### DEV-001 — Scaffold frontend and backend workspaces

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

### DEV-002 — Add local environment and PostgreSQL workflow

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

### DEV-003 — Establish backend application foundation

Scope:

- Add typed Pydantic settings, async SQLAlchemy engine/session factory, injectable UTC clock, and application lifespan.
- Add the FastAPI factory, `/api/health`, request IDs, structured logging, CORS/cookie settings, and standard error envelope handlers.
- Validate production-only configuration requirements without embedding secrets.
- Add backend startup, configuration, health, and error-shape tests.

Acceptance:

- Health returns successfully with an explicit response contract.
- Invalid configuration fails early with actionable errors.
- Logs omit credentials/cookies and unexpected errors return a safe request-correlated response.

### DEV-004 — Establish frontend application foundation

Scope:

- Add the app provider tree, React Router shell, TanStack Query client, and feature-oriented directories.
- Add the credentialed API client with base URL configuration and standard error parsing.
- Define stable query-key factories, common request states, API contract types, and test setup with Vitest, RTL, and MSW.
- Add the Vite `/api` development proxy and a minimal accessible application shell.

Acceptance:

- The application renders through the router and builds in strict mode.
- API tests prove credentials and the standard error envelope are handled.
- Tests can mock API behavior through MSW without implementation-detail assertions.

### DEV-005 — Add initial database models and migration

Scope:

- Implement separate SQLAlchemy models for users, sessions, entries, and opportunity-cost examples.
- Add all named keys, checks, indexes, lifecycle constraints, timestamp rules, and bounded cent values from the database design.
- Configure Alembic and create the initial migration without importing mutable models from the revision.
- Add PostgreSQL constraint, cascade, index/metadata drift, and migration-cycle tests.

Acceptance:

- Empty database upgrade, downgrade to base, and re-upgrade succeed.
- Model metadata and migration head do not drift.
- Raw session tokens/plaintext passwords have no persistence columns.

### DEV-006 — Add quality commands and continuous integration

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

### DEV-007 — Add deterministic development demo data

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

### Design Traceability

- `implementation/0-implementation-plan.md`: foundation phase, repository target, contracts, test strategy.
- `implementation/1-database-implementation-plan.md`: complete schema, migration plan, and database tests.
- `implementation/2-frontend-implementation-plan.md`: structure, API client, query keys, testing, build.
- `implementation/3-backend-implementation-plan.md`: structure, configuration, lifecycle, errors, quality.
- `implementation/4-development-tools-implementation-plan.md`: environment, Makefile, demo data, CI, migrations.

## Authentication Development

### DEV-008 — Implement authentication and session API

Scope:

- Implement auth schemas, repository operations, service transactions, and the exact `SYS-004` endpoints.
- Normalize emails, hash passwords with Argon2id, generate opaque random session tokens, and store only SHA-256 digests.
- Issue the configured `HttpOnly`, `SameSite=Lax` session cookie with environment-appropriate `Secure` behavior.
- Resolve, expire, refresh `last_used_at` as designed, and revoke sessions; expose the authenticated-user dependency.
- Translate duplicate email, invalid credentials, validation, and missing/expired session cases into standard safe errors.
- Add service and API integration tests for cookie attributes, persistence, expiry boundaries, logout, and secret non-disclosure.

Acceptance:

- Signup/login return the documented user and session behavior; refresh can resolve `/me` without credentials in browser storage.
- Logout invalidates the server record and clears the cookie idempotently as designed.
- The database and logs contain neither raw tokens nor plaintext passwords.

### DEV-009 — Implement authentication UI and route guards

Scope:

- Build signup and login pages with accessible labels, client-side usability validation, and server field/global errors.
- Bootstrap auth from the current-session endpoint before deciding routes.
- Add protected and guest-only route guards without treating frontend guards as authorization.
- Add logout behavior, auth-expiry handling, focus management, pending-state duplicate-submit prevention, and safe redirect rules.
- Add MSW-backed component/router tests for success, invalid credentials, duplicate email, expiry, refresh restoration, and logout.

Acceptance:

- A valid session survives reload and reaches protected content without UI flicker to the wrong route.
- Guest users cannot remain on protected routes; authenticated users do not remain on guest-only auth routes.
- Passwords and session values are never stored in local/session storage or logged.

### Design Traceability

- `implementation/2-frontend-implementation-plan.md`: authentication UI, routes, state, security, and tests.
- `implementation/3-backend-implementation-plan.md`: authentication/session lifecycle, validation, errors, and tests.
- `implementation/1-database-implementation-plan.md`: users and sessions constraints/indexes.

## Entry Management Development

### DEV-010 — Implement entry CRUD and dashboard API

Scope:

- Add entry Pydantic schemas, response mapping, repositories, services, and routes for create/list/detail/update/delete.
- Normalize strings and enforce positive bounded integer cents without floating-point API/database values.
- Scope every primary query by authenticated user and use the minimal existence check required to distinguish `403` from `404`.
- Partition list results into `needs_check_in`, `waiting`, `saved`, and `purchased` with one request clock and deterministic ordering.
- Permit core edits/deletion only while stored status is waiting; return `204` with no body for delete.
- Test ownership, normalization, ordering ties, exact derived bucket boundaries, lifecycle conflicts, and response/error contracts.

Acceptance:

- All four arrays are always present and derived fields use the same request-scoped UTC clock.
- Cross-user access returns the contractually required `403` without leaking resource data; unknown IDs return `404`.
- Entry responses consistently include `updated_at`, bucket, and eligibility fields specified by the design.

### DEV-011 — Build dashboard entry lists

Scope:

- Build the protected dashboard and components for all four buckets.
- Display item, formatted USD price, timing/status, comments where relevant, and correct actions per stored/derived state.
- Use TanStack Query keys and the credentialed API client; implement loading, empty, expired-auth, and retryable error states.
- Preserve backend ordering and avoid duplicating eligibility/business calculations in the browser beyond display countdowns.
- Add component tests for all buckets, zero data, request failure, and auth expiry.

Acceptance:

- Dashboard data renders after auth restoration and all four empty/non-empty states are understandable.
- Eligible entries link to check-in while younger waiting entries expose only legal waiting actions.
- Currency formatting is frontend-only and API cents remain integers.

### DEV-012 — Build entry create, edit, and delete flows

Scope:

- Build shared create/edit form controls for item name, price, and reason wanted.
- Parse user currency input deterministically into integer cents and show safe validation errors.
- Add waiting-entry detail/edit navigation and an explicit delete confirmation.
- On successful mutations, update/invalidate detail and dashboard queries so results appear without a reload.
- Handle duplicate submission, lifecycle conflicts caused by stale UI, server failures, and cancellation.
- Add MSW-backed tests for create, edit, delete, invalid money/text, errors, and cache refresh.

Acceptance:

- A newly created entry immediately appears in Waiting.
- Edit changes only allowed core fields; deletion removes the entry and returns to a valid route.
- UI never sends decimals/floats or assumes that hiding an action enforces authorization.

### Design Traceability

- `implementation/1-database-implementation-plan.md`: entry constraints and dashboard query design.
- `implementation/2-frontend-implementation-plan.md`: dashboard composition and create/edit/delete flows.
- `implementation/3-backend-implementation-plan.md`: entry service, ownership, response mapping, transactions.

## Check-in Lifecycle Development

### DEV-013 — Implement atomic entry check-in API

Scope:

- Add the check-in request/response schemas, service operation, repository row lock, and route.
- Select the owned entry `FOR UPDATE`, then recheck waiting status and `created_at + 48 hours` eligibility.
- At eligibility, set only status, normalized optional comment, `checked_in_at`, and `updated_at` using one injected clock.
- Return stable `early_check_in`, invalid status, ownership, validation, and unexpected error responses.
- Add PostgreSQL-backed service/API tests at one microsecond before and exactly at the boundary, plus concurrent requests.

Acceptance:

- Exactly `now == eligible_at` succeeds; any earlier request fails without mutation.
- Concurrent check-ins yield one success and one conflict, never two transitions.
- Statistics timestamps originate from `checked_in_at`, not creation time.

### DEV-014 — Build the check-in experience

Scope:

- Build the eligible-entry check-in route showing the original decision context and saved/purchased choices.
- Collect an optional normalized comment and require an explicit resolution action.
- Handle early/stale status conflicts, expired auth, request failure, and duplicate submission.
- Refresh dashboard/detail/statistics-related query keys after success and show the correct confirmation state.
- Add tests for both outcomes, optional comment, boundary conflicts, navigation, and cache effects.

Acceptance:

- Saved and purchased submissions use the same API contract and result in the proper dashboard bucket.
- Confirmation is accessible and cannot accidentally submit twice.
- The frontend relies on server eligibility and handles clock disagreement gracefully.

### DEV-015 — Add resolved-entry comment editing

Scope:

- Add the backend comment-only mutation route/service with ownership, row locking, normalization, and status checks.
- Build comment editing for saved and purchased details; do not expose core-field edits.
- Support clearing to `null` if allowed by the API normalization contract.
- Refresh affected dashboard/detail data and test waiting-entry rejection, ownership, empty normalization, and failures.

Acceptance:

- Resolved entries can change only `comment` and `updated_at`.
- Waiting entries receive the documented lifecycle conflict.
- Updated comments appear without a page reload.

### Design Traceability

- `implementation/0-implementation-plan.md`: 48-hour invariant and Phase 4 gate.
- `implementation/1-database-implementation-plan.md`: atomic check-in and lifecycle constraints.
- `implementation/2-frontend-implementation-plan.md`: check-in and comment flows.
- `implementation/3-backend-implementation-plan.md`: check-in/comment services and concurrency.

## Statistics and Opportunity Costs Development

### DEV-016 — Implement statistics aggregate API

Scope:

- Add the supported range enum and pure UTC half-open boundary calculation.
- Implement one conditional PostgreSQL aggregate for total saved, avoided count, and purchased count using `checked_in_at`.
- Return zeros for empty ranges and never load all entries for Python aggregation.
- Add response schemas/routes and unit, repository, and API tests for every range and exact boundary.
- Cover calendar-month subtraction, month/year edges, equal end timestamps, large cent totals, and invalid ranges.

Acceptance:

- `this_month`, rolling 3/6/12-month, and `all_time` results match the implementation definitions.
- Saved contributes to saved total/avoided count; purchased contributes only to purchased count.
- Calculations use one request clock and safe integer cents.

### DEV-017 — Implement opportunity-cost example API

Scope:

- Add schemas, response mapping, owned repositories, services, and CRUD routes for examples.
- Normalize label/unit, enforce positive bounded cents, preserve stable creation order, and allow duplicate labels.
- Lock updates/deletes where required and distinguish other-owner `403` from absent `404` without leaking data.
- Add CRUD, constraint, ordering, ownership, normalization, and failure tests.

Acceptance:

- Create/update accept only the documented mutable fields; delete returns an empty `204`.
- Every database access is user-scoped and stable ordering is deterministic.
- Zero/negative/out-of-range dollar values cannot enter through API or database.

### DEV-018 — Build statistics and equivalents UI

Scope:

- Extend the stats response/service to load examples and compute equivalents with Decimal and `ROUND_HALF_UP` to one decimal.
- Build statistics cards, the range filter, opportunity-cost equivalents, and loading/empty/error states.
- Treat whole/fractional JSON values numerically rather than depending on lexical `25.0` formatting.
- Invalidate/refetch statistics after check-ins and example changes.
- Test each filter, zero totals, whole/fractional equivalents, rounding, failures, and relevant cache refresh.

Acceptance:

- Displayed totals/counts/equivalents match the selected server-calculated range.
- The browser performs formatting only; it does not reproduce aggregate or equivalent rules.
- Invalid stored zero values are defensively skipped/logged by the backend despite database prevention.

### DEV-019 — Build opportunity-cost settings UI

Scope:

- Build protected list/create/edit/delete settings flows with shared accessible form controls.
- Convert display currency to integer cents and surface field/global server errors.
- Add delete confirmation, duplicate-submit prevention, stable list behavior, and cache updates for settings and statistics.
- Test CRUD success, validation, auth expiry, ownership-safe failures, retry, and equivalents refresh.

Acceptance:

- Example changes immediately affect both settings and statistics views.
- Duplicate labels remain supported and destructive actions require confirmation.
- UI handles an empty example list with a clear creation action.

### Design Traceability

- `implementation/1-database-implementation-plan.md`: aggregate query, ranges, example constraints/order.
- `implementation/2-frontend-implementation-plan.md`: statistics and opportunity-cost presentation/state.
- `implementation/3-backend-implementation-plan.md`: statistics calculation and example service behavior.

## Hardening and Release Development

### DEV-020 — Complete shared UX, accessibility, and responsive behavior

Scope:

- Audit every route for loading, empty, validation, expired-session, forbidden/not-found, server-error, retry, and success behavior.
- Complete semantic headings/landmarks, labels, keyboard interaction, focus movement, announcements, contrast, and reduced-motion behavior.
- Validate mobile through desktop layouts, long content, large currency values, and touch targets.
- Consolidate shared UI primitives only where repetition is proven; preserve feature ownership.
- Add focused automated accessibility/component checks and a documented manual test matrix.

Acceptance:

- All V1 workflows are usable by keyboard and at supported viewport sizes.
- Errors are actionable, focus is deliberate, and no route produces an unexplained blank state.
- Automated tests cover the shared patterns and the manual audit has no unresolved critical issue.

### DEV-021 — Add security and abuse protections

Scope:

- Add login/signup throttling by IP and normalized account key with a deployment-compatible store abstraction.
- Enforce trusted hosts/proxy behavior, body-size limits, conservative security headers, origin/cookie protections, and safe production settings.
- Redact cookies, authorization values, passwords, session digests, and other secrets from all logs.
- Add tests for rate-limit boundaries, forwarded/trusted proxy behavior, redaction, headers, invalid origins, and oversized bodies.
- Add locked dependency/security scanning to CI with a documented severity policy.

Acceptance:

- Public auth endpoints resist straightforward abuse without exposing whether an account exists beyond the approved contract.
- Production refuses unsafe cookie/origin/host configuration.
- No high-severity dependency finding remains untriaged at merge.

### DEV-022 — Add production observability and operational configuration

Scope:

- Finalize structured request logs containing request ID, method, route template, status, duration, and user ID when available.
- Ensure exception traces remain server-side while safe responses provide request correlation.
- Define liveness/readiness behavior, database-unavailable `503`, log level controls, and clean startup/shutdown.
- Add production configuration examples for the Oracle VPS origin without real secrets.
- Document reverse-proxy, process-supervisor, TLS, local-only database, backup, and restore expectations; do not provision or deploy.

Acceptance:

- Operators can correlate a safe client error with server logs without sensitive data exposure.
- Health behavior distinguishes application liveness/readiness as documented.
- Production operational requirements are executable as a future runbook, with unresolved infrastructure choices clearly marked.

### DEV-023 — Add end-to-end smoke coverage

Scope:

- Add a small browser smoke suite for signup/login, create entry, seeded eligible check-in, statistics/equivalents, and logout.
- Run against the real frontend/backend and PostgreSQL with isolated deterministic data.
- Provide local and CI commands, failure artifacts, and reliable readiness/cleanup behavior.
- Keep deeper boundary/authorization/concurrency coverage in lower-level suites.

Acceptance:

- The critical journey passes repeatedly in CI without timing sleeps for the 48-hour rule.
- Failed runs retain useful non-secret diagnostics.
- Test isolation prevents state leakage and never targets development or production data.

### DEV-024 — Validate release and document operations

Scope:

- Run the full check suite against PostgreSQL and validate clean migration upgrade, downgrade/re-upgrade, and drift checks.
- Complete dependency review, accessibility/manual smoke checks, production build/startup validation, and environment documentation.
- Add a release checklist covering backup, disk space, immutable revision/artifact, forward migration, restart, health/browser verification, and application rollback.
- Confirm production decisions for domain/DNS, USD scope, session lifetime/retention, and any email-dependent work; record unresolved items as explicit release blockers.
- Update README and development trackers with the release-candidate evidence.

Acceptance:

- CI is green and every V1 implementation acceptance checklist is satisfied or has an explicitly approved deferral.
- A clean environment can follow documentation through install, migrate, seed, test, build, and startup.
- No deployment-changing command is introduced; production release remains a separately authorized operation.

### Design Traceability

- `implementation/0-implementation-plan.md`: hardening gate, definition of done, security/operations, open items.
- `implementation/2-frontend-implementation-plan.md`: states, accessibility, responsive design, frontend security.
- `implementation/3-backend-implementation-plan.md`: security, abuse controls, observability, test acceptance.
- `implementation/4-development-tools-implementation-plan.md`: CI, Oracle operations boundary, documentation rules.

## PR Contract

Every `DEV-*` PR must:

- Link its task ID and use the listed title, optionally with a conventional prefix such as `feat:` or `chore:`.
- Stay within the stated scope; discovered follow-up work receives a new task.
- Include implementation, tests, migrations, configuration examples, and documentation needed for that slice.
- Preserve the standard API error envelope, UTC timestamps, UUID identifiers, integer cents, ownership checks, and server-owned business rules.
- Add no secrets, real `.env` files, database dumps, credentials, raw session tokens, or plaintext passwords.
- Pass the relevant local checks and all required CI jobs.
- Add `[x]` to the master tracker and update the category tracker after the PR is merged.

## Definition of Ready

A task is ready when its dependencies are `Done`, its acceptance criteria are still consistent with the implementation design, and no unresolved product decision changes its scope.

## Definition of Done

A task is done when the PR is merged and:

- Its category acceptance criteria pass.
- Normal, boundary, validation, unauthenticated, unauthorized, and failure paths appropriate to the slice are tested.
- Backend authorization is independent of frontend route guards.
- Loading, empty, error, and mutation-refresh states appropriate to any UI are handled.
- Types, lint, formatting, tests, build, and migration checks relevant to the change pass.
- Documentation and example environment files reflect the merged behavior.

## Scope Boundaries and Deferred Work

These items are not prerequisites for the V1 development PRs unless the implementation design is revised:

- Password reset and transactional email; the AWS service and flow remain undecided.
- Automated production deployment or a `make deploy` target.
- Account deletion, stored multi-currency support, and entry pagination.
- Provisioning the Oracle VPS, registering the domain, or changing DNS.

Before production, confirm the 30-day session lifetime, USD-only scope, domain/DNS readiness, and the chosen AWS transactional email design if email-dependent features enter scope.
