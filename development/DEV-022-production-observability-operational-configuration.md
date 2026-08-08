# DEV-022 — Production Operations

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Operational Rules](#operational-rules)
- [Commit 1 Contracts](#commit-1-contracts)
- [Commit 1 — Define the Production Operations Contract](#commit-1--define-the-production-operations-contract)
- [Commit 2 — Add Structured Request Logging and Correlation](#commit-2--add-structured-request-logging-and-correlation)
- [Commit 3 — Add Safe Application Metrics](#commit-3--add-safe-application-metrics)
- [Commit 4 — Complete Health and Process Lifecycle Behavior](#commit-4--complete-health-and-process-lifecycle-behavior)
- [Commit 5 — Document the Production Configuration and Runbook](#commit-5--document-the-production-configuration-and-runbook)
- [Commit 6 — Verify the Complete Operational Boundary](#commit-6--verify-the-complete-operational-boundary)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|             | Commit                                                        | Short title                    | Depends on          |
| ----------- | ------------------------------------------------------------- | ------------------------------ | ------------------- |
| &#91;x&#93;      | [1](#commit-1--define-the-production-operations-contract)     | Define the operations contract | DEV-003 and DEV-021 |
| &#91;x&#93;      | [2](#commit-2--add-structured-request-logging-and-correlation) | Add correlated request logs    | Commit 1            |
| &#91;x&#93;      | [3](#commit-3--add-safe-application-metrics)                  | Add bounded metrics            | Commits 1–2         |
| &#91;x&#93;      | [4](#commit-4--complete-health-and-process-lifecycle-behavior) | Complete health and lifecycle  | Commits 1–2         |
| &#91;&#160;&#93; | [5](#commit-5--document-the-production-configuration-and-runbook) | Document production operations | Commits 1–4      |
| &#91;&#160;&#93; | [6](#commit-6--verify-the-complete-operational-boundary)      | Verify operational behavior    | Commits 1–5         |

## Objective

DEV-022 makes the application understandable and operable after it is started in
production. It does not add a customer-facing feature and it does not deploy the
application.

In plain English, this work answers questions such as:

- When a user reports an error, can an operator find the matching server event?
- Can the operator tell which route failed without logging a private entry ID?
- Can monitoring distinguish a running process from one that is ready for traffic?
- What happens when PostgreSQL is temporarily unavailable?
- Can logs and metrics explain slow or failing requests without exposing secrets?
- Can the service start, stop, and restart cleanly under a process supervisor?
- Is there one safe example of the production settings the Oracle VPS will need?
- Are backup, restore, TLS, proxy, and rollback expectations written down before a
  real release is attempted?

The result is an operational contract: safe machine-readable evidence from the
application and clear instructions for the person responsible for it. DEV-024 will
use this contract during final release validation.

## Operational Rules

These rules apply throughout the implementation:

- Logs go to standard output/error. Production infrastructure owns collection,
  rotation, retention, and access control.
- Production application logs are structured JSON with stable field names. Local
  development may retain a readable format.
- Use the route template, such as `/api/entries/{entry_id}`, in logs and metric
  labels. Never use a raw URL, query string, email, entry ID, session value, request
  body, or other unbounded user value as a label.
- Accept a client request ID only when it matches a small documented character and
  length policy. Otherwise generate a new cryptographically unpredictable value.
- Return the effective request ID in the response and include it in every log event
  for that request.
- Keep exception details and stack traces server-side. The client receives the
  existing safe error envelope plus its correlation ID, not internal details.
- A liveness check answers only whether the application process can respond. A
  readiness check answers whether the instance can safely receive normal traffic.
- Health responses must be fast, small, unauthenticated, and non-sensitive. They do
  not expose versions, credentials, database addresses, stack traces, or dependency
  internals.
- A database outage makes readiness fail with `503 Service Unavailable`; it must not
  make the lightweight liveness endpoint depend on the database.
- Startup configuration is validated before serving traffic. Shutdown stops taking
  new work, releases owned resources, and finishes within a documented supervisor
  timeout.
- Production examples contain names and placeholders, never usable credentials,
  private keys, cookies, database passwords, or tokens.
- Documentation may describe commands that an authorized operator will run later,
  but DEV-022 does not provision infrastructure, change DNS, obtain certificates,
  access production data, or deploy a release.

## Commit 1 Contracts

Commit 1 establishes five promises that the later implementation commits must keep.

### 1. Structured Logging Contract

Every completed HTTP request will produce one structured event with these required
fields: `timestamp`, `level`, `environment`, `event`, `request_id`, `method`,
`route`, `status`, and `duration_ms`. A safely resolved `user_id` and bounded
`context` may be present when relevant.

The `route` value is a route template such as `/api/entries/{entry_id}`, never the
raw URL. Requests that cannot be matched use the fixed value `unmatched`. Logs do
not include query strings, request or response bodies, passwords, cookies,
authorization values, session tokens, database credentials, emails, client IPs, or
raw user/resource identifiers. Production uses newline-delimited JSON on standard
output/error; collection and retention belong to the host infrastructure.

### 2. Request-Correlation Contract

The correlation header is `X-Request-ID`. An inbound value is accepted only when it
is a canonical UUID no longer than 36 characters. A missing or invalid value is
replaced with a newly generated UUID. The effective value is returned in the
response, remains isolated between concurrent requests, and is included in all log
events associated with that request.

Expected failures keep the approved safe error response. An unexpected failure also
returns the effective request ID so an operator can locate the private server-side
trace without sending exception details to the client.

### 3. Metrics Contract

The private metrics path is `/internal/metrics`. Commit 3 will implement these
definitions:

| Metric name                            | Type      | Unit        | Allowed labels                       | Operator question                         |
| -------------------------------------- | --------- | ----------- | ------------------------------------ | ----------------------------------------- |
| `http_server_requests_total`           | Counter   | requests    | method, route, status class          | How much traffic is the API receiving?    |
| `http_server_request_duration_seconds` | Histogram | seconds     | method, route                        | Which route templates are slow?           |
| `http_server_errors_total`             | Counter   | errors      | method, route, status class          | Are safe client/server errors increasing? |
| `database_pool_connections`            | Gauge     | connections | bounded connection state             | Is the database pool under pressure?      |
| `authentication_failures_total`        | Counter   | failures    | operation, bounded reason            | Are login/signup failures increasing?     |
| `entry_lifecycle_conflicts_total`      | Counter   | conflicts   | operation                            | Are state-transition conflicts rising?    |
| `application_readiness`                | Gauge     | state       | none                                 | Is the instance ready for normal traffic? |

Metric labels never contain request IDs, user IDs, emails, client IPs, entry IDs,
raw paths, query strings, bodies, error messages, or secrets. Exact allowed values
for labels such as status class, connection state, operation, and reason must remain
small and enumerated when Commit 3 instruments them.

### 4. Health-Check Contract

`GET /api/health` is the liveness endpoint. It returns `200` with
`{"status":"ok"}` when the application process can answer HTTP. It deliberately
does not query PostgreSQL, so a separate database outage does not tell the process
supervisor to restart a live application.

`GET /api/ready` is the readiness endpoint. It performs a database probe within the
configured timeout. It returns `200` with `{"status":"ready"}` when ordinary work
can be served and `503` with `{"status":"unavailable"}` when the dependency is not
ready. Neither response exposes versions, addresses, credentials, or error details.

### 5. Configuration Contract

The operational settings are:

| Environment variable                 | Type    | Default | Valid range/values        | Production rule                 |
| ------------------------------------ | ------- | ------- | ------------------------- | ------------------------------- |
| `LOG_LEVEL`                          | enum    | `INFO`  | DEBUG–CRITICAL            | Explicit supported level        |
| `LOG_FORMAT`                         | enum    | `json`  | `json`, `text`            | Must be `json`                  |
| `HEALTH_CHECK_TIMEOUT_SECONDS`       | decimal | `2.0`   | 0.1 through 30.0 seconds  | Must remain within bounds       |
| `METRICS_ENABLED`                    | boolean | `false` | `true`, `false`           | Safe opt-in exposure            |
| `GRACEFUL_SHUTDOWN_TIMEOUT_SECONDS`  | integer | `30`    | 1 through 300 seconds     | Must remain within bounds       |

Unsupported enum values and out-of-range timeouts fail settings validation before
the application starts. Metrics remain disabled until Commit 3 supplies the private
endpoint and the production proxy/access policy is configured.

## Commit 1 — Define the Production Operations Contract

**Status:** Complete — `03dc757`.

### In Plain English

Commit 1 decides what the application will report before adding new reporting code.
It defines the fields that belong in a request log, which measurements are useful,
what “alive” and “ready” mean, and which production settings control those behaviors.

Think of this as agreeing on the dashboard instruments before wiring them into the
car. Without a stable contract, one request might be called `request_id` in one log
and `trace` in another, or a health check might say “healthy” even though the
database is unreachable. Later commits implement the definitions established here.

This commit also draws the privacy boundary. Operators need a route name, status,
timing, and correlation ID; they do not need a password, cookie, raw URL, entry UUID,
or request body. The tests added here turn that distinction into an enforceable rule.

Suggested commit message:

```text
Commit 1: Define the production operations contract
```

Implement:

- Document the structured log schema: timestamp, level, environment, event name,
  request ID, method, route template, status, duration, and authenticated user ID
  only when it has been safely resolved.
- Define behavior for unmatched routes and failures that occur before route
  resolution without falling back to a raw path containing private values.
- Define the accepted inbound request-ID header, validation policy, generated format,
  response header, and propagation through application code.
- Define the metric names, units, bounded labels, and intended operator questions for
  request rate, duration, error count, database-pool state, authentication failures,
  lifecycle conflicts, and readiness.
- Define separate liveness and readiness contracts, including status codes, response
  shapes, timeouts, and database-failure behavior.
- Add typed configuration for log level, log format, health-check timeout, metrics
  exposure, and graceful-shutdown timing where these values need to be configurable.
- Reject unsupported or unsafe production values while keeping deterministic test and
  development defaults.
- Add contract and configuration tests before behavior changes.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
git diff --check
```

## Commit 2 — Add Structured Request Logging and Correlation

**Status:** Complete — `900cba4`.

### In Plain English

Commit 2 gives every request a safe tracking number and records one consistent
completion event. If a client receives an error with request ID `abc123`, an
operator can search the server logs for that same ID and see which general route ran,
its status, and how long it took.

“Every request” means every HTTP call the browser, a monitoring tool, or another API
client sends to this backend. Examples include logging in, loading dashboard entries,
creating or editing an entry, checking an entry in, loading statistics, changing an
opportunity-cost example, calling a health endpoint, or requesting an API route that
does not exist. It is not a tracking number for one database row or one user action;
each individual HTTP exchange receives its own request ID.

For example, the browser may send `GET /api/entries/123`. The backend returns an
`X-Request-ID` response header such as
`07a541df-c2db-4e26-976e-14a03b11bc49` and writes the same value in the matching
server log. If the request fails, the user can report that ID so an operator can find
the exact server-side evidence.

The tracking number connects the public symptom to private operational evidence; it
does not expose the evidence itself. Expected client mistakes still receive concise
safe errors. Unexpected exceptions retain a full server-side traceback for diagnosis,
while the browser sees only the approved generic message and correlation ID.

The request ID does not identify the user and does not contain anything the user
submitted. It only connects one response to the server events produced while handling
that response.

For example, a request for `/api/entries/8f...` is recorded under the stable route
template `/api/entries/{entry_id}`. This lets operators group all entry-detail
requests together and prevents each private identifier from becoming a new log or
metric category.

Suggested commit message:

```text
Commit 2: Add structured request logging and correlation
```

Implement:

- Add request-context middleware that validates or generates a request ID and returns
  the effective value in a documented response header.
- Make the request ID available to route, service, error-handler, and lifecycle log
  events without global state leaking between concurrent requests.
- Emit one completion event per request with method, route template, status, duration,
  environment, and resolved user ID when available.
- Use a safe bounded fallback for unmatched routes and failures before routing; never
  log raw paths or query strings merely to fill a field.
- Configure structured JSON output in production and deterministic readable output in
  development/test as established in Commit 1.
- Log expected application errors at an appropriate level without a traceback and
  unexpected exceptions once with their traceback on the server.
- Include the request ID in every standard error response, including unexpected
  `500` responses and applicable middleware rejections.
- Preserve DEV-021 redaction for nested values, exceptions, headers, URLs, and
  multi-line messages.
- Test accepted, rejected, and generated request IDs; concurrent isolation; resolved
  and unmatched routes; authenticated and anonymous requests; streaming/failure
  behavior; safe client errors; and server-side exception correlation.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
make security-check
git diff --check
```

## Commit 3 — Add Safe Application Metrics

**Status:** Complete — `5e7428f`.

### In Plain English

Commit 3 adds counters and timings that show trends without requiring an operator to
read every log line. Metrics can answer “Are errors increasing?”, “Which kind of
request is slow?”, and “Is the database connection pool under pressure?”

Commit 2 creates a detailed record for one individual request. Commit 3 summarizes
many requests. For example, it can report that the backend handled 142 successful
`GET /api/entries/{entry_id}` requests without identifying any of the 142 request
IDs, entry IDs, or users. A monitoring system can use the duration measurements to
calculate typical response time and identify unusually slow route templates.

The measurements cover request volume, request duration, HTTP errors, database-pool
state, authentication failures, entry lifecycle conflicts, and the most recently
observed readiness state. They are exposed only when `METRICS_ENABLED=true` through
the private `/internal/metrics` endpoint. That endpoint is intended for a monitoring
service on the server’s private network, not for ordinary users or the public
internet.

Metrics are deliberately less detailed than logs. They group requests by a small set
of stable values such as route template, method, and status class. They must not use
email addresses, user IDs, entry IDs, request IDs, error messages, or raw URLs as
labels because those values can reveal private information and create an unlimited
number of time series.

This commit exposes application measurements for an already-chosen monitoring system;
it does not buy a monitoring service, create a public dashboard, or configure paging.
The production runbook will require the reverse proxy or firewall to keep the metrics
endpoint away from the public internet.

Suggested commit message:

```text
Commit 3: Add bounded operational metrics
```

Implement:

- Instrument request count, duration, and error count using method, route template,
  and bounded status information only.
- Record authentication failures and lifecycle conflicts as aggregate event counters
  without account, client-IP, resource, or submitted-value labels.
- Export supported database-pool utilization measurements without database addresses
  or credentials.
- Publish current readiness state and readiness-check outcomes as bounded metrics.
- Expose metrics in the format and at the path chosen in Commit 1, with production
  access restrictions documented and unsafe public exposure avoided by default.
- Avoid double counting when middleware rejects a request or an exception is handled.
- Document metric meanings, units, label sets, and example operator queries or alert
  conditions without claiming fixed thresholds before production baselines exist.
- Test representative success, validation, authentication, conflict, server-error,
  unmatched-route, and database-unavailable paths.
- Add a cardinality/privacy test that rejects forbidden labels and proves raw paths,
  IDs, emails, request IDs, and exception text are absent.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
make security-check
git diff --check
```

## Commit 4 — Complete Health and Process Lifecycle Behavior

**Status:** Complete — `1d5bda5`.

### In Plain English

Commit 4 makes health checks tell the truth. “Live” means the application process is
running and can answer a basic request. “Ready” means it can also reach the resources
required to serve ordinary traffic, especially PostgreSQL.

`GET /api/health` answers whether the backend process can respond to HTTP. It does
not contact PostgreSQL, so a database outage does not cause a supervisor to restart
an otherwise live process repeatedly. A successful liveness response is `200` with
`{"status":"ok"}`.

`GET /api/ready` answers whether this instance can handle normal application traffic.
It checks PostgreSQL within `HEALTH_CHECK_TIMEOUT_SECONDS`. It returns `200` with
`{"status":"ready"}` on success and a safe `503` with
`{"status":"unavailable"}` while starting, stopping, timed out, or unable to reach
the database. It never exposes a database address, credential, or exception message.

The distinction matters during an outage or restart. A supervisor should restart a
dead process, but repeatedly restarting a perfectly live application will not repair
a separate database outage. In that case liveness remains successful, readiness
returns `503`, and the reverse proxy can stop sending normal traffic until the
dependency recovers.

This commit also makes startup and shutdown predictable. The process validates its
settings and initializes required resources before becoming ready. On shutdown it
marks itself unready, stops accepting new work through the surrounding supervisor
and proxy flow, and releases its database resources cleanly.

The intended order is:

```text
Startup
  → validate configuration
  → create database resources
  → become ready

Shutdown
  → become unready
  → allow the server to finish active work within its timeout
  → close database resources
  → exit
```

This gives `systemd` or another supervisor reliable signals for starting, stopping,
and restarting the backend. Commit 4 implements the application side of that
contract; Commit 5 documents the real supervisor and reverse-proxy configuration.

Suggested commit message:

```text
Commit 4: Complete health checks and process lifecycle
```

Implement:

- Preserve or add a lightweight liveness endpoint that does not query PostgreSQL or
  disclose configuration details.
- Add the documented readiness endpoint with a bounded database probe and `503`
  behavior when the application is starting, stopping, misconfigured, timed out, or
  unable to reach PostgreSQL.
- Keep response bodies stable and minimal while including request correlation on
  failure.
- Ensure health routes remain available through the intended host/proxy boundary and
  are not blocked by authentication or ordinary user rate limits.
- Validate production settings and initialize application-owned resources before
  readiness can succeed.
- On graceful shutdown, transition readiness to failure before disposing of the
  database engine and other application-owned resources.
- Define supervisor-compatible startup, shutdown, and termination behavior with a
  finite documented timeout; do not terminate the process from a request handler.
- Emit correlated lifecycle and readiness transition logs without creating a noisy
  log event on every successful health probe.
- Test healthy startup, invalid startup, database outage and recovery, probe timeout,
  shutdown ordering, repeated lifecycle calls, and resource disposal.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
make backend-build
git diff --check
```

## Commit 5 — Document the Production Configuration and Runbook

**Status:** Implemented and verified; awaiting commit.

### In Plain English

Commit 5 turns the application behavior into instructions an authorized operator can
follow later. It provides a secret-free production configuration example for
`stopimpulsebuying.us` and explains how the reverse proxy, application supervisor,
PostgreSQL, TLS, logs, metrics, backups, and restores fit together on the Oracle VPS.

The production environment example lists required settings such as
`APP_ENV=production`, the approved HTTPS origin, secure cookies, JSON logs, and
opt-in metrics. Database and rate-limit secrets remain obvious `REPLACE_WITH`
placeholders; populated credentials are stored outside the repository.

The reverse-proxy example serves the built frontend, sends `/api` traffic to FastAPI
over loopback, preserves the trusted proxy boundary, applies matching request-size
and timeout limits, supports the React route fallback, terminates HTTPS, and prevents
public access to `/internal/metrics`. The supervisor example runs the backend as a
non-root account, loads secrets from `/etc`, restarts unexpected failures, sends logs
to the journal, and allows graceful shutdown without automatically running database
migrations.

The runbook also defines TLS-renewal ownership, loopback-only PostgreSQL, log and
metric access, database-outage diagnosis, disk-growth checks, backup creation,
checksum verification, isolated restore rehearsal, and application-versus-database
rollback boundaries. A backup is not considered proven until a separate disposable
database restore has succeeded.

This is a design and rehearsal document, not a deployment. Placeholder values show
where a secret belongs without inventing or storing the real secret. Example proxy
and supervisor configuration must be reviewed for the actual server paths, users,
ports, and certificate tooling before it is installed.

Commit 5 does not connect to the Oracle VPS, install Nginx or a service unit, change
DNS or firewall rules, obtain a certificate, create a production secret, run a
production backup or restore, or deploy the application. Every unresolved host
choice is recorded as a release decision or DEV-024 blocker.

The runbook separates backup from restore. Creating a backup is useful only if the
team knows where it is retained, how it is protected, and how to prove it can be
restored into an isolated database. It also distinguishes application rollback from
database rollback: returning to an earlier artifact may be safe, while reversing an
applied migration is a separate reviewed decision.

Suggested commit message:

```text
Commit 5: Document production configuration and operations
```

Implement:

- Add a tracked, secret-free production environment example documenting every
  required variable, whether it is secret, its source, and safe formatting rules.
- Use the approved same-origin `https://stopimpulsebuying.us` topology: the reverse
  proxy serves frontend assets and proxies `/api` over loopback to the backend.
- Provide reviewed example configuration for trusted proxy/host handling, request
  size, timeouts, security headers, request-ID forwarding, health checks, metrics
  access, and static SPA fallback.
- Document a non-root `systemd` or equivalent supervisor service with explicit working
  directory, environment delivery, restart policy, startup command, graceful stop,
  log destination, and hardening expectations.
- Document TLS issuance/renewal ownership and verification while keeping certificate
  provisioning and DNS changes outside this task.
- Require PostgreSQL to listen only on loopback or a private local network and explain
  least-privilege application and backup roles.
- Write executable backup and isolated restore-verification procedures covering
  format, consistency, encryption/access, retention, disk space, checksums, exit-code
  checks, and evidence recording.
- Document log access, metric access, disk/log growth checks, readiness diagnosis,
  database-outage response, certificate renewal checks, rollback boundaries, and
  escalation/incident-contact placeholders.
- Mark every unresolved infrastructure choice as an explicit decision or release
  blocker rather than silently choosing a production value.
- Validate configuration syntax where local tooling safely permits and add tests or
  lint checks that prevent real-looking secrets from entering examples.

Commit gate:

```bash
make check
make security-check
git diff --check
```

## Commit 6 — Verify the Complete Operational Boundary

**Status:** Not started.

### In Plain English

Commit 6 proves that the earlier pieces agree. It starts the application with a safe
production-like configuration, sends successful and failing requests, simulates a
database outage, and checks the resulting responses, logs, metrics, and health state.

This is where the team demonstrates the important operator journey: take a request
ID from a safe client error, find the matching structured log, confirm that no secret
was recorded, and use readiness and metrics to understand the broader condition.
Warnings and failed checks are fixed or recorded as explicit release blockers; they
are not hidden to make the tracker look complete.

No command in this commit touches the real Oracle VPS or production database. The
evidence comes from isolated local or CI services using placeholder secrets.

Suggested commit message:

```text
Commit 6: Verify production observability and operations
```

Implement:

- Run assembled-application tests for correlated success, safe client error,
  unexpected exception, middleware rejection, unmatched route, and authenticated
  request behavior.
- Prove a client-visible request ID finds the corresponding request and exception log
  events without exposing traceback details in the response.
- Assert representative logs and metrics contain no seeded password, cookie, token,
  authorization value, database URL, email, client IP, user-controlled path segment,
  body value, or sensitive derivative.
- Verify bounded metric labels and exact-once request accounting under concurrency and
  error handling.
- Start with PostgreSQL available, simulate loss and recovery, and verify readiness
  changes between success and `503` while liveness continues to succeed.
- Exercise clean startup, graceful termination, shutdown ordering, resource disposal,
  and the documented supervisor timeout in an isolated environment.
- Validate the production configuration example and any proxy/supervisor examples
  with the available syntax or static checks.
- Rehearse backup creation and restore into a new isolated database, verify migration
  revision and representative row counts/integrity, and destroy only the explicitly
  named disposable test target afterward.
- Run the full quality, build, migration, and security gates.
- Update this tracker and implementation record with hashes, commands, versions,
  test counts, observed evidence, limitations, and unresolved release blockers.
- Update the master development tracker only after the DEV-022 pull request is merged
  and accepted on the default branch.

Commit gate:

```bash
make clean
make install
make db-up
make db-upgrade
make check
make security-check
cd backend
../.venv/bin/python -m alembic check
cd ..
git diff --check
git status --short
```

## Out of Scope

- Provisioning or changing the Oracle VPS, firewall, DNS, reverse proxy, system
  service, TLS certificates, PostgreSQL instance, monitoring provider, dashboards,
  alert routes, or secrets is not authorized by this task.
- A `make deploy` target, automated production deployment, production migration, and
  real rollback remain outside DEV-022.
- The final release decision and execution checklist belong to DEV-024.
- Live browser journey coverage belongs to DEV-023; DEV-022 tests the backend and
  operational surfaces needed to support that suite.
- Centralized log vendors, distributed tracing vendors, on-call paging products,
  uptime providers, and incident-management tooling require separate infrastructure
  decisions.
- Logs and metrics are not analytics. Do not add behavioral tracking, user profiling,
  or user/entry-level metric dimensions.
- This task does not log request or response bodies and does not weaken DEV-021's
  redaction, trusted-proxy, origin, host, cookie, header, or request-size protections.
- Automatic database failover, replication, point-in-time recovery infrastructure,
  and automatic restore into production are outside the single-VPS V1 scope.
- Email delivery monitoring remains out of scope until an email-dependent feature is
  approved and implemented.

## Implementation Record

Complete this section as each commit lands. Record concrete files, configuration
names, commit hashes, test counts, tool versions, production-example validation,
backup/restore rehearsal evidence, limitations, and blockers.

### Commit Evidence

| Commit | Hash | Result      | Verification |
| ------ | ---- | ----------- | ------------ |
| 1      | `03dc757` | Complete | Ruff format/lint and 549 backend tests passed |
| 2      | `900cba4` | Complete | Ruff format/lint, 555 backend tests, and security scans passed |
| 3      | `5e7428f` | Complete | Ruff format/lint, 560 backend tests, and security scans passed |
| 4      | `1d5bda5` | Complete | Ruff format/lint, backend construction, and 565 backend tests passed |
| 5      | —    | Implemented; awaiting commit | Full `make check` (429 frontend and 567 backend tests), operations validation, builds, and security scans passed |
| 6      | —    | Not started | —            |

### Operational Verification Checklist

| Check                                                                    | Result  | Evidence |
| ------------------------------------------------------------------------ | ------- | -------- |
| Safe client errors carry a request ID that matches server logs           | Pending | —        |
| Unexpected exception details remain server-side                          | Pending | —        |
| Request logs use route templates and the documented stable schema        | Pending | —        |
| Logs preserve DEV-021 redaction under representative failures            | Pending | —        |
| Metrics use bounded labels and contain no user or resource identifiers   | Pending | —        |
| Liveness remains independent of PostgreSQL                                | Pending | —        |
| Readiness returns `503` during database loss and recovers afterward       | Pending | —        |
| Startup validation and graceful shutdown follow the documented lifecycle | Pending | —        |
| Production examples contain no real secrets and pass available checks    | Pass    | Typed settings test and `make operations-check` |
| Backup and isolated restore procedures have been successfully rehearsed  | Pending | —        |
| Unresolved infrastructure choices are explicit DEV-024 blockers          | Pass    | Runbook required-decisions section and table below |
| Full repository quality, migration, build, and security gates pass       | Pending | —        |

### Infrastructure Decisions and Release Blockers

Record the owner, decision deadline, chosen value, and verification evidence for each
item. A blank value is not an implicit approval.

| Decision                         | Owner | Decision / blocker | Required evidence | Status  |
| -------------------------------- | ----- | ------------------ | ----------------- | ------- |
| Oracle VPS operating system      | DEV-024 release owner | Choose supported image and patch policy | Supported version | Blocker |
| Reverse proxy and version        | DEV-024 release owner | Nginx candidate; installed version undecided | `nginx -t` | Blocker |
| Process supervisor and service user | DEV-024 release owner | systemd and `penny-saved` candidate; host paths unverified | Startup/stop test | Blocker |
| TLS client and renewal owner     | DEV-024 release owner | ACME client and named renewal owner undecided | Renewal dry run | Blocker |
| Secret-delivery mechanism        | DEV-024 release owner | `/etc` example exists; delivery and readers undecided | Permission review | Blocker |
| PostgreSQL version and ownership | DEV-024 release owner | V1 targets PostgreSQL 16; host roles unverified | Backup/restore test | Blocker |
| Backup location and retention    | DEV-024 release owner | Destination, encryption, off-host copy, and retention undecided | Isolated restore | Blocker |
| Log retention and access         | DEV-024 release owner | systemd journal candidate; limits and readers undecided | Rotation/access test | Blocker |
| Metrics collection and access    | DEV-024 release owner | Loopback endpoint defined; collector undecided | Private scrape test | Blocker |
| Incident contact and escalation  | Product owner | Contact and response threshold undecided | Contact validation | Blocker |

DEV-022 remains incomplete until every commit gate passes and each unresolved item
needed for release is either decided or carried into DEV-024 as an explicit blocker.
