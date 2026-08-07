# DEV-021 — Security and Abuse Protection

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [Security Rules](#security-rules)
- [Commit 1 — Establish the Security Baseline](#commit-1--establish-the-security-baseline)
- [Commit 2 — Add the Shared Rate-Limit Store](#commit-2--add-the-shared-rate-limit-store)
- [Commit 3 — Throttle Authentication Attempts](#commit-3--throttle-authentication-attempts)
- [Commit 4 — Harden HTTP and Production Boundaries](#commit-4--harden-http-and-production-boundaries)
- [Commit 5 — Complete Redaction and Security Scanning](#commit-5--complete-redaction-and-security-scanning)
- [Commit 6 — Verify the Complete Security Boundary](#commit-6--verify-the-complete-security-boundary)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|                  | Commit                                                   | Short title                      | Depends on                |
| ---------------- | -------------------------------------------------------- | -------------------------------- | ------------------------- |
| &#91;x&#93;      | [1](#commit-1--establish-the-security-baseline)          | Establish security rules         | DEV-008, DEV-010, DEV-017 |
| &#91;&#160;&#93; | [2](#commit-2--add-the-shared-rate-limit-store)          | Add shared rate-limit storage    | Commit 1                  |
| &#91;&#160;&#93; | [3](#commit-3--throttle-authentication-attempts)         | Throttle signup and login        | Commit 2                  |
| &#91;&#160;&#93; | [4](#commit-4--harden-http-and-production-boundaries)    | Harden public request boundaries | Commit 1                  |
| &#91;&#160;&#93; | [5](#commit-5--complete-redaction-and-security-scanning) | Redact secrets and scan packages | Commits 3–4               |
| &#91;&#160;&#93; | [6](#commit-6--verify-the-complete-security-boundary)    | Complete security verification   | Commits 1–5               |

## Objective

DEV-021 protects the finished V1 application from common public-internet mistakes
and straightforward abuse. It does not add a user-facing feature. It makes the
existing authentication and API behavior safer when the application is deployed.

In plain English, this work answers questions such as:

- Can one person repeatedly guess passwords or create accounts without slowing down?
- Can an attacker bypass a limit by changing only the capitalization of an email?
- Does the application trust a forged forwarded IP address?
- Will it accept a request sent to an unexpected hostname or from an unapproved
  website?
- Can an oversized body consume unnecessary server resources?
- Could a password, cookie, token, or database credential appear in a log?
- Will CI warn the team when a locked dependency has a serious known vulnerability?

The goal is layered protection. No single middleware, header, scanner, or rate limit
is treated as complete security by itself.

## Security Rules

These rules apply throughout the implementation:

- Preserve the approved authentication response contract. Throttling must not reveal
  whether an account exists.
- Derive account limits from the same normalized email representation used by the
  authentication service; never store plaintext passwords or session tokens.
- Use a shared, deployment-compatible rate-limit store. A process-local dictionary is
  not sufficient because separate workers would enforce separate limits.
- Trust forwarded client information only from explicitly configured proxy addresses.
  Untrusted `Forwarded` or `X-Forwarded-*` values are attacker-controlled input.
- Fail application startup when production security settings are missing, ambiguous,
  or unsafe.
- Keep error responses small and non-sensitive. Do not echo rejected origins, secrets,
  raw request bodies, or internal configuration.
- Apply controls narrowly enough that health checks and normal authenticated product
  use continue to work.
- Pin security tooling and dependencies so local and CI results are repeatable.
- A scanner finding is evidence to triage, not permission to apply an unreviewed
  upgrade or suppress a vulnerability silently.

## Commit 1 — Establish the Security Baseline

**Status:** Complete — `199f400`.

### In Plain English

Commit 1 writes down the rules before enforcing them. It defines which hosts,
origins, proxies, body sizes, headers, secrets, and authentication actions need
protection. It also adds typed settings and representative tests for safe and unsafe
production configurations.

This is the safety checklist for the hardening work. Later commits can change
request behavior confidently because the intended boundaries and failure behavior
are already testable. This commit does not start rejecting ordinary requests or
claim the application is hardened yet.

Concretely, Commit 1 decides which website origins and hostnames are allowed, which
reverse proxies may report the real client IP, how large a request may be, and the
thresholds and time windows for login and signup limits. It specifies which values
are safe in development, test, and production. For example, production must refuse
to start with wildcard trusted hosts, an insecure HTTP frontend origin, insecure
session cookies, invalid or trust-everywhere proxy networks, or missing and
unreasonable request-size and rate-limit values.

The important distinction is that this commit establishes and tests those rules. It
does not yet throttle a user, interpret forwarded headers, or reject an oversized
request; those enforcement mechanisms arrive in later commits.

### Threat and Trust-Boundary Matrix

| Boundary                         | Trusted input                                     | Untrusted input or risk                                     | Rule established here                                       |
| -------------------------------- | ------------------------------------------------- | ----------------------------------------------------------- | ----------------------------------------------------------- |
| Browser → reverse proxy          | Configured HTTPS origin and expected host         | Cross-site origins, forged host, oversized request          | Exact origin/host and body-size settings                    |
| Reverse proxy → application      | Direct peers in configured proxy networks         | Forwarded headers from any other peer                       | Empty-by-default explicit proxy trust                       |
| Application worker → PostgreSQL  | Parameterized application operations              | Raw secret-bearing keys and inconsistent local counters     | Shared-store contract will use digested keys                |
| Application → logs               | Safe request metadata and correlation identifiers | Cookies, passwords, tokens, bodies, URLs containing secrets | Sensitive-value inventory for Commit 5                      |
| Lock files → CI advisory service | Committed, pinned dependency graphs               | Unreviewed findings or silent suppressions                  | High-severity triage policy and repeatable scan requirement |

Suggested commit message:

```text
Commit 1: Establish the security hardening baseline
```

Implement:

- Add a concise threat and trust-boundary matrix covering browser, reverse proxy,
  application workers, PostgreSQL, logs, and CI.
- Define typed settings for trusted hosts, trusted proxy networks, maximum request
  body size, and authentication rate-limit windows and thresholds.
- Decide and document whether each setting is required, forbidden, or safely
  defaulted in development, test, and production.
- Reject wildcard or malformed production hosts, origins, and proxy networks.
- Preserve the existing requirements that production uses HTTPS for the frontend
  origin and secure session cookies.
- Require positive bounded values for body-size and rate-limit settings.
- Ensure Pydantic configuration errors hide input values so secrets cannot be copied
  into startup errors.
- Add configuration tests for safe defaults, production success, and every unsafe
  boundary.
- Add a security verification checklist that later commits fill with concrete test
  and scan evidence.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
git diff --check
```

## Commit 2 — Add the Shared Rate-Limit Store

**Status:** Implemented and verified; awaiting commit.

### In Plain English

Commit 2 creates the counter that all application workers share. When several server
processes handle requests, they must agree about how many attempts have occurred.
Keeping counts only in one process would let traffic avoid a limit simply by reaching
a different worker or restarting the application.

The store records an irreversible digest of the limit key, a time window, and a
count. It does not store submitted passwords or a readable list of attempted email
addresses. This commit builds and tests the mechanism but does not yet attach it to
signup or login.

For example, without shared storage, worker A could count eight attempts while
worker B counts seven. Each worker would think a ten-attempt limit had not been
reached even though the application received fifteen attempts. Restarting either
worker could also erase its local count. With PostgreSQL-backed storage, every worker
atomically reads and updates the same total, so all fifteen attempts are recognized.

In practical terms, a rate limit means allowing only a configured number of actions
within a period, such as ten login attempts for one account in fifteen minutes.
Commit 2 creates the trustworthy counting mechanism. Commit 3 will decide which
signup and login requests consume those counters and will return `429 Too Many
Requests` when a limit is exceeded.

Suggested commit message:

```text
Commit 2: Add shared authentication rate-limit storage
```

Implement:

- Define a small rate-limit store interface that accepts a bucket, digested key,
  limit, window, and injected clock.
- Add a PostgreSQL-backed implementation that works consistently across application
  workers and uses an atomic operation under concurrent requests.
- Add the minimum model and Alembic migration required for active counters.
- Store only keyed digests for sensitive account identifiers and client keys.
- Return a decision containing allowed/blocked state and the retry time needed by the
  HTTP layer; do not expose internal counter rows.
- Define deterministic behavior at the first request, final allowed request, first
  blocked request, exact window boundary, and after window expiry.
- Bound stale-record growth with a documented cleanup strategy that does not add a
  scheduler to this task.
- Provide a lightweight isolated test store for route/service tests without weakening
  production construction.
- Test atomic concurrency, independent buckets and keys, expiry, rollback behavior,
  digest safety, migration upgrade/downgrade, and model/migration agreement.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
cd backend
../.venv/bin/python -m alembic check
cd ..
git diff --check
```

## Commit 3 — Throttle Authentication Attempts

**Status:** Not started.

### In Plain English

Commit 3 connects the shared limiter to signup and login. Each attempt is considered
by both its trustworthy client IP and its normalized account key. This slows broad
traffic from one source and repeated targeting of one account, even when the attacker
changes capitalization or spacing.

A blocked request returns `429 Too Many Requests` with a useful retry delay. Login
still gives the same safe public behavior whether an email is missing or a password
is wrong. Rate limiting must not become a new account-discovery tool.

Suggested commit message:

```text
Commit 3: Throttle signup and login attempts
```

Implement:

- Apply separate, configurable policies to `POST /api/auth/signup` and
  `POST /api/auth/login`.
- Evaluate both a trusted client-IP key and the normalized account key; block when
  either applicable limit is exhausted.
- Normalize the account key through the same canonical rule used by authentication.
- Hash account and client identifiers before persistence with domain-separated keys.
- Count attempts according to one documented policy that cannot be bypassed by
  alternating valid, invalid, and malformed credentials.
- Return the standard safe error envelope with status `429` and a valid `Retry-After`
  header without revealing which bucket triggered.
- Avoid setting or clearing an authentication cookie on a throttled response.
- Keep signup conflict and login invalid-credential responses consistent with their
  existing approved contracts when the request is not throttled.
- Add tests for threshold boundaries, both dimensions, normalization, independent
  routes, window reset, malformed input, successful attempts, response uniformity,
  cookies, and concurrent requests.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
git diff --check
```

## Commit 4 — Harden HTTP and Production Boundaries

**Status:** Not started.

### In Plain English

Commit 4 makes the server strict about how public requests arrive. It accepts only
approved hostnames and browser origins, limits body size before parsing expensive
content, and trusts proxy-supplied client details only when the immediate connection
comes from a configured proxy.

It also adds conservative browser security headers. These headers reduce common
browser risks, but they do not replace correct authentication, authorization, input
validation, or TLS. Local development remains convenient through explicit
development settings; production refuses to start with unsafe ambiguity.

Suggested commit message:

```text
Commit 4: Harden public HTTP request boundaries
```

Implement:

- Enforce an explicit trusted-host allowlist without trusting the request's host for
  redirects, cookies, or security decisions.
- Resolve the client IP from the socket peer by default; honor forwarded information
  only when the direct peer belongs to an explicitly trusted proxy network.
- Define handling for malformed, conflicting, or multi-hop forwarded values and test
  it independently from rate limiting.
- Reject disallowed browser origins on state-changing cookie-authenticated requests,
  including requests that omit required origin evidence under the documented policy.
- Keep CORS credential settings restricted to the one configured frontend origin.
- Reject oversized fixed-length and streamed request bodies with a safe `413` before
  route parsing; do not rely only on `Content-Length`.
- Add conservative headers such as `X-Content-Type-Options`, `Referrer-Policy`, a
  reviewed `Content-Security-Policy`, and appropriate framing protection.
- Add HSTS only for production HTTPS responses under the documented proxy scheme
  policy; never teach a development HTTP origin to use HSTS.
- Ensure security headers are also present on validation errors, `404`, `413`, `429`,
  and unexpected-error responses where applicable.
- Test trusted and untrusted hosts/proxies, spoofed forwarded values, valid and invalid
  origins, exact body boundaries, streamed overflow, headers, preflight behavior,
  production startup rejection, health routes, and normal authenticated API requests.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
make backend-build
git diff --check
```

## Commit 5 — Complete Redaction and Security Scanning

**Status:** Not started.

### In Plain English

Commit 5 makes two safety nets repeatable. First, it prevents known categories of
secret from reaching application logs even when they appear in structured fields,
exceptions, URLs, or unusually formatted text. Second, CI scans the exact locked
Python and JavaScript dependency trees for known vulnerabilities.

The scanner does not prove that the application is secure. It identifies published
dependency risks so the team can upgrade, mitigate, or document them deliberately.
The merge policy blocks untriaged high-severity findings without silently ignoring
lower-severity work.

Suggested commit message:

```text
Commit 5: Complete secret redaction and dependency scanning
```

Implement:

- Centralize recursive redaction for log messages and structured values before JSON
  serialization.
- Redact cookies, `Set-Cookie`, authorization values, passwords, raw session tokens,
  token digests, database URLs, rate-limit key material, and common API-secret forms.
- Preserve useful non-sensitive context such as request ID, route template, status,
  duration, and safe exception type.
- Prevent query strings, request bodies, and raw headers from being logged by the
  request middleware.
- Test case, separators, embedded URLs, mappings, sequences, exceptions, multiline
  values, and misleading near-matches so redaction is broad without destroying all
  diagnostics.
- Add pinned Python and npm audit commands that inspect the committed lock files.
- Add a dedicated CI security job with read-only permissions, bounded runtime, and no
  application secrets.
- Document the severity policy: every high or critical finding must be fixed,
  mitigated, or linked to an approved triage record before merge.
- Require every suppression to identify the advisory, affected package/path, impact,
  rationale, owner, expiry/review date, and follow-up issue.
- Test the CI workflow and local security command contract without depending on live
  vulnerability-service responses in the ordinary unit suite.

Commit gate:

```bash
make backend-format-check
make backend-lint
make backend-test
make frontend-test
make security-check
git diff --check
```

## Commit 6 — Verify the Complete Security Boundary

**Status:** Not started.

### In Plain English

Commit 6 proves that all earlier protections work together. It runs the full quality
and security gates, exercises boundary cases through the assembled application, and
records actual results. It checks that hardening did not break signup, login, logout,
session restoration, health checks, or normal authenticated product requests.

This commit is evidence, not a place to wave through warnings. A failing security
test or untriaged high-severity dependency finding is resolved before DEV-021 is
marked complete.

Suggested commit message:

```text
Commit 6: Verify security and abuse protections
```

Implement:

- Run combined integration tests through the assembled middleware stack for safe and
  hostile hosts, origins, forwarded headers, request sizes, and auth rates.
- Verify rate-limit decisions remain consistent across concurrent database sessions
  and independent application instances.
- Verify every rejected request uses a safe response, request correlation, expected
  security headers, and no session cookie mutation.
- Capture logs from representative success and failure requests and assert that no
  seeded secret or sensitive derivative appears.
- Run migration upgrade, downgrade, re-upgrade, and drift checks for the rate-limit
  schema.
- Run locked frontend and backend dependency scans and record advisory triage.
- Verify production application construction accepts a complete safe configuration
  and rejects each unsafe configuration independently.
- Update the DEV-021 tracker and implementation record with commit hashes, test
  counts, scanner versions, findings, triage links, and approved deferrals.
- Update the master development tracker only after the DEV-021 PR is merged and its
  acceptance checks pass on the default branch.

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

- Reverse-proxy installation, TLS certificate provisioning, process supervision,
  production deployment, backups, restores, metrics, alerts, and operational
  dashboards belong to DEV-022.
- A live end-to-end browser smoke suite belongs to DEV-023.
- Final release validation belongs to DEV-024.
- Password reset, email verification, multi-factor authentication, passkeys, social
  login, account deletion, and a user-visible session-management screen are not part
  of V1 hardening.
- CAPTCHA, third-party bot scoring, a web application firewall, and external denial-
  of-service mitigation are infrastructure/product decisions beyond this task.
- CSRF tokens for a cross-site frontend/backend deployment are out of scope. DEV-021
  preserves the approved same-origin deployment and `SameSite=Lax` cookie model and
  refuses unsafe cross-site production configuration.
- Scheduled stale-counter cleanup infrastructure is not introduced here; the data
  lifecycle must still be bounded and documented.
- Automatically upgrading dependencies or suppressing advisories merely to make CI
  green is not allowed.

## Implementation Record

Complete this section as each commit lands. Record concrete files, migration IDs,
configuration names, commit hashes, test counts, scan tools and versions, findings,
triage links, and limitations.

### Commit Evidence

| Commit | Hash      | Result                       | Verification                                                                     |
| ------ | --------- | ---------------------------- | -------------------------------------------------------------------------------- |
| 1      | `199f400` | Complete                     | Ruff format/lint, 505 backend tests, backend construction, and diff check passed |
| 2      | —         | Implemented; awaiting commit | Ruff format/lint, 522 backend tests, migration drift, and diff check passed      |
| 3      | —         | Not implemented              | —                                                                                |
| 4      | —         | Not implemented              | —                                                                                |
| 5      | —         | Not implemented              | —                                                                                |
| 6      | —         | Not implemented              | —                                                                                |

### Security Verification Checklist

| Check                                                                    | Result  | Evidence                                                                     |
| ------------------------------------------------------------------------ | ------- | ---------------------------------------------------------------------------- |
| Login and signup enforce IP and normalized-account limits                | Pending | —                                                                            |
| Limit state is shared across workers and safe under concurrency          | Pass    | Atomic PostgreSQL upsert passed across two stores and 12 concurrent attempts |
| Throttling does not reveal whether an account exists                     | Pending | —                                                                            |
| Untrusted forwarded values cannot change the resolved client identity    | Pending | —                                                                            |
| Unsafe host, origin, cookie, proxy, and production settings are rejected | Pending | —                                                                            |
| Fixed-length and streamed oversized bodies receive safe `413` responses  | Pending | —                                                                            |
| Security headers cover success and applicable error responses            | Pending | —                                                                            |
| Representative logs contain no seeded secret or sensitive derivative     | Pending | —                                                                            |
| Locked dependency scans have no untriaged high-severity finding          | Pending | —                                                                            |
| Full repository quality, build, migration, and security gates pass       | Pending | —                                                                            |

### Advisory Triage

| Advisory | Package/path | Severity | Decision | Owner/follow-up | Review date |
| -------- | ------------ | -------- | -------- | --------------- | ----------- |
| —        | —            | —        | None yet | —               | —           |

### Final Verification

Record the final `make check`, `make security-check`, Alembic drift result,
production-construction result, test counts, scanner versions, unresolved findings,
and confirmation that no high-severity dependency finding remains untriaged.
