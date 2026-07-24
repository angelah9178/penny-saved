# DEV-007 — Add Deterministic Development Demo Data

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Commit 1 — Add the Guarded Demo-Seed Foundation](#commit-1--add-the-guarded-demo-seed-foundation)
- [Commit 2 — Add the Deterministic Demo User](#commit-2--add-the-deterministic-demo-user)
- [Commit 3 — Seed Every Entry and Statistics State](#commit-3--seed-every-entry-and-statistics-state)
- [Commit 4 — Seed Opportunity Costs and Verify Idempotency](#commit-4--seed-opportunity-costs-and-verify-idempotency)
- [Commit 5 — Document and Verify the Completed Demo Workflow](#commit-5--document-and-verify-the-completed-demo-workflow)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)
  - [Overview](#overview)
  - [What It Achieved](#what-it-achieved)
  - [Demo Dataset](#demo-dataset)
  - [Safety and Idempotency](#safety-and-idempotency)
  - [Verification](#verification)
  - [Limitations and Follow-up](#limitations-and-follow-up)

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|  | Commit | Title | Depends on |
|---|---|---|---|
| &#91;x&#93; | [1](#commit-1--add-the-guarded-demo-seed-foundation) | Add guarded demo-seed foundation | — |
| &#91; &#93; | [2](#commit-2--add-the-deterministic-demo-user) | Add deterministic demo identity | Commit 1 |
| &#91; &#93; | [3](#commit-3--seed-every-entry-and-statistics-state) | Add representative demo entries | Commit 2 |
| &#91; &#93; | [4](#commit-4--seed-opportunity-costs-and-verify-idempotency) | Add opportunity costs and idempotency coverage | Commit 3 |
| &#91; &#93; | [5](#commit-5--document-and-verify-the-completed-demo-workflow) | Document DEV-007 demo workflow | Commits 1–4 |

## Objective

Create a safe, repeatable development dataset that makes every important application
state available without manual setup or real waiting periods. DEV-007 adds one root
command:

```text
make seed-demo
```

That command creates or restores a labeled local demo user, waiting and eligible
entries, saved and purchased outcomes, comments, statistics time ranges, and
opportunity-cost examples. A contributor can then start the application and inspect
representative data immediately:

```text
make db-up
    ↓
make db-upgrade
    ↓
make seed-demo
    ↓
make dev
```

The seed is **deterministic**: stable identifiers and an injected UTC clock make the
logical dataset predictable. It is **idempotent**: running it repeatedly updates or
restores the same known demo records instead of adding duplicates. It is **guarded**:
the command refuses production, unsafe hosts, missing migration head, and any database
that is not explicitly suitable for local development or testing.

Complete and commit each section in order. Every commit must preserve `make check`, and
all database-writing tests must use only the explicit disposable `TEST_DATABASE_URL`.
The seeder must never modify records owned by a non-demo user.

## Commit 1 — Add the Guarded Demo-Seed Foundation

To **seed** a database means to populate it with prepared starting data. In this project,
demo seeding will create a known local account and representative purchase records so a
contributor can inspect the application without entering every scenario manually:

```text
empty migrated development database
    ↓
make seed-demo
    ↓
database contains the known demonstration dataset
```

Commit 1 establishes the rules and boundaries for that command before later commits add
the user, entries, and opportunity-cost examples. Its purpose is to make every future
demo-data write pass through one protected path: never production, never an unsafe
database target, never an outdated schema, and never a partial transaction.

Commit 1 creates the command path and safety boundary before adding demo records. The
seeder is backend-owned because it writes SQLAlchemy models, uses the backend clock and
configuration, and must enforce the same PostgreSQL constraints as application code.
The frontend does not create, import, or define seed data.

The command flow is:

```text
make seed-demo
    ├── verify backend environment and tooling
    ├── load validated backend settings
    ├── refuse production
    ├── verify the database host and database name are safe
    ├── verify PostgreSQL is at Alembic head
    ├── open one database transaction
    ├── reconcile known demo records
    └── commit all changes together
```

### Rules `make seed-demo` Must Follow

Every current and future version of the command must follow these rules:

1. **Never run against production.** `APP_ENV=production` must be rejected before an
   engine is created or a database connection is opened.
2. **Only use an explicitly safe PostgreSQL target.** Development may use only a
   loopback host such as `localhost`, `127.0.0.1`, or `::1`. Test mode additionally
   requires a disposable database name ending in `_test`.
3. **Require a valid migrated database.** The applied Alembic heads must exactly match
   the heads in the checked-out code before any data is changed.
4. **Make no setup changes automatically.** The command must not start Docker, create
   a database, install dependencies, or apply migrations. The developer runs
   `make db-up` and `make db-upgrade` first.
5. **Use one all-or-nothing transaction.** All demo records must succeed together. Any
   validation or write failure must roll back the entire seed operation.
6. **Reconcile only known demo records.** Repeated runs must reuse the stable demo
   identities instead of creating duplicates or taking over unrelated records.
7. **Use backend-owned configuration, models, and UTC time.** Seeded data must follow
   the same database constraints and timestamp rules as application data.
8. **Never expose secrets.** Output may identify the local demo account and record
   counts, but it must not print password hashes, database credentials, or other
   sensitive configuration.

The environment guard must allow only:

- `APP_ENV=development` with a loopback PostgreSQL host.
- `APP_ENV=test` with an explicit disposable database whose name ends in `_test`.

It must reject production regardless of hostname. It must also reject remote,
shared-looking, missing, malformed, or unsupported database targets. These checks are
defense in depth; they do not make a shared database safe merely because its hostname
looks local.

The Alembic-head check runs before mutation. A database behind the current revision may
not have required tables or columns, while a database ahead of the checked-out code may
not match the models. The seed operation must stop without changing data unless the
database contains exactly the current migration heads.

All seed changes occur inside one transaction:

```text
every demo record succeeds → commit
any validation/write fails → rollback everything
```

The production command receives the real UTC clock. Tests call the same seed service
with a fixed clock so timestamp-derived states are deterministic and boundary behavior
can be asserted without waiting.

Suggested commit message:

```text
Add guarded demo seed foundation
```

Implement:

- Add a backend seed entry point such as `backend/app/scripts/seed_demo.py`.
- Separate command-line orchestration, environment/database guards, migration-head
  verification, dataset construction, and persistence into focused functions.
- Reuse the validated backend settings and injected UTC clock.
- Add `make seed-demo` as a public `.PHONY` target with a concise `make help`
  description.
- Have the Make target use the root virtual environment and backend configuration; do
  not install dependencies or start Docker as a side effect.
- Require the caller to run `make db-up` and `make db-upgrade` first.
- Refuse `APP_ENV=production` before creating an engine or opening a connection.
- Allow only loopback development PostgreSQL or an explicit `_test` test database.
- Compare the database's applied Alembic heads with the code's current heads before any
  insert, update, or delete.
- Run the complete seed in one transaction and roll back on failure.
- Return concise success output that identifies the demo account and record counts
  without printing a password hash, database credential, or other secret.
- Add unit tests for accepted and rejected environments, hosts, database names,
  migration states, clock injection, rollback behavior, and actionable errors.
- Add Makefile contract coverage for the target, prerequisite behavior, working
  directory, and use of the pinned backend Python executable.

Commit gate:

```text
make help
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/tooling tests/scripts/test_seed_demo_guards.py
cd ..
make check
git diff --check
```

## Commit 2 — Add the Deterministic Demo User

**Status:** Complete.

Commit 2 adds the stable identity that owns every later demo record. The demo account
uses a fixed UUID and normalized, clearly labeled local-only email. Stable identity
allows every seed run to find the same row without relying on a generated ID or a
mutable display value.

Only one demo user is created. It is a persistent local-development account, not a
temporary automated-test user, so `make seed-demo` does not delete it when the command
finishes. Later demo entries and opportunity-cost examples all belong to this same
account. Each subsequent seed run finds and reconciles the existing user instead of
creating a duplicate. The user remains until the local database is reset or the record
is deliberately deleted.

The fixed local-only credentials are:

```text
Email:    demo@penny-saved.local
Password: PennySavedDemo!2026
```

These credentials are for local demonstration data only and must never be reused for a
real account or production environment.

The account must contain a real password hash, never plaintext:

```text
documented local-only password
    ↓
approved password-hashing primitive
    ↓
password hash stored in users.password_hash
```

DEV-008 still owns signup, login, logout, cookies, sessions, and authentication policy.
DEV-007 may add only the minimal shared password-hashing primitive required to create a
compatible demo hash safely. That primitive must use the already pinned password
library and be reusable by DEV-008; the seed command must not invent a demo-only hash
format.

On repeated runs, the seeder finds the account by its stable UUID and verifies the
expected email. It may also use the unique normalized email as a collision guard, but
it must not take over an unrelated row. If the stable UUID and email identify different
users, the command stops and rolls back with an actionable collision error.

The password behavior must keep the published demo credential usable without rewriting
an already valid salted hash on every run:

```text
stored hash verifies demo password → preserve it
stored hash does not verify         → replace it with a new secure hash
```

Suggested commit message:

```text
Add deterministic demo user
```

Implement:

- Define stable demo constants for the user UUID, normalized email, and local-only
  password label.
- Keep the plaintext demo password only in backend command code/documentation intended
  for local development; never store it in a database column or log its hash.
- Add or reuse a shared Argon2 password hash/verify primitive backed by the pinned
  password library.
- Create the demo user with the fixed UUID and clock-supplied `created_at` and
  `updated_at` timestamps.
- Reconcile only the known demo user on subsequent runs.
- Preserve an existing hash when it verifies the expected demo password; refresh it
  only when necessary.
- Refuse UUID/email collisions instead of modifying a possibly unrelated account.
- Add tests proving the UUID and logical identity remain stable, the password hash
  verifies, plaintext is never persisted, repeated runs do not duplicate or
  unnecessarily update the account, and collision failures roll back.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/scripts/test_seed_demo_guards.py tests/scripts/test_seed_demo_user.py
cd ..
make check
git diff --check
```

## Commit 3 — Seed Every Entry and Statistics State

**Status:** Complete.

Commit 3 adds impulse-purchase entries that cover every stored lifecycle state and every
time-derived dashboard state. Timestamps are calculated relative to the injected UTC
clock rather than hard-coded calendar dates, so the dataset remains useful whenever it
is seeded.

The required dashboard coverage is:

```text
waiting, less than 48 hours old  → waiting
waiting, at least 48 hours old   → needs check-in
saved with checked_in_at         → saved
purchased with checked_in_at     → purchased
```

`needs_check_in` remains derived. The seeder stores a `waiting` entry old enough to be
eligible; it must not add an unsupported status or eligibility column.

The exact nine deterministic entries created by Commit 3 are:

| Demo entry | State and relative timestamp | Edge case covered |
|---|---|---|
| Ceramic travel mug | Waiting, created 6 hours ago | Very recent normal waiting state |
| Wireless headphones | Waiting, created 36 hours ago | Still waiting shortly before eligibility |
| Running shoes | Waiting, created exactly 48 hours ago | Inclusive check-in boundary |
| Drawing tablet | Waiting, created 10 days ago | Clearly overdue check-in |
| Desk lamp | Saved, checked in 3 days ago | Short-range statistics and a comment |
| Lightweight jacket | Saved, checked in 21 days ago | Monthly-range statistics and a null comment |
| Online design course | Saved, checked in 120 days ago | Annual-range statistics and a comment |
| Espresso machine | Saved, checked in 500 days ago | All-time inclusion and annual exclusion |
| Concert ticket | Purchased, checked in 2 days ago | Purchased outcome with a comment |

Together these entries cover both sides of the 48-hour boundary, every stored status,
resolved and unresolved timestamps, saved statistics across short through all-time
ranges, purchased outcomes, varied positive prices, and both populated and null
comments. They are local demo scenarios rather than shared records used by automated
tests. In total, Commit 3 creates exactly nine deterministic entries for the single
demo user. Every `make seed-demo` run reconciles these same nine stable entry UUIDs, so
it restores their expected values without creating duplicates.

The exact approved ages, item names, prices, reasons, comments, and UUIDs must be defined
as one deliberate dataset. At least one saved and one purchased entry contain comments;
other resolved entries may leave comments null to cover both shapes. `checked_in_at`
must be present only for resolved statuses and must never precede `created_at`.

Idempotency is based on stable entry UUIDs. Each run restores the known records to the
values calculated from that run's clock. It must not match records by non-unique text,
delete manually created rows, or change entries owned by another user.

Suggested commit message:

```text
Add representative demo entries
```

Implement:

- Define a stable UUID and immutable logical label for every demo entry.
- Seed at least two recent waiting and two eligible waiting entries.
- Include one entry exactly at the 48-hour eligibility boundary.
- Seed multiple saved entries across short, medium, annual, and all-time statistics
  ranges.
- Seed at least one purchased entry.
- Include a comment on at least one saved and one purchased entry and preserve null
  comment coverage.
- Use varied positive integer-cent prices suitable for totals and opportunity-cost
  examples.
- Calculate all timestamps from one normalized injected UTC `now`.
- Respect every database lifecycle and timestamp constraint.
- Reconcile only stable demo-owned entry IDs and refuse an ID owned by another user.
- Add fixed-clock tests for exact field values, dashboard buckets, the 48-hour boundary,
  comments, statistics range coverage, stable ordering, repeated-run behavior, and
  non-demo preservation.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/scripts/test_seed_demo_entries.py
cd ..
make check
git diff --check
```

## Commit 4 — Seed Opportunity Costs and Verify Idempotency

Commit 4 completes the logical dataset with opportunity-cost examples and proves the
entire operation is safe to repeat. Examples translate saved cents into relatable units
and must support both whole and fractional equivalents:

```text
saved total ÷ unit value = equivalent quantity

$20.00 ÷ $5.00  = 4 whole units
$20.00 ÷ $12.00 = 1.666… fractional units
```

The seeder stores only the example label, unit name, and positive integer-cent unit
value. Later statistics and opportunity-cost features own presentation, rounding, and
calculation behavior; DEV-007 chooses data that will exercise those paths but does not
implement them.

Stable UUIDs identify the examples. Duplicate labels are allowed by the database, so
the seeder must never use label text alone as an upsert key. It updates or recreates
only the known demo UUIDs and rejects a stable-ID collision owned by another user.

This commit adds PostgreSQL integration coverage for the complete command:

```text
first run
    ↓
capture known demo rows and unrelated-user rows
    ↓
second run with the same fixed clock
    ↓
known demo rows remain logically identical
unrelated-user rows remain byte-for-byte unchanged
row counts do not grow
```

A second scenario deletes or changes one known demo record and reruns the seeder. The
command must restore that known record without disturbing manual or non-demo records.

Suggested commit message:

```text
Add demo opportunity costs and idempotency tests
```

Implement:

- Add at least two stable opportunity-cost examples with positive integer-cent values.
- Choose values that produce both whole and fractional equivalents from the seeded
  saved-entry totals.
- Calculate timestamps from the same injected UTC clock as the user and entries.
- Reconcile examples by stable UUID, not label.
- Add an end-to-end seed integration test against explicit `TEST_DATABASE_URL`.
- Prove two runs do not duplicate users, entries, or opportunity-cost examples.
- Prove the same fixed clock produces the same logical dataset.
- Prove missing or altered known demo records are restored.
- Prove unrelated users and all records they own remain unchanged.
- Prove manually created rows are not deleted merely because they are absent from the
  known demo specification.
- Prove any collision, constraint failure, or injected mid-seed error rolls back the
  complete transaction.
- Verify the final database remains at Alembic head and model metadata does not drift.

Commit gate:

```text
cd backend
../.venv/bin/ruff format --check .
../.venv/bin/ruff check .
../.venv/bin/pytest tests/scripts tests/integration/test_seed_demo.py
../.venv/bin/python -m alembic check
cd ..
make check
git diff --check
```

## Commit 5 — Document and Verify the Completed Demo Workflow

This final commit publishes the supported local workflow and records the completed
dataset. It does not add another kind of demo record.

Suggested commit message:

```text
Document DEV-007 demo data workflow
```

Implement:

- Update the root README with the exact first-run and repeat-run workflow:

  ```text
  make db-up
  make db-upgrade
  make seed-demo
  make dev
  ```

- Publish the clearly labeled local-only demo email and password.
- State that demo credentials must never be reused in staging, production, or another
  shared environment.
- Explain that `make seed-demo` is safe to repeat, which known data it reconciles, and
  which manual/non-demo data it preserves.
- Document the environment, host, database-name, and Alembic-head guards.
- Add `make seed-demo` to the main quality/development section of
  `development/DEV-MAKEFILE.md`, including when to run it and whether it is one-time.
- Add seed troubleshooting for missing migrations, unsafe targets, collisions, and
  connection failures.
- Record the final UUID-backed dataset, fixed-clock verification, idempotency results,
  limitations, and follow-up work in this document.
- Mark DEV-007 complete in `development/0-development-plan.md` only after all local and
  CI checks pass.
- Keep this table of contents synchronized if a section is added, removed, or renamed.
- Confirm no real credential, local environment file, database dump, generated cache,
  or plaintext password hash is tracked.

Commit gate:

```text
make clean
make install
make db-up
make db-upgrade
make seed-demo
make seed-demo
make check
cd backend
../.venv/bin/python -m alembic check
cd ..
git diff --check
git status --short
```

Manual verification:

```text
make dev
# Sign in with the documented local-only demo account after authentication exists.
# Verify waiting, needs-check-in, saved, purchased, comments, statistics ranges,
# and opportunity-cost examples as the corresponding UI features become available.
# Press Ctrl+C and confirm both application servers stop.
```

## Out of Scope

DEV-007 creates local development data. It does not implement:

- Signup, login, logout, session creation, cookies, session resolution, or route guards;
  those belong to DEV-008 and DEV-009.
- Entry repositories, CRUD endpoints, dashboard API grouping, check-in operations, or
  comment editing; those belong to DEV-010 and DEV-013.
- Dashboard, form, check-in, statistics, or opportunity-cost UI.
- Statistics aggregation queries or opportunity-cost calculations; DEV-007 only chooses
  representative stored data for those later features.
- A production, staging, shared-team, load-test, or customer-data seed.
- Automatic seeding during application, container, migration, or test-runner startup.
- Deleting all demo-user records or resetting demo data through a destructive
  `make reset-demo` command.
- Schema changes or a new migration unless implementation discovers and separately
  approves a genuine schema requirement.
- Production backup, restore, deployment, or database lifecycle operations.

## Implementation Record

Complete this section during Commit 5. Keep the table of contents synchronized if its
headings change or more sections are added.

### Overview

Record the final seed command, backend architecture, transaction boundary, clock
injection, and dataset-reconciliation strategy implemented by DEV-007.

### What It Achieved

Record the verified contributor outcomes, dashboard/statistics coverage, secure demo
identity, and opportunity-cost coverage.

### Demo Dataset

Record every stable demo UUID or logical key, representative field values, relative
timestamp, expected bucket/range, and whole/fractional opportunity-cost relationship.

### Safety and Idempotency

Record the final production, environment, host, database-name, migration-head,
collision, transaction, and non-demo preservation guarantees.

### Verification

Record the exact local commands, test counts, fixed clock, database target, repeated-run
results, Alembic status, tracked-artifact audit, and passing CI jobs used to complete
DEV-007.

### Limitations and Follow-up

Record the dependency on later authentication and product features, any manual
inspection that remains unavailable, and future changes that must preserve seed safety
and determinism.
