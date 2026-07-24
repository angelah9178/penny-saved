# DEV-005 — Add Initial Database Models and Migration

## Commit Tracker

Change `[ ]` to `[x]` only after the commit's implementation and commit gate are complete.

|  | Commit | Title | Depends on |
|---|---|---|---|
| &#91;x&#93; | [1](#commit-1--add-the-shared-orm-foundation-and-user-model) | Add ORM foundation and user model | — |
| &#91;x&#93; | [2](#commit-2--add-the-session-model) | Add secure session persistence | Commit 1 |
| &#91;x&#93; | [3](#commit-3--add-the-entry-model) | Add impulse-purchase entry persistence | Commit 1 |
| &#91;x&#93; | [4](#commit-4--add-the-opportunity-cost-example-model) | Add opportunity-cost persistence | Commit 1 |
| &#91;x&#93; | [5](#commit-5--configure-alembic-and-create-the-initial-migration) | Add Alembic and the initial schema migration | Commits 1–4 |
| &#91;x&#93; | [6](#commit-6--add-postgresql-schema-and-migration-tests) | Verify PostgreSQL constraints and migrations | Commit 5 |
| &#91;x&#93; | [7](#commit-7--document-and-verify-the-completed-database-foundation) | Document DEV-005 database foundation | Commits 1–6 |

## Objective

Build the first durable PostgreSQL schema in small, independently reviewable commits.
DEV-005 adds SQLAlchemy models for users, sessions, impulse-purchase entries, and
opportunity-cost examples, then creates one reviewed Alembic migration that reproduces
that schema from an empty database.

Each step adds a distinct part of the persistence layer. The model commits define the
intended schema in application code; the migration commit turns that design into
versioned PostgreSQL operations; the database-test commit proves PostgreSQL enforces the
design in practice.

Complete and commit each section in order. Every commit must leave the backend checks
green before work begins on the next commit. Run backend commands from `backend/`.
Commands that exercise the real schema require the dedicated PostgreSQL test database
configured by `TEST_DATABASE_URL`.

## Commit 1 — Add the Shared ORM Foundation and User Model

The ORM foundation is the shared setup that lets SQLAlchemy represent database tables as
Python classes. It defines the common base that every database model—users, sessions,
entries, and opportunity-cost examples—will inherit from. It also establishes the
conventions every later model follows, including typed mappings, UUID primary keys,
timezone-aware timestamps, explicit names, and relationships that refuse accidental
lazy loading.

Users are created first because they are the ownership foundation for the other records
and the starting point for the user data flow:

```text
User
├── Sessions
├── Impulse-purchase entries
└── Opportunity-cost examples
```

Each session, entry, and opportunity-cost example contains a `user_id` foreign key that
connects it to its owner. This ownership link allows the application to ensure that each
user sees and manages only their own information.

The user's sessions, entries, and opportunity-cost examples remain in separate tables
connected through `user_id`. This avoids duplicating account information and keeps each
kind of data independently manageable. Unlike the later commits, this step focuses on
the shared ORM structure and user identity rather than the dependent authentication and
product records.

Suggested commit message:

```text
Add ORM foundation and user model
```

Implement:

- Add the shared SQLAlchemy declarative base under `backend/app/db/`.
- Add a separate `User` persistence model under `backend/app/models/`.
- Map `id`, normalized `email`, `password_hash`, `created_at`, and `updated_at`.
- Use application-supplied UUIDv4 identifiers and timezone-aware timestamps without
  model hooks or mutable server defaults.
- Add the explicitly named unique email index and nonblank-email check constraint.
- Establish the relationship conventions (`lazy="raise"` and delete-orphan ownership);
  add each typed user relationship with its target model in Commits 2–4 so every
  intermediate commit remains runnable.
- Export all model metadata through one deliberate import location for Alembic.
- Add metadata-focused tests for table names, column types, nullability, names,
  relationships, and the absence of plaintext-password persistence fields.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/models/test_user.py
```

## Commit 2 — Add the Session Model

This commit creates the database representation of login sessions. A session records
which user is logged in, stores only a secure SHA-256 hash of the session token, and
tracks when the session was created, when it expires, and when it was last used. These
timestamps provide the information needed to determine how long a user stays logged in
and to support later session-refresh and cleanup rules.

The eventual login flow will be:

```text
User logs in
    ↓
Backend creates a random session token
    ↓
Database stores only the token's SHA-256 hash
    ↓
Browser receives the raw token in a secure HttpOnly cookie
    ↓
Future requests use the cookie to identify the session
    ↓
Session remains valid until logout, revocation, or expiration
```

The `expires_at` value will later be calculated from the creation time and the configured
`SESSION_TTL_SECONDS`. The `last_used_at` value records recent activity, but it does not
automatically extend the session lifetime; DEV-008 will define and implement the exact
refresh behavior.

Commit 1 established who owns data; Commit 2 adds short-lived authentication state for
that owner. It is intentionally limited to storage rules—token generation, cookies,
session refresh, and authentication behavior remain part of DEV-008.

Suggested commit message:

```text
Add secure session model
```

Implement:

- Add a separate `Session` model mapped to `sessions`.
- Map `id`, `user_id`, `session_token_hash`, `expires_at`, `created_at`, and
  `last_used_at`.
- Add the named user foreign key with `ON DELETE CASCADE`.
- Add the named unique token-hash index plus indexes for `user_id` and `expires_at`.
- Require expiry after creation and last use at or after creation.
- Store only the fixed-length lowercase SHA-256 digest representation; do not add a raw
  session-token column.
- Add metadata-focused tests for ownership, indexes, constraints, column shape, and the
  absence of raw-token persistence fields.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/models/test_session.py
```

## Commit 3 — Add the Entry Model

This commit defines how an impulse purchase is stored in PostgreSQL after a user creates
it. Each entry records:

- The user who owns it.
- The item name.
- The price as integer cents.
- Why the user wanted the item.
- Its current status.
- An optional check-in comment.
- When it was created, checked in, and last updated.

The stored lifecycle is:

```text
Entry created
    ↓
waiting
    ↓ after the waiting period
User checks in
    ├── saved
    └── purchased
```

The database prevents invalid stored combinations. A `waiting` entry cannot have a
`checked_in_at` time, while a `saved` or `purchased` entry must have one. Check-in and
update times cannot be earlier than the creation time, prices must remain within the
approved positive range, required text cannot be blank, and an optional comment cannot
be blank when it is present.

`needs_check_in` is not stored as another status. It is derived later from the current
time and the entry's creation time:

```text
waiting + less than 48 hours old  → waiting
waiting + at least 48 hours old   → needs check-in
```

Deriving this value prevents the database from storing an eligibility flag that becomes
outdated merely because time passes.

Unlike the authentication-focused session model, this model captures product state and
the timestamps needed for dashboards and statistics. The database prevents impossible
stored combinations, while services added later still enforce authorization, the exact
48-hour eligibility rule, and legal state transitions. Commit 3 defines the storage
model and database safeguards; it does not yet implement the entry form, API endpoints,
dashboard, or check-in operation.

Suggested commit message:

```text
Add impulse purchase entry model
```

Implement:

- Add `EntryStatus` as a Python `StrEnum` and a separate
  `ImpulsePurchaseEntry` model mapped to `impulse_purchase_entries`.
- Map the owner, item name, price cents, reason wanted, status, optional comment, and
  lifecycle timestamps using the designed lengths and PostgreSQL-compatible types.
- Add the named user foreign key with `ON DELETE CASCADE`.
- Add named checks for supported statuses, nonblank text, bounded positive cents,
  status/check-in consistency, and timestamp ordering.
- Add the dashboard and statistics indexes with their required descending columns.
- Keep `needs_check_in` derived from `created_at`; do not persist a bucket or eligibility
  column.
- Add metadata-focused tests for columns, enum values, constraints, indexes, and
  relationship behavior.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/models/test_entry.py
```

## Commit 4 — Add the Opportunity-Cost Example Model

This commit adds user-owned examples that later translate saved money into relatable
units. For example, a user could define coffee as `$5.00` per cup. If they later save
`$20.00`, the application can describe that amount as four cups of coffee.

Each database record stores:

- The user who owns the example through `user_id`.
- A descriptive label, such as `Coffee`.
- A unit name, such as `cups`.
- The value of one unit as integer cents.
- Creation and update timestamps.

The model ensures:

- Labels and unit names cannot be blank.
- The integer-cent value is positive and within the approved maximum.
- `updated_at` cannot be earlier than `created_at`.
- Deleting a user also deletes their opportunity-cost examples.
- Every example remains connected to its owner.
- The listing order remains stable when examples have equal creation times.
- Duplicate labels remain allowed because similarly named examples may intentionally
  have different units or values.

This is the final model commit. It differs from entries because it represents reusable
comparison settings rather than purchase lifecycle data, so duplicate labels are valid
and stable creation order is more important than status-based indexing. Commit 4 only
defines database storage and safeguards; creating, editing, deleting, displaying, and
calculating equivalents are implemented later in DEV-017–DEV-019.

Suggested commit message:

```text
Add opportunity cost example model
```

Implement:

- Add a separate `OpportunityCostExample` model mapped to
  `opportunity_cost_examples`.
- Map `id`, `user_id`, `label`, `unit_name`, `dollar_value_cents`, `created_at`, and
  `updated_at`.
- Add the named user foreign key with `ON DELETE CASCADE`.
- Add named checks for nonblank label and unit, bounded positive cents, and timestamp
  ordering.
- Add the stable-listing index on `user_id`, `created_at`, and `id`.
- Allow duplicate labels; do not add a label uniqueness constraint.
- Add metadata-focused tests for columns, constraints, ownership, duplicate-label
  support, and stable-order indexing.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/models/test_opportunity_cost_example.py
```

## Commit 5 — Configure Alembic and Create the Initial Migration

The previous commits describe the target schema as SQLAlchemy metadata. This commit makes
that schema deployable by configuring Alembic and recording the exact operations needed
to create or remove it.

One way to understand the relationship is to imagine constructing and maintaining a
building:

```text
SQLAlchemy models → the architect's current blueprints
Migration files   → the numbered construction and renovation instructions
Alembic           → the construction manager that executes those instructions
PostgreSQL        → the actual building where the data lives
```

The SQLAlchemy models describe what the database should look like from the application's
perspective. PostgreSQL is the real database that stores the tables and records, but it
does not read the model classes and rebuild itself automatically. Migration files contain
the reviewed `upgrade()` and `downgrade()` instructions. Alembic acts as the construction
manager: it reads those files, determines which instructions PostgreSQL has already
received, executes the missing operations, and records the newest applied revision in
PostgreSQL.

A migration is one numbered set of database changes. Alembic records which migrations a
database has already applied, allowing a new local, test, or production database to
reach the same structure in the same order. Future schema changes receive new migrations
instead of requiring developers to edit databases manually or rewrite previously
applied migration files.

The initial migration creates:

1. The `users` table.
2. The `sessions` table and its indexes.
3. The `impulse_purchase_entries` table and its indexes.
4. The `opportunity_cost_examples` table and its index.

Together, these operations create the approved columns, PostgreSQL data types, primary
and foreign keys, check constraints, unique rules, cascading deletion behavior, and
performance indexes. The user-owned tables are created after `users` because their
`user_id` foreign keys depend on it.

The initial revision creates tables in dependency order and drops them in reverse order.
Its `upgrade()` and `downgrade()` operations are self-contained: the revision must not
import mutable application models, because an old migration must keep the same meaning
as the application evolves.

The migration's `upgrade()` builds the schema. Its `downgrade()` removes the schema in
reverse dependency order, deleting the user-owned tables before `users` so foreign keys
do not block the operation.

Suggested commit message:

```text
Add initial database migration
```

Implement:

- Add `backend/alembic.ini` and the Alembic environment under `backend/alembic/`.
- Load the validated database URL and complete model metadata without exposing
  credentials in logs.
- Configure PostgreSQL migrations and metadata comparison for types, defaults, indexes,
  constraints, and names.
- Add one initial revision that creates `users`, `sessions`,
  `impulse_purchase_entries`, and `opportunity_cost_examples` in dependency order.
- Name every foreign key, unique rule, check constraint, and index explicitly.
- Write a complete downgrade that removes indexes and tables in reverse dependency
  order.
- Keep the revision self-contained with Alembic operations and stable SQLAlchemy types;
  do not import application model definitions from the revision.
- Confirm the existing `make db-upgrade`, `make db-downgrade`, and
  `make db-revision` workflows recognize the new configuration.

Commit gate:

```text
ruff format --check .
ruff check .
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

## Commit 6 — Add PostgreSQL Schema and Migration Tests

This commit proves that the model and migration design works against PostgreSQL rather
than only looking correct in Python. It tests actual constraint failures, cascading
deletes, migration reversibility, and drift between Alembic head and model metadata.

Here, “real PostgreSQL” means the actual PostgreSQL database engine running in Docker,
not production data or records created by real users. Commit 6 uses a separate,
disposable test database identified by `TEST_DATABASE_URL`. Tests can safely create
invalid and valid sample records, remove tables, and rebuild the schema without changing
the normal development database.

In simple terms, the database tools have different responsibilities. Using the same
building metaphor:

| Tool | Technical role | Building metaphor |
|---|---|---|
| SQL | The language used to give database instructions. | The shared language used to describe construction work and request information from the building. |
| PostgreSQL | The database software that stores data and executes SQL. | The actual building, including the staff who store, find, protect, and update everything inside it. |
| SQLAlchemy | The Python toolkit that maps classes and Python operations to SQL. | The interpreter that translates the application's Python requests into instructions the building staff understand. |
| Models | The Python description of the application's intended tables, columns, and relationships. | The architect's current blueprints describing how the finished building should be arranged. |
| Migrations | Versioned instructions for changing the database structure. | Numbered construction and renovation plans explaining how to build or modify the structure step by step. |
| Alembic | The tool that executes and tracks migrations. | The construction manager who identifies unfinished plans, directs the work, and records which renovations are complete. |
| Commit 6 tests | Verification of the resulting structure in a disposable PostgreSQL database. | Building inspectors who test the finished structure, safety rules, locks, and connections before it is approved. |

The development database created through `make db-up` and the test database both use the
same PostgreSQL engine, but they serve different purposes. The development database
holds local application data while a developer uses the application. The test database
exists for automated verification and may be repeatedly emptied or rebuilt.

This differs from the earlier metadata tests: those quickly inspect declarations, while
these integration tests execute the resulting schema and verify PostgreSQL is the final
enforcement boundary.

Suggested commit message:

```text
Add database schema integration tests
```

Implement:

- Require an explicit `TEST_DATABASE_URL` that points to PostgreSQL; never derive it from
  the development `DATABASE_URL`.
- Add isolated test-database fixtures that apply migrations and clean up safely without
  targeting a shared or production database.
- Test unique email and session-token digests.
- Test every nonblank, bounded-cent, status, lifecycle, expiry, and timestamp constraint
  with failing inserts or updates.
- Test deletion of a user cascades to sessions, entries, and opportunity-cost examples.
- Verify duplicate opportunity-cost labels remain allowed.
- Verify an empty database can upgrade to head, downgrade to base, and re-upgrade.
- Add a drift check proving the schema at migration head matches SQLAlchemy metadata.
- Inspect the migrated schema to verify all expected tables, columns, foreign keys,
  constraints, and indexes exist with their approved names.

Commit gate:

```text
ruff format --check .
ruff check .
pytest tests/models tests/integration/test_database_schema.py tests/integration/test_migrations.py
```

## Commit 7 — Document and Verify the Completed Database Foundation

This final commit records how contributors create, migrate, verify, and safely evolve the
database. It does not add another schema feature; it confirms that the preceding model,
migration, and integration-test commits work together as one reproducible foundation.

Suggested commit message:

```text
Document initial database foundation
```

Implement:

- Update the root README with the initial migration workflow and relevant
  troubleshooting.
- Document that migrations are the only supported way to change shared schemas.
- Document the required local PostgreSQL and explicit test-database configuration.
- Explain migration review rules, including forward and reverse review, stable applied
  revisions, and the prohibition on importing mutable models into revision files.
- Record the completed DEV-005 implementation, verification results, limitations, and
  follow-up work in this document.
- Run the complete backend suite and migration cycle.
- Confirm no local environment file, database dump, credential, raw token, plaintext
  password, or generated cache artifact is tracked.

Commit gate:

```text
ruff format --check .
ruff check .
pytest
alembic downgrade base
alembic upgrade head
alembic check
git diff --check
```

## Out of Scope

DEV-005 establishes persistence structure and migration safety. It does not implement:

- Signup, login, logout, password hashing, cookie handling, session resolution, or
  session cleanup; those belong to DEV-008.
- Entry repositories, CRUD routes, dashboard partitioning, authorization, or statistics
  queries; those begin in DEV-010 and DEV-016.
- Atomic 48-hour check-in behavior; that belongs to DEV-013.
- Opportunity-cost CRUD behavior or calculations; those belong to DEV-017 and DEV-018.
- Deterministic demo data; that belongs to DEV-007.
- GitHub Actions and the final combined migration CI job; those belong to DEV-006.
- Production deployment, backups, retention jobs, or account-deletion UI.

## Implementation Record

### Overview

DEV-005 established the first versioned PostgreSQL schema for A Penny Saved. It added a
shared typed SQLAlchemy foundation, separate persistence models for users, login
sessions, impulse-purchase entries, and opportunity-cost examples, and a self-contained
Alembic revision that builds all four tables in dependency order.

The database design now exists in two complementary forms: model metadata describes the
schema expected by current application code, while the migration history provides the
stable instructions used to construct actual databases.

### What It Achieved

- UUID-owned user data is separated into account, session, entry, and opportunity-cost
  tables with explicit bidirectional relationships and cascading foreign keys.
- Session storage contains only fixed-length SHA-256 token digests; no raw-token or
  plaintext-password persistence column exists.
- Entry status, lifecycle timestamps, nonblank fields, optional comments, and bounded
  integer-cent prices are protected by named PostgreSQL constraints.
- Opportunity-cost examples preserve positive bounded values, allow duplicate labels,
  and have deterministic per-user listing order.
- Dashboard, statistics, session-resolution, expiry-cleanup, and stable-listing indexes
  are explicitly named and represented in both metadata and the migration.
- The initial migration upgrades an empty database, downgrades to base, and re-upgrades
  without model/migration drift.
- A dedicated PostgreSQL integration suite verifies real constraint enforcement,
  cascading deletion, schema objects, migration reversibility, and metadata agreement.

### Usage and Safety

Start local PostgreSQL and apply pending development migrations from the repository root:

```text
make db-up
make db-upgrade
```

Create future revisions with `make db-revision message="describe_change"`, review both
directions, and never edit a revision already applied to a shared environment. Migration
files remain self-contained and do not import mutable application models.

Integration tests require an explicit PostgreSQL `TEST_DATABASE_URL` whose database name
ends in `_test`. The fixtures reject the development database, migrate only the selected
test database, isolate schema-test data with transaction rollbacks, and leave the test
schema at Alembic head. Local `.env` files, credentials, dumps, raw session tokens, and
plaintext passwords must never be committed.

### Verification

The final DEV-005 verification includes:

```text
ruff format --check .
ruff check .
pytest
alembic downgrade base
alembic upgrade head
alembic check
git diff --check
```

Focused coverage verifies every model declaration; every migrated table, column, primary
key, foreign key, check constraint, and index; unique emails and token digests; invalid
text, cent, status, lifecycle, and timestamp values; cascading user deletion; allowed
duplicate opportunity-cost labels; migration cycling; and model/migration drift.

Verification performed for Commit 7:

- Ruff formatting and lint checks passed.
- All 122 backend tests passed, including the live PostgreSQL integration suite.
- The development database successfully downgraded to base and re-upgraded to
  `0001_initial_schema`.
- Alembic reported no model-to-migration upgrade operations.
- Both the development and dedicated test databases finished at migration head.
- `git diff --check` and the tracked-artifact audit passed.

### Limitations and Follow-up

- DEV-006 must add the combined root quality commands and continuous-integration
  PostgreSQL migration job.
- DEV-007 must add guarded, deterministic development demo data.
- DEV-008 must implement password hashing, token generation, cookies, session expiry,
  and authentication behavior using the user/session tables.
- DEV-010 and DEV-013 must add owned entry repositories, CRUD, dashboard grouping, and
  atomic 48-hour check-ins.
- DEV-016–DEV-019 must add statistics queries and opportunity-cost CRUD/calculations.
- Production backup, restore, retention, account deletion, and deployment procedures
  remain release and operations work.
