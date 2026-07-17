# Backend Implementation Plan

## Scope and Architecture

The backend exposes `/api`, authenticates cookie sessions, applies ownership and lifecycle rules, persists with PostgreSQL, and returns frontend-ready representations. Use FastAPI with async SQLAlchemy 2.x and Pydantic v2.

Dependency direction:

```text
router -> service -> repository -> SQLAlchemy/database
             |          |
          schemas      models
```

Routers handle HTTP translation. Services define transactions and business decisions. Repositories issue scoped queries. Models represent persistence. Pydantic schemas define external contracts. No layer may import routers from a lower layer.

## Package Structure

```text
backend/app/
  main.py
  api/
    router.py
    dependencies.py
    errors.py
    routes/
      auth.py
      entries.py
      stats.py
      opportunity_costs.py
      health.py
  core/
    config.py
    logging.py
    security.py
    time.py
  db/
    base.py
    session.py
  models/
    user.py
    session.py
    entry.py
    opportunity_cost.py
  repositories/
    users.py
    sessions.py
    entries.py
    opportunity_costs.py
  schemas/
    auth.py
    common.py
    entries.py
    stats.py
    opportunity_costs.py
  services/
    auth.py
    entries.py
    stats.py
    opportunity_costs.py
backend/tests/
  api/
  services/
  repositories/
  conftest.py
  factories.py
```

## Configuration

Use `pydantic-settings` with a cached `Settings` object. Environment variables:

| Variable | Required | Meaning |
|---|---:|---|
| `APP_ENV` | no | `development`, `test`, or `production` |
| `DATABASE_URL` | yes | `postgresql+psycopg://...` |
| `FRONTEND_ORIGIN` | yes outside test | exact permitted browser origin |
| `SESSION_COOKIE_NAME` | no | default `penny_saved_session` |
| `SESSION_TTL_SECONDS` | no | default 2,592,000 (30 days) |
| `SESSION_COOKIE_SECURE` | production true | require HTTPS |
| `LOG_LEVEL` | no | default `INFO` |

Fail startup on missing/invalid production configuration. Never accept wildcard CORS with credentials. Development may load a local `.env`; production secrets come from the deployment environment.

## Application Lifecycle and Dependencies

- `main.py` builds the FastAPI app, registers middleware, exception handlers, and the versioned router.
- Create one async SQLAlchemy engine for the process and dispose it at shutdown.
- `get_db_session` yields one `AsyncSession` per request. Services explicitly commit; dependency cleanup rolls back open transactions.
- `get_clock` returns an injectable UTC clock so request operations share a consistent `now`.
- `get_current_user` resolves the cookie session and raises the standard `401` error.
- Health endpoints: `/api/health` for process liveness and `/api/ready` for a bounded `SELECT 1` readiness check.

## Authentication and Sessions

### Passwords

- Hash with Argon2id through `pwdlib`/argon2 using library-recommended parameters.
- Enforce 8–128 Unicode characters in V1; reject values longer than the hashing library's safe input rather than truncating.
- Rehash after successful login when parameters become outdated.
- Login always returns the same `invalid_credentials` response whether email is absent or password is wrong.

### Session creation

1. Generate 32 random bytes with `secrets.token_urlsafe(32)`.
2. Hash the raw token with SHA-256 and store only the 64-character hex digest.
3. Create a session with the configured expiry.
4. Return the raw token only through `Set-Cookie`.

Cookie attributes:

```text
HttpOnly=true
Secure=true in production
SameSite=Lax
Path=/
Max-Age=SESSION_TTL_SECONDS
```

SameSite Lax plus same-origin production deployment is the V1 CSRF defense. State-changing endpoints must additionally reject cross-site requests using `Origin` validation against `FRONTEND_ORIGIN`; requests without Origin are allowed for non-browser clients only if they otherwise authenticate. If frontend/backend become cross-site, introduce a CSRF token design before changing SameSite.

### Session resolution

- Missing/malformed cookie: `401` without a database error leak.
- Hash presented token and look up by unique digest, joining the user.
- Reject and delete expired sessions.
- Throttle `last_used_at` writes to at most once per hour to avoid a write on every request; expiry remains absolute, not sliding.
- Logout deletes only the presented valid session and clears the cookie with matching name/path/attributes. It is idempotent and returns `200`.

### Auth endpoint behavior

| Endpoint | Success | Important failures |
|---|---:|---|
| `POST /auth/signup` | `201`, user, cookie | `422`, `duplicate_email` `409` |
| `POST /auth/login` | `200`, user, cookie | `invalid_credentials` `401` |
| `POST /auth/logout` | `200`, cleared cookie | idempotent |
| `GET /auth/me` | `200`, user | `unauthorized` `401` |

Catch the database unique violation on signup to handle concurrent duplicate requests; prechecking alone is insufficient.

## Validation and Response Schemas

Pydantic input models use `extra='forbid'` and field/string constraints. Service functions normalize text after validation:

- Required text: strip outer whitespace; reject empty.
- Optional comment: strip; convert empty to `None`.
- Email: strip and lowercase.
- `price_cents` and `dollar_value_cents`: strict integers, excluding booleans, within database bounds.
- Enum inputs accept only documented string values.

Response models use `from_attributes=True` only for deliberate mapping. Provide functions `to_entry_response(model, now)` and `to_example_response(model)` so derived fields are uniform.

Entry response always includes `updated_at`, including create/list responses, to make the contract consistent. `dashboard_bucket` and `eligible_for_check_in_at` are calculated from the same request clock.

## Error Handling

Define domain exceptions such as `NotFound`, `LifecycleConflict`, `EarlyCheckIn`, and `DuplicateEmail`. Central FastAPI handlers map them to the standard envelope. Override request validation handling to return `validation_error` with safe per-field messages.

- Never return raw Pydantic, SQLAlchemy, or traceback details.
- Owned-resource queries first return no data on a scoped miss. A minimal existence query then distinguishes absent (`404`) from owned by another user (`403`) to follow `SYS-004`; neither response reveals owner identity or resource fields.
- Malformed UUID path parameters return `422` consistently.
- Database availability errors return generic `503`; unexpected errors return `500` and include the request ID in logs.

## Entry Service

### Create

- Accept authenticated user and normalized payload.
- Assign UUID, `waiting`, null comment/check-in, and one clock value for timestamps.
- Commit and return a mapped entry using the same clock.

### List and detail

- Repository calls always take `user_id`.
- Dashboard listing returns four arrays, including empty arrays, with deterministic ordering from the database plan.
- Detail maps its current bucket using request time.

### Update and delete

- Lock the owned entry for mutation.
- If status is not waiting, raise `conflict`/`invalid_entry_status` with `409`.
- Update only the three allowed core fields and `updated_at`.
- Delete only waiting entries and return `204` with no body.

An old waiting entry remains technically editable/deletable until checked in because `SYS-003` restricts by stored status, not derived bucket. The frontend may still encourage check-in first.

### Check-in

Inside one transaction:

1. Select the owned entry `FOR UPDATE`.
2. If status is not waiting, return `invalid_entry_status` `409`.
3. Calculate `eligible_at = created_at + timedelta(hours=48)`.
4. If `now < eligible_at`, return `early_check_in` `409`.
5. Set status to requested `saved`/`purchased`, normalized comment, and both `checked_in_at` and `updated_at` to `now`.
6. Commit and return the mapped entry.

Exactly `now == eligible_at` is eligible. The database lock makes the transition single-use.

### Comment

Lock owned entry. Only saved or purchased is allowed; waiting returns `invalid_entry_status` `409`. Modify only comment and `updated_at`, then commit.

## Statistics Service

Supported range enum:

```text
this_month
last_3_months
last_6_months
last_year
all_time
```

Use UTC half-open intervals. The repository performs the conditional aggregate defined in the database plan. Do not load all entries to Python.

Load the user's opportunity-cost examples, then calculate each equivalent with decimal arithmetic:

```text
equivalent = Decimal(total_saved_cents) / Decimal(dollar_value_cents)
```

Quantize to one decimal using `ROUND_HALF_UP`; serialize exact whole results as JSON integers and fractional results as JSON numbers with one decimal. Because JSON numeric formatting and TypeScript number semantics can blur `25.0`, the UI must not depend on the lexical form. Invalid zero values are impossible through constraints but are defensively skipped and logged.

## Opportunity Cost Service

- All repository methods require `user_id`.
- Create/update normalize label and unit and validate positive cents.
- Update permits only label, unit, and dollar value.
- List uses stable creation order.
- Delete returns `204`.
- A missing UUID returns `404`; an existing other-user UUID returns `403`, matching the common API contract.

## Transactions and Concurrency

- One service operation owns one transaction.
- Do not commit inside repositories.
- Roll back on every domain or persistence exception.
- Use row locks for entry mutations that depend on status and for example updates/deletes where last-write behavior matters.
- No external network calls occur inside database transactions.
- Translate known integrity errors; do not blanket-catch and mislabel programming errors.

## API Routing Details

Use `/api` as the application prefix and keep endpoint paths exactly as `SYS-004`. Explicitly declare response models and status codes. For `204`, return an empty `Response(status_code=204)`.

Generate OpenAPI in non-production and use it to detect accidental contract drift. Add route operation IDs stable enough for future client generation. API changes require updating schemas, tests, and planning documents together.

## Security and Abuse Controls

- Add trusted-host and proxy settings appropriate to deployment.
- Add request ID middleware and conservative security headers.
- Limit JSON request body size at the server/proxy layer.
- Rate-limit signup/login by IP and normalized account key; use a shared store if multiple backend instances run.
- Password comparison relies on the hashing library's timing-safe behavior.
- A `403` necessarily confirms that an ID exists because `SYS-004` requires it; reveal no owner identity or resource fields and revisit this contract before a public security review.
- Redact `Cookie`, `Set-Cookie`, authorization values, passwords, and session digests from logs.
- Keep dependencies locked and scan them in CI.

## Observability

Structured logs include timestamp, level, environment, request ID, method, route template, status, latency, and user ID when resolved. Metrics should include request rate/latency/error count, database pool utilization, auth failures, lifecycle conflicts, and readiness status. Avoid high-cardinality entry IDs in metric labels.

## Backend Tests

### Service tests

- Email/comment/text normalization and password hashing.
- Session creation stores only digest; expiry and last-used throttling.
- Entry create/update/delete state matrix.
- Check-in immediately before, exactly at, and after 48 hours.
- Second/concurrent check-in conflict.
- Stats ranges, saved/purchased inclusion, and opportunity rounding.

### API integration tests

- Exact success status and response shape for every endpoint.
- Cookie attributes and logout clearing.
- Missing, invalid, and expired sessions.
- Field validation, forbidden extra fields, malformed UUID/JSON.
- User A cannot list/read/change/delete User B data.
- All lifecycle conflicts use correct code/status.
- `204` responses contain no JSON body.
- Database rollback leaves no partial state after failure.

Use a real isolated PostgreSQL database. Override the session and clock dependencies. Factories must create explicit users and timestamps; no test relies on wall-clock sleep.

## Quality Commands and Acceptance

```text
ruff check .
ruff format --check .
pytest
alembic upgrade head
alembic check
```

Backend completion requires passing lint/tests, migration validation on a clean database, documented OpenAPI matching `SYS-004`, ownership coverage for every resource route, deterministic clock-boundary tests, and confirmation that logs/database contain neither plaintext passwords nor raw session tokens.
