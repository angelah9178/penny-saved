# DEV-023 — Browser Smoke Tests

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [What Smoke Coverage Means](#what-smoke-coverage-means)
- [Smoke-Test Rules](#smoke-test-rules)
- [Critical Journey](#critical-journey)
- [Commit 1 — Define the Browser Smoke Contract](#commit-1--define-the-browser-smoke-contract)
- [Commit 2 — Add Isolated End-to-End Test Data](#commit-2--add-isolated-end-to-end-test-data)
- [Commit 3 — Start and Stop the Complete Test Stack](#commit-3--start-and-stop-the-complete-test-stack)
- [Commit 4 — Cover Authentication and Entry Creation](#commit-4--cover-authentication-and-entry-creation)
- [Commit 5 — Cover Check-In, Statistics, and Logout](#commit-5--cover-check-in-statistics-and-logout)
- [Commit 6 — Add CI and Verify Reliable Smoke Coverage](#commit-6--add-ci-and-verify-reliable-smoke-coverage)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|                  | Commit                                                    | Short title                   | Depends on              |
| ---------------- | --------------------------------------------------------- | ----------------------------- | ----------------------- |
| &#91;x&#93;      | [1](#commit-1--define-the-browser-smoke-contract)         | Define smoke-test rules       | DEV-020 and DEV-021     |
| &#91;x&#93;      | [2](#commit-2--add-isolated-end-to-end-test-data)         | Add isolated browser data     | Commit 1 and DEV-007    |
| &#91;x&#93;      | [3](#commit-3--start-and-stop-the-complete-test-stack)    | Orchestrate the live stack    | Commits 1–2 and DEV-022 |
| &#91;x&#93;      | [4](#commit-4--cover-authentication-and-entry-creation)   | Test auth and entry creation  | Commit 3                |
| &#91;x&#93;      | [5](#commit-5--cover-check-in-statistics-and-logout)      | Test the completed journey    | Commit 4                |
| &#91;&#160;&#93; | [6](#commit-6--add-ci-and-verify-reliable-smoke-coverage) | Add CI and verify reliability | Commits 1–5             |

## Objective

DEV-023 proves that the application's most important V1 journey works in a real
browser connected to the real React frontend, FastAPI backend, and PostgreSQL
database.

In plain English, earlier tests prove individual parts in detail. DEV-023 checks that
the assembled product works from the user's point of view:

- Can someone create an account and remain signed in after a browser reload?
- Can an existing account log in through the real form and session cookie?
- Can the person create an impulse-purchase entry and see it on the dashboard?
- Can a deterministically eligible entry be checked in without waiting 48 real hours?
- Do saved totals and opportunity-cost equivalents appear after that check-in?
- Does logout remove access to protected pages?
- Can the same journey run repeatedly without inheriting data from an earlier run?
- When the journey fails in CI, is there enough safe evidence to understand why?

This is deliberately a small smoke suite, not a second copy of every backend,
component, accessibility, security, and concurrency test. Its value is proving that
the boundaries connect correctly: browser navigation, built frontend assets, HTTP,
cookies, backend rules, migrations, and PostgreSQL persistence.

## What Smoke Coverage Means

Smoke coverage is a small set of tests that checks whether an application's most
important features work together. The term comes from an old hardware check: turn a
device on and see whether it immediately produces smoke. It is a fast signal that the
assembled product is fundamentally working, not an exhaustive inspection of every
possible behavior.

For Penny Saved, smoke coverage answers one practical question:

> Can a person complete the essential V1 journey in the assembled application?

The smoke suite therefore uses a real Chromium browser to exercise the built React
frontend, running FastAPI backend, real HTTP requests and cookies, applied database
migrations, and PostgreSQL persistence together. Its critical path is:

```text
open the real frontend
  → sign up or log in
  → create an entry
  → check in an eligible entry
  → view updated statistics and opportunity-cost equivalents
  → log out
```

This catches integration failures that isolated tests can miss, such as the frontend
using the wrong API address, cookies failing in a real browser, built routes not
loading, frontend forms disagreeing with backend contracts, a missing migration,
successful mutations not updating the visible page, or logout failing to remove
protected access.

Smoke coverage does not mean testing every field value, authorization edge case,
concurrency race, viewport, browser engine, accessibility requirement, security
boundary, or exact calculation. Those detailed responsibilities remain with the
existing backend, component, integration, security, and manual accessibility suites.
The browser smoke tests provide a small release-level confidence signal that those
parts connect correctly.

## Smoke-Test Rules

These rules apply throughout the implementation:

- Use a real browser automation tool, initially Playwright with its pinned Chromium
  runtime. Browser-like jsdom tests do not satisfy DEV-023.
- Run the actual frontend and backend processes against PostgreSQL. Do not replace the
  API with MSW, stub repositories, or use SQLite.
- Use an explicit `E2E_DATABASE_URL` that is separate from development, ordinary test,
  staging, and production databases.
- Refuse unsafe databases before any setup or cleanup. Local runs require a loopback
  host and a database name ending in `_e2e_test`; CI must use its explicitly created
  ephemeral service database.
- Give each run a unique identifier and create only records owned by that run. Cleanup
  may delete only those identified records or remove an explicitly named disposable
  database.
- Never expose a test-only setup, clock, reset, or data-mutation route through the HTTP
  application. Seed through a guarded command using the same models and database
  constraints as the application.
- Do not wait 48 hours and do not use a browser timing sleep to make an entry eligible.
  Seed its server-owned `created_at` relative to one injected UTC setup clock.
- Wait for observable conditions: process readiness, visible page state, URL changes,
  and completed network/UI behavior. Fixed `sleep`, `waitForTimeout`, and arbitrary
  retry loops are forbidden.
- Prefer accessible selectors such as role, label, and visible name. Test IDs are a
  last resort when the user has no meaningful way to identify an element.
- Assert user-visible outcomes and a small amount of durable persisted state. Do not
  duplicate every validation, authorization, date-boundary, or rounding test already
  owned by lower-level suites.
- Run with one browser worker until isolation is proven. Parallel execution may be
  enabled only after records, ports, cookies, and artifacts are independent.
- Use an ephemeral, run-specific email and password. Never use local demo, developer,
  staging, or production credentials. Destroy the account/session before retaining
  failure artifacts so captured test credentials are no longer usable.
- Retain screenshots, a Playwright trace, browser console output, and bounded process
  logs on failure only. Redact cookies, authorization values, database URLs, passwords,
  request bodies, and session material before artifact upload.
- Start processes only for this suite, record their process IDs, and stop them on
  success, failure, cancellation, and signals. Never kill a process merely because it
  uses a common name or port.
- The suite must not connect to the public internet or production origin. It must use
  explicit loopback URLs locally and isolated CI services in automation.

## Critical Journey

The completed suite must cover this minimum path:

```text
prepare isolated run data and migrate database
  → start FastAPI and built frontend
  → wait for backend readiness and frontend HTTP readiness
  → sign up a new account
  → reload and prove the HttpOnly-cookie session restores
  → create a waiting entry and see it on the dashboard
  → log out and prove the protected route redirects
  → log in as the seeded journey account
  → open its deterministically eligible entry
  → check it in as saved
  → verify saved statistics and opportunity-cost equivalents
  → log out and prove the session is gone
  → stop processes and remove only run-owned data
```

Signup and login are both required because they exercise different backend services
and browser screens. The seeded journey account is separate from the signup account
so the setup command can attach an already eligible entry, existing statistics rows,
and opportunity-cost examples without adding a test-only API.

## Commit 1 — Define the Browser Smoke Contract

**Status:** Complete in `d9834be`.

### In Plain English

Commit 1 chooses how the browser suite will work before it automates a product
journey. It installs and configures the browser test runner, defines which browsers
and URLs are supported, and writes down the rules for waits, selectors, retries,
timeouts, credentials, and failure evidence.

Think of this commit as building an empty but safe test track. It proves that a pinned
browser can open a controlled local page and that the configuration will not silently
point at production. It does not sign up, create an entry, or change application data
yet.

In practical terms, this commit proves only the browser-testing foundation: Chromium
starts, Playwright can make a user-visible assertion, unsafe URLs and unreliable wait
patterns are rejected, and useful evidence is retained when a test fails. It does not
start FastAPI or PostgreSQL, create test users, seed entries, or exercise any Penny
Saved screen. Those product-facing pieces begin in later commits.

The initial target is Chromium in CI because this is release smoke coverage, not a
cross-browser compatibility matrix. Firefox and WebKit can be added later if a real
compatibility risk justifies their installation and runtime cost.

Suggested commit message:

```text
Commit 1: Define the browser smoke test contract
```

Implement:

- Add the pinned Playwright test dependency and lockfile changes through the supported
  frontend package workflow.
- Add a browser-test directory separate from Vitest component tests.
- Configure one Chromium project, one worker by default, bounded per-test/global
  timeouts, no implicit production URL, and retries only in CI.
- Define explicit environment names for frontend base URL, backend URL,
  `E2E_DATABASE_URL`, run ID, test email domain, and ephemeral credential input.
- Refuse public/non-loopback base URLs locally and refuse
  `https://stopimpulsebuying.us` in every test mode.
- Configure screenshots, trace, console capture, and bounded process logs for failure
  diagnosis; do not record artifacts for successful runs by default.
- Add helpers for role/label-based interactions and observable waits without wrapping
  Playwright's built-in retry behavior in arbitrary loops.
- Add lint/static tests that reject `waitForTimeout`, fixed sleeps, focused tests,
  committed browser artifacts, and production hostnames in executable smoke code.
- Add an empty-run or local fixture smoke proving the runner and pinned Chromium can
  start without contacting the product stack.
- Document the difference between Vitest/MSW tests and live Playwright smoke tests.

Commit gate:

```bash
npm --prefix frontend run format:check
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run e2e:list
make frontend-security-check
git diff --check
```

## Commit 2 — Add Isolated End-to-End Test Data

**Status:** Complete in `b029216`.

### In Plain English

Commit 2 creates the controlled database starting point for each browser run. The
suite needs an existing account with an entry that is already more than 48 hours old,
some saved history, and opportunity-cost examples. Creating those rows through the
ordinary UI would either require a two-day wait or reproduce server-owned rules in
the browser test.

The setup command creates that data directly in the dedicated end-to-end database
using one injected UTC time. It also returns a small manifest describing what the
browser should expect, such as the unique email, eligible item name, saved total, and
equivalent labels. The password comes from an ephemeral environment variable and is
never printed.

Every row is tied to one unique run. Cleanup deletes only the run-owned user records,
which cascade to their sessions, entries, and opportunity-cost examples. A setup or
cleanup command refuses to run if the database guard, migration revision, or run ID
is unsafe.

In practical terms, Commit 2 gives every browser run its own predictable starting
point:

- It reserves a unique signup email that does not exist yet, so the browser can test
  real account creation.
- It creates a separate journey account that can test the existing-user login form.
- That journey account owns an entry created 49 hours earlier, so it is immediately
  eligible for check-in without changing the real 48-hour rule.
- It includes saved history and two opportunity-cost examples so later tests can
  verify both whole and fractional statistics results.
- A secret-free manifest tells the browser exactly which email, item, totals, and
  labels belong to its run.

The run ID is the ownership label. It appears in deterministic IDs, emails, entry
names, and opportunity-cost labels. Cleanup reads the matching manifest and removes
only those exact run-owned users; it never truncates a table or deletes everything in
a shared test email domain. The password is supplied temporarily, stored only as its
normal hash, and never written to the manifest or command output.

Suggested commit message:

```text
Commit 2: Add isolated end-to-end test data
```

Implement:

- Add a typed end-to-end data manifest and guarded setup/cleanup CLI under the backend
  scripts package.
- Require `APP_ENV=test`, an explicit `E2E_DATABASE_URL`, a loopback/approved CI host,
  and an exact database-name suffix such as `_e2e_test` before mutation.
- Reject the ordinary `DATABASE_URL`, `TEST_DATABASE_URL`, demo user, production host,
  missing run ID, malformed run ID, and any pre-existing row owned by another run.
- Require Alembic `head` before setup; do not create or migrate schema implicitly in
  the data command.
- Create separate signup and seeded-login identities using unique run-scoped emails
  and an ephemeral supplied password whose value is never printed or stored outside
  its normal password hash.
- Seed at least one waiting entry older than 48 hours relative to the injected setup
  clock, saved history in a known statistics range, and examples producing one whole
  and one fractional equivalent.
- Ensure item names and labels contain the run ID so the browser can distinguish its
  own data without relying on global row counts.
- Emit a secret-free JSON manifest to a caller-selected temporary path with exact
  expected visible values and stable identifiers needed for cleanup.
- Make setup transactional and idempotent for the same run specification; fail on a
  conflicting specification instead of combining datasets.
- Make cleanup idempotent and limited to the exact manifest/run-owned users. Never
  truncate tables or delete by a broad email domain alone.
- Add PostgreSQL tests for guards, migration checks, determinism, eligibility,
  equivalents, rollback, unrelated-row preservation, repeated cleanup, and absence of
  plaintext passwords/session tokens.

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

## Commit 3 — Start and Stop the Complete Test Stack

**Status:** Complete in `7a7c842`.

### In Plain English

Commit 3 makes one command assemble the real application for browser testing. It
checks the dedicated database, applies migrations through an explicit orchestration
step, prepares run data, starts FastAPI and the built frontend on reserved loopback
ports, and waits until both report that they are ready.

This commit replaces timing guesses with readiness evidence. The browser does not
start merely because five seconds have passed; it starts after the backend readiness
endpoint succeeds and the frontend serves its entry page. If either process exits
early or never becomes ready within the deadline, the command fails with bounded safe
logs.

When testing ends, the orchestrator stops only the process IDs it started, waits for
graceful shutdown, cleans the run's database records, and keeps failure artifacts when
needed. This cleanup runs even when a browser assertion fails or CI cancels the job.

The reusable entry point added by this commit is:

```bash
make e2e
```

This is not a one-time setup command. Every invocation creates a fresh run ID and
ephemeral password, migrates and seeds the explicitly configured `_e2e_test` database,
builds and starts the application, runs Chromium, stops the exact child processes, and
removes that run's data. Developers can run it repeatedly, and Commit 6 will call the
same command in CI.

`make e2e-prepare` is the focused diagnostic command: it validates the environment and
free ports, applies migrations to the dedicated database, builds the frontend, and
lists the browser tests without leaving application servers running. `make
e2e-cleanup-check` runs the supervision, redaction, and cleanup safety contracts. In
contrast, `make seed-demo` only writes persistent sample data for manual development;
it does not manage servers, Chromium, or automatic cleanup.

Suggested commit message:

```text
Commit 3: Orchestrate the live end-to-end stack
```

Implement:

- Add `make e2e` plus focused prepare, run, and cleanup commands with concise
  `make help` descriptions.
- Validate required tools, pinned browser availability, ports, loopback URLs,
  environment, and dedicated database guard before starting a process.
- Build the frontend and serve the production bundle through a supported preview or
  static server configuration that proxies `/api` to the live backend.
- Start FastAPI with `APP_ENV=test`, the dedicated E2E database, exact frontend origin,
  safe test secrets, and loopback-only host/proxy settings.
- Use available-port checks or run-specific reserved ports; fail rather than killing
  an unrelated listener.
- Poll `/api/ready` and the frontend root with bounded HTTP timeouts and an overall
  deadline. Do not use an unconditional sleep.
- Capture bounded stdout/stderr separately for frontend, backend, setup, and browser
  runner, using DEV-021 redaction before artifact retention.
- Track exact child process IDs, forward termination signals, request graceful stop,
  enforce a finite outer deadline, and stop a sibling when one process exits.
- Run guarded data cleanup in a `finally`/trap path after browser completion and
  process shutdown; report cleanup failure separately from the test failure.
- Preserve the original browser-test exit code while still completing cleanup.
- Add tooling tests for readiness timeout, early process exit, occupied ports, signal
  handling, exact-PID cleanup, redacted logs, manifest cleanup, and no orphan process.
- Document the local workflow and troubleshooting without adding a deployment command.

Commit gate:

```bash
make e2e-prepare
make e2e
make e2e-cleanup-check
make check
git diff --check
```

## Commit 4 — Cover Authentication and Entry Creation

**Status:** Complete in `5eace49`.

### In Plain English

Commit 4 automates the first half of the user journey in the real browser. One test
opens the signup page, creates a new account, reaches the protected dashboard, reloads
the page, and proves the server-backed session still works. It then creates a waiting
entry through the same form a person uses and confirms the dashboard displays it.

This is the first half of actual product testing. Commits 1–3 built the safe browser,
data, and live-stack infrastructure; Commit 4 is where Chromium first behaves like a
real Penny Saved user:

```text
sign up → reload the signed-in session → create an entry → see it persist → log out
```

Commit 5 supplies the second half: return through login, check in the seeded eligible
entry, verify statistics and opportunity-cost equivalents, and log out again.

A second path proves that the separately seeded account can log in through the real
login form. This matters because signup and login use different backend operations;
testing only signup would not prove that an existing user can return later.

The browser interacts by visible labels, button names, headings, and links. It does
not call the API directly to skip screens, read the HttpOnly cookie value, or inspect
React internals. Database verification is limited to proving that the visible action
persisted under the correct run-owned account.

Suggested commit message:

```text
Commit 4: Cover authentication and entry creation smoke flows
```

Implement:

- Add a signup smoke flow using the run-specific signup email and ephemeral password.
- Prove successful signup reaches the dashboard and does not expose a password or
  session token in the URL, local storage, session storage, console, or retained logs.
- Reload the browser and prove `/api/auth/me` restores the session without showing the
  login form or losing protected content.
- Create a uniquely named waiting entry through `/entries/new` with known integer-cent
  value and reason text.
- Confirm the success state and dashboard waiting list show the new entry after real
  backend persistence; avoid asserting implementation-only request sequences.
- Log out the signup account so the login flow starts with a clean browser session.
- Log in as the seeded journey account through the real form and prove its unique
  eligible entry appears in the correct dashboard section.
- Verify browser history/reload does not accidentally resubmit signup or entry-create
  mutations.
- Add a small post-run database assertion that both accounts and the created waiting
  entry belong to the current run, without duplicating repository-level field tests.
- Use test steps and assertion messages that make a failed trace understandable.

Commit gate:

```bash
make e2e-auth-entry
make frontend-lint
make frontend-typecheck
make backend-test
git diff --check
```

## Commit 5 — Cover Check-In, Statistics, and Logout

**Status:** Complete in `2b3b672`.

### In Plain English

Commit 5 completes the critical journey. After logging into the seeded account, the
browser opens the entry whose timestamp was prepared as already eligible, checks it
in as “saved,” and sees it move out of the waiting/check-in list.

This is the second half of product testing, and its important distinction is that it
tests account-specific actions available to a particular user after login. Commit 4
proved that someone can enter the application and create an entry. Commit 5 proves
that the authenticated seeded user can act on their own eligible entry, see their own
saved history, statistics, and opportunity-cost equivalents, and then remove their
own access by logging out. The test does not treat those entries or totals as shared
application-wide data; every assertion is tied to that logged-in run-owned account.

The test then opens statistics and checks the values a person cares about: the saved
count and money total include the newly resolved entry, and the seeded
opportunity-cost examples display both a whole and a fractional equivalent. The
expected values come from the setup manifest, not calculations copied into the
browser test.

Finally, the test logs out, tries a protected route, and proves the application returns
to login. This confirms the real browser cookie, backend session revocation, frontend
cache clearing, and route guard work together.

Suggested commit message:

```text
Commit 5: Complete the critical browser journey
```

Implement:

- Navigate to the uniquely seeded eligible entry through the visible dashboard UI.
- Submit a saved check-in with a run-specific comment and wait for confirmed success,
  not an arbitrary delay.
- Prove the entry appears in the saved list and no longer appears in the waiting or
  needs-check-in list.
- Open the relevant statistics range and assert the manifest's saved count and exact
  formatted currency total.
- Assert the manifest's whole and fractional equivalent labels/quantities as returned
  by the real statistics API and formatted by the frontend.
- Reload statistics and prove the server-confirmed result persists.
- Log out through the visible account control, confirm the login page, and navigate
  directly to a protected URL to prove access remains revoked.
- Confirm browser storage contains neither session material nor a cached authenticated
  user record after logout.
- Add post-run database verification for one resolved saved entry, its comment and
  timestamp, unchanged seeded history, and revoked browser session.
- Keep this as one critical journey or a very small number of independent specs; do
  not split every click into a separately expensive browser test.

Commit gate:

```bash
make e2e
make frontend-lint
make frontend-typecheck
make backend-test
git diff --check
```

## Commit 6 — Add CI and Verify Reliable Smoke Coverage

**Status:** Implemented and verified; awaiting commit.

### In Plain English

Commit 6 proves the browser suite is dependable enough to protect a release. It adds
an isolated CI job with PostgreSQL and pinned Chromium, runs the complete journey
more than once, and records whether setup and cleanup leave any state behind.

In plain English, Commits 1–5 built the complete browser test. Commit 6 makes GitHub
run it automatically when relevant code changes. GitHub creates a temporary database,
builds the real application, runs the complete user journey twice with fresh test
users, and confirms each run removes its users, entries, sessions, processes, and
occupied ports. One passing run shows the journey works once; two clean independent
runs also show that it does not depend on leftover data or a random success.

Commit 6 does not add another user-facing part of the journey. It turns the journey
from Commits 1–5 into a repeatable safety check before changes are accepted.

When a test fails, CI keeps a screenshot, trace, console messages, and redacted
process logs. Those files show what the browser saw and which safe request IDs can be
matched to backend logs. Artifacts are uploaded only after the ephemeral accounts and
sessions have been destroyed, and they never contain credentials from another
environment.

This commit treats flaky success as failure. Retries may collect evidence for a
known CI-only transient, but a test that passes only on retry is reported and fixed or
explicitly blocked; it is not silently accepted as reliable coverage.

Suggested commit message:

```text
Commit 6: Verify browser smoke coverage in CI
```

Implement:

- Add a dedicated CI smoke job with PostgreSQL 16, Node/Python versions from the
  repository, locked/pinned dependencies, and Playwright's pinned Chromium install.
- Use an explicit ephemeral database name ending in `_e2e_test`; never reuse the
  ordinary backend test database or accept repository/developer `.env` files.
- Apply migrations, run the production frontend build, start the live stack, and wait
  for readiness through the same commands used locally.
- Run the complete suite at least twice during the final reliability gate with fresh
  run IDs and no fixed sleeps; record duration and prove both runs pass independently.
- Keep CI's default worker count and retries explicit. Report retry-dependent tests as
  reliability failures until triaged.
- Always run process and database cleanup, then assert no run-owned user, session,
  entry, example, manifest, listener, or child process remains.
- Upload screenshots, traces, console logs, and redacted frontend/backend logs only on
  failure, with a bounded retention period and no secret environment dump.
- Include safe request IDs in failure summaries when available so DEV-022 logs can be
  correlated without exposing request bodies or cookies.
- Add CI/tooling contract tests for service health, browser caching, artifact paths,
  timeouts, cleanup ordering, least GitHub token permissions, and absence of production
  secrets/URLs.
- Run the suite repeatedly locally or in the equivalent CI environment and record
  browser/tool versions, test counts, durations, artifacts, and any approved deferral.
- Update this tracker and implementation record with commit hashes and evidence.
- Update the master development tracker only after the DEV-023 pull request is merged
  and accepted on the default branch.

Commit gate:

```bash
make clean
make install
make db-up
make db-upgrade
make check
make e2e
make e2e
make security-check
git diff --check
git status --short
```

## Out of Scope

- Exhaustive browser coverage of every route, validation message, viewport, keyboard
  path, screen reader, browser engine, or error condition is not part of a smoke suite.
- DEV-020 remains the owner of the complete manual accessibility, responsive, zoom,
  contrast, and assistive-technology audit. Playwright smoke success is not WCAG proof.
- Lower-level tests remain responsible for detailed authorization, cross-user access,
  malformed payloads, exact date boundaries, concurrency races, transaction rollback,
  rate-limit windows, proxy trust, redaction variants, and statistics rounding.
- Visual-regression snapshots and pixel-perfect screenshot approval are not introduced.
- Performance/load testing, synthetic production monitoring, uptime checks, and
  production browser probes are separate operational decisions.
- The suite does not target `stopimpulsebuying.us`, a developer database, staging, or
  production, and it does not provision cloud infrastructure or deploy the product.
- A test-only API route, production clock override, shortened 48-hour product rule,
  shared demo credentials, CAPTCHA bypass, or security-control bypass is forbidden.
- Browser artifacts are debugging evidence, not analytics and not a source for product
  usage tracking.
- Final release validation, manual browser acceptance, production configuration
  decisions, and the release/rollback checklist belong to DEV-024.

## Implementation Record

Complete this section as each commit lands. Record concrete files, package/browser
versions, commit hashes, commands, run IDs, test counts, durations, artifact behavior,
database names, cleanup evidence, limitations, and deferrals.

### Commit Evidence

| Commit | Hash      | Result                       | Verification                                                                                                                                            |
| ------ | --------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1      | `d9834be` | Complete                     | Playwright 1.62.1 contract passed in pinned Chromium; formatting, lint, typecheck, static contract, test listing, security, and whitespace gates passed |
| 2      | `b029216` | Complete                     | Ruff formatting/lint, 589 backend tests, Alembic drift check, and whitespace gate passed                                                                |
| 3      | `7a7c842` | Complete                     | `make e2e` run `run-20260808152536-98c2bd11` passed; prior rehearsal left zero run-owned users; 429 frontend and 599 backend tests passed               |
| 4      | `5eace49` | Complete                     | First-half run `run-20260808154334-3cc82342` and combined run `run-20260808155113-a2f60614` passed; 600 backend tests and zero residual users           |
| 5      | `2b3b672` | Complete                     | Complete run `run-20260808161234-a810a6b2` passed all four Chromium tests and cleanup; frontend lint/typecheck and 601 backend tests passed             |
| 6      | —         | Implemented; awaiting commit | Independent runs `run-20260808163520-1e8424af` and `run-20260808163700-05952a05` passed without retries; residue, quality, and security gates passed    |

### Smoke Verification Checklist

| Check                                                                | Result | Evidence                                                                                |
| -------------------------------------------------------------------- | ------ | --------------------------------------------------------------------------------------- |
| Real pinned browser runs against live React, FastAPI, and PostgreSQL | Pass   | Combined Chromium run `run-20260808155113-a2f60614`                                     |
| Local and CI targets refuse development/staging/production data      | Pass   | URL, database suffix, ordinary-database, production-domain, and explicit CI-host guards |
| Setup creates only deterministic run-owned data at Alembic head      | Pass   | Live manifest setup, migration verification, and post-run ownership assertion           |
| Cleanup removes only run-owned data and is safe when repeated        | Pass   | Exact-manifest tests and zero users after live rehearsal                                |
| Stack startup uses readiness rather than fixed sleeps                | Pass   | Live readiness plus timeout and early-exit tooling tests                                |
| Stack shutdown leaves no child process or occupied test port         | Pass   | Exact process-group and real-child reap tests; live stack run passed                    |
| Signup succeeds and browser reload restores its session              | Pass   | Signup reached dashboard; reload restored the protected session                         |
| Existing seeded account can log in through the real form             | Pass   | Seeded journey account displayed its unique eligible entry                              |
| Entry creation persists and appears in the waiting dashboard list    | Pass   | Entry survived reload and passed the PostgreSQL ownership assertion                     |
| Seeded eligible entry checks in without waiting or changing rules    | Pass   | The eligible account-owned entry was resolved as saved with its run-specific comment    |
| Statistics show saved totals and whole/fractional equivalents        | Pass   | All-time total, counts, and both manifest-defined equivalents survived a browser reload |
| Logout revokes access to protected browser routes                    | Pass   | Logout made direct protected navigation return to login                                 |
| Failure artifacts are useful, bounded, retained, and non-sensitive   | Pass   | Bounded failure-log and secret/header/cookie/database redaction tests                   |
| Repeated runs pass independently without retry-dependent success     | Pass   | Two Commit 6 runs passed with fresh IDs, zero retries, zero data, and released ports    |
| Full quality, build, migration, smoke, and security gates pass       | Pass   | `make check`, two live build/migration smoke runs, and `make security-check` passed     |

### Failure Artifact Record

| Artifact               | Success behavior | Failure behavior                      | Sensitive-data rule          |
| ---------------------- | ---------------- | ------------------------------------- | ---------------------------- |
| Screenshot             | Do not retain    | Retain current page and failure point | Isolated run only            |
| Playwright trace       | Do not retain    | Retain bounded trace                  | Upload after cleanup         |
| Browser console        | Do not retain    | Retain warnings/errors                | Redact secret-like values    |
| Frontend process log   | Do not retain    | Retain bounded startup/runtime tail   | No environment dump          |
| Backend process log    | Do not retain    | Retain bounded structured tail        | Apply DEV-021 redaction      |
| Setup/cleanup manifest | Remove           | Retain secret-free summary only       | Never include password/token |

DEV-023 remains incomplete until every commit gate passes, repeated runs are
independent, cleanup is proven, and any unresolved smoke reliability issue is either
fixed or carried into DEV-024 as an explicit release blocker.
