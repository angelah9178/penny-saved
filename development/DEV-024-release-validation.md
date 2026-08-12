# DEV-024 — Release Validation

## Table of Contents

- [Commit Tracker](#commit-tracker)
- [Objective](#objective)
- [What Release Validation Means](#what-release-validation-means)
- [Release Rules](#release-rules)
- [Commit 1 — Inventory Decisions and Blockers](#commit-1--inventory-decisions-and-blockers)
- [Commit 2 — Prove a Clean Build and Startup](#commit-2--prove-a-clean-build-and-startup)
- [Commit 3 — Rehearse Data Safety and Rollback](#commit-3--rehearse-data-safety-and-rollback)
- [Commit 4 — Complete Manual Product Acceptance](#commit-4--complete-manual-product-acceptance)
- [Commit 5 — Finalize the Release Runbook](#commit-5--finalize-the-release-runbook)
- [Commit 6 — Record the Release-Candidate Decision](#commit-6--record-the-release-candidate-decision)
- [Out of Scope](#out-of-scope)
- [Implementation Record](#implementation-record)

## Commit Tracker

Change `[ ]` to `[x]` only after that commit is implemented, committed, and its gate
passes.

|                  | Commit                                                | Short title                 | Depends on                  |
| ---------------- | ----------------------------------------------------- | --------------------------- | --------------------------- |
| &#91;x&#93;      | [1](#commit-1--inventory-decisions-and-blockers)      | Inventory release decisions | DEV-006, DEV-021, DEV-022   |
| &#91;x&#93;      | [2](#commit-2--prove-a-clean-build-and-startup)       | Prove clean startup         | Commit 1 and DEV-023        |
| &#91;x&#93;      | [3](#commit-3--rehearse-data-safety-and-rollback)     | Rehearse recovery           | Commit 2 and DEV-022        |
| &#91;&#160;&#93; | [4](#commit-4--complete-manual-product-acceptance)    | Complete manual acceptance  | Commit 2 and DEV-020        |
| &#91;&#160;&#93; | [5](#commit-5--finalize-the-release-runbook)          | Finalize release procedure  | Commits 1–4 and DEV-022     |
| &#91;&#160;&#93; | [6](#commit-6--record-the-release-candidate-decision) | Record go/no-go evidence    | Commits 1–5 and DEV-001–023 |

## Objective

DEV-024 decides whether the completed V1 code is ready to become a release candidate.
It brings together the quality, security, accessibility, operations, migration, and
browser evidence created by DEV-001 through DEV-023.

In plain English, earlier tasks built and tested the product. DEV-024 performs the
final inspection and writes down exactly how an authorized release would be prepared,
verified, and rolled back. It answers:

- Can a clean machine install, migrate, test, build, and start the application from
  the committed documentation?
- Are all automated checks and the real-browser journey green?
- Have the remaining manual accessibility and product checks been completed?
- Can the database be backed up and restored before a release?
- Is the exact immutable revision known, and is there enough disk space to install it?
- Are domain, DNS, TLS, secrets, service ownership, backups, logs, metrics, sessions,
  and incident responsibility decided?
- Does the release owner know when to stop, roll the application back, or declare a
  blocker?

DEV-024 validates and documents these answers. It does not connect to a production
host, change DNS, provision infrastructure, migrate production data, or deploy code.

## What Release Validation Means

Release validation is the last evidence-gathering step before deployment authorization.
It is broader than running tests: it checks the exact build, its data-change plan, the
operator instructions, manual behavior, security findings, and unresolved decisions as
one release candidate.

A successful DEV-024 result means either:

1. **Ready:** every required check passes and every production decision has an owner
   and an approved value; or
2. **Blocked:** the code may be healthy, but one or more explicitly named decisions or
   host-level checks still prevent a safe release.

“Probably fine,” a blank checklist cell, an expired advisory exception, or an
unassigned operational decision is not a pass. A blocker is an acceptable DEV-024
outcome when it is recorded honestly; silently assuming an answer is not.

## Release Rules

- Validate one immutable Git revision. Record its full SHA and do not call a moving
  branch name the release artifact.
- Use locked frontend dependencies and pinned backend requirements. Do not perform an
  opportunistic dependency upgrade during final verification.
- Run database checks against disposable PostgreSQL 16 data. Never rehearse destructive
  operations against development or production data.
- Production migrations move forward through reviewed Alembic revisions. Downgrading a
  live database is a separate destructive decision, not the default rollback plan.
- Distinguish application rollback from database rollback. An older application may
  be restarted only when its schema compatibility has been reviewed.
- Take and verify a recoverable backup before any future production migration.
- Treat the DEV-021 React Router advisory review date and every current dependency scan
  as release inputs; do not suppress or auto-fix findings merely to make the gate green.
- Complete the remaining interactive accessibility audit with a human-operated browser
  and assistive technology. Automated Playwright checks do not replace it.
- Use the production configuration examples without real secrets. Record only secret
  names, owners, delivery methods, and permission evidence—not secret values.
- Every release decision needs an owner, approved value, verification method, and date.
- Failed checks stop the candidate unless an authorized owner records a narrow,
  time-bounded deferral with its risk and follow-up.
- Do not add or run a deployment command. Any future production mutation requires
  separate, explicit authorization.

## Commit 1 — Inventory Decisions and Blockers

**Status:** Complete in `df87f5f`; Markdown source conversion in `e595c5d`.

### In Plain English

Commit 1 creates the release control sheet. It gathers every unfinished choice from
the roadmap, security review, manual audit, and operations runbook into one place.

A release control sheet is one organized checklist containing every decision that
must be made before releasing the application. For Penny Saved, it records who manages
the server, domain and DNS settings, TLS renewal, secret storage, PostgreSQL ownership,
backup location and retention, log and metric access, incident response, session
lifetime, USD-only scope, and excluded email features. Each item contains a responsible
owner, the approved answer or current blocker, the evidence needed to verify it, a
deadline, and a status such as ready, deferred, or blocked. It prevents “the code
passes” from being mistaken for “production responsibilities are settled.”

This commit does not fix or approve those choices. It prevents a release from moving
forward while important details are scattered across documents or left implicit. Each
item gets an owner, deadline, proposed or approved value, required evidence, and a
status of ready, deferred, or blocker.

The initial inventory must include the Oracle VPS operating system and patch policy,
domain and DNS ownership, reverse proxy, process supervisor and service account, TLS
client and renewal owner, secret delivery, PostgreSQL ownership, backup destination
and retention, log retention/access, metrics collection/access, incident contact,
USD-only product scope, session lifetime and cleanup retention, and email-dependent
features that remain outside V1.

### Where the Answers Come From

The implementation does not guess these answers. Each answer must come from one of
three places:

1. **Existing approved evidence:** Repository requirements and completed DEV guides
   already establish some answers. For example, V1 is USD-only, PostgreSQL 16 is the
   current target, the application uses same-origin secure cookies, and production
   migrations normally move forward.
2. **The responsible owner:** Infrastructure and business decisions must be supplied
   and approved by the person who owns them. For example, the server owner chooses the
   supported Oracle VPS operating system, the domain owner confirms DNS, and the
   operations owner approves backup retention and incident escalation.
3. **An explicit blocker:** If no approved answer or evidence exists, the sheet says
   `Blocked`. It records who must answer, what evidence is required, and the deadline.
   A proposed example configuration is not silently promoted to a production decision.

The source is recorded beside every answer. Code and documentation can validate facts
such as configuration shape, dependency versions, migration behavior, and test
results. They cannot decide ownership, acceptable business risk, recovery targets,
retention policy, or real infrastructure details on behalf of the responsible person.

Suggested commit message:

```text
Commit 1: Inventory release decisions and blockers
```

Implement:

- Add a single release-decision register linked to the detailed DEV-021, DEV-022, and
  DEV-023 evidence rather than copying their entire implementation records.
- Record owner, deadline, approved value or explicit blocker, evidence required, and
  current status for every production decision.
- Review the current frontend and backend dependency reports and the dated React Router
  advisory triage; upgrade safely or renew/reject the exception with evidence.
- Confirm that V1 remains USD-only and document what users will see.
- Confirm session idle/absolute lifetime, cookie policy, expired-session cleanup owner,
  and retention expectations.
- State that password reset, email verification, MFA, account deletion, and outbound
  email are not silently promised by V1 unless product scope is explicitly changed.
- Add a static validation test that rejects missing owners, blank statuses, expired
  decision dates, and release decisions containing secret values.
- Do not convert unresolved infrastructure choices into guessed defaults.

Commit gate:

```bash
make operations-check
make security-check
make backend-test
git diff --check
```

## Commit 2 — Prove a Clean Build and Startup

**Status:** Complete in `0c8f44e`.

### In Plain English

Commit 2 proves that the repository instructions work from a clean starting point. A
release candidate is not ready if it works only in a developer directory containing
old dependencies, generated files, or an already-migrated database.

The rehearsal removes generated artifacts, installs the pinned dependencies, starts
disposable PostgreSQL, applies migrations, optionally creates local demo data, runs all
quality checks, builds the production frontend, constructs the production-configured
backend, and starts the assembled application on loopback. It then runs the DEV-023
browser journey and shuts everything down cleanly.

This is a reproducibility test, not a deployment. It uses only local/disposable
resources and safe example configuration.

### What Commit 2 Tested

Commit 2 is primarily testing and verification. It does not add a user-facing feature
or deploy the application. It proves that a clean environment can:

- install the pinned Python dependencies and locked npm packages;
- start PostgreSQL 16 and apply the complete migration history;
- create the deterministic local demo data safely;
- pass formatting, linting, TypeScript, frontend tests, and backend tests;
- build the production frontend and construct the configured backend;
- start the assembled frontend and backend on loopback;
- complete the real Chromium signup-to-logout journey; and
- stop its processes and remove all isolated browser-test data afterward.

In plain English, it asks: “If this exact repository revision were given to a clean
machine, could it build and run correctly without relying on leftover developer files?”
The recorded rehearsal answered yes for the tested local/disposable environment. It
does not prove that an unconfigured production server is ready for deployment.

Suggested commit message:

```text
Commit 2: Prove clean release-candidate startup
```

Implement:

- Rehearse `make clean` and `make install` using the repository's pinned Python, Node,
  npm, backend requirement, frontend lockfile, and Playwright versions.
- Start PostgreSQL 16 and prove the empty database reaches the exact Alembic head.
- Run formatting, linting, TypeScript, all frontend/backend tests, production builds,
  backend construction, operations validation, and security scans.
- Follow the documented local install/migrate/seed/start workflow exactly; correct the
  documentation when a clean operator cannot follow it.
- Start the built frontend and production-configured backend on loopback, verify
  liveness/readiness, and run the complete isolated Chromium smoke journey.
- Record revision SHA, tool versions, migration head, test counts, build output, smoke
  run IDs, duration, and cleanup evidence.
- Add or update tooling tests so the clean-room command cannot accept production URLs,
  real secrets, unsafe databases, or unbounded processes.

Commit gate:

```bash
make clean
make install
make db-up
make db-upgrade
make check
make e2e
make security-check
git diff --check
```

## Commit 3 — Rehearse Data Safety and Rollback

**Status:** Complete in `cdf8d67`.

### In Plain English

Commit 3 proves that data can be protected before a release and explains what rollback
actually means.

Commit 3 is also primarily testing, but it focuses specifically on protecting and
recovering database data. Commit 2 asked whether a clean machine could build and run
the application. Commit 3 asks: “If a release changes the database or something goes
wrong, can the data be protected and recovered safely?”

It tests upgrading an empty PostgreSQL database to the latest migration, downgrading
the disposable database through the migration history, re-upgrading it, checking that
the application models and migrations agree, creating a PostgreSQL backup, restoring
that backup into a separate disposable database, verifying the restored schema and row
counts, and removing the temporary backup and restored database.

First, an empty disposable database is upgraded to the current migration head,
downgraded through the supported migration history, re-upgraded, and checked for model
drift. Next, a PostgreSQL 16 custom-format backup is restored into a separately named
disposable database and its schema and representative row counts are compared.

Finally, the guide records the application rollback boundary: stop the new artifact,
start the previously approved immutable artifact only if it is compatible with the
current schema, and keep the database forward unless a separately approved recovery
decision requires restoring or reversing data.

The distinction is important:

- **Application rollback:** restart the previously approved application artifact, but
  only when it is compatible with the database schema already in place.
- **Database rollback:** reverse migrations or restore data. This is more destructive,
  can discard writes, and requires a separate operator decision and verified backup.

Commit 3 rehearses these operations only on disposable local PostgreSQL databases. It
does not downgrade, restore, delete, or otherwise change production data.

Suggested commit message:

```text
Commit 3: Rehearse release data recovery
```

Implement:

- Run clean Alembic upgrade, downgrade-to-base, re-upgrade, and drift checks against a
  disposable PostgreSQL 16 database.
- Review every revision's forward and reverse operations, locks, expected duration,
  compatibility, and data-loss implications.
- Rehearse the DEV-022 guarded backup/restore procedure with matching PostgreSQL 16
  tools and verify the restored migration revision and representative counts.
- Record backup destination requirements, encryption, retention, off-host copy,
  restore owner, recovery-point objective, and recovery-time expectation—or mark them
  blockers.
- Document application rollback separately from database restore/downgrade, including
  schema compatibility and the point at which rollback must stop for operator review.
- Prove temporary archives and restore databases are removed in success and failure
  paths without deleting the source database.
- Do not run a downgrade, restore, or cleanup operation against production.

Commit gate:

```bash
make db-upgrade
make backend-test
make rehearse-restore
make operations-check
git diff --check
```

## Commit 4 — Complete Manual Product Acceptance

**Status:** Automated verification complete; human acceptance pending.

### In Plain English

Commit 4 completes the checks that automation cannot honestly certify. A person uses
the release candidate like a user and finishes the interactive accessibility audit
left open by DEV-020.

The reviewer walks through signup, login, entry creation, check-in, statistics,
opportunity-cost settings, error states, reload, logout, and protected-route behavior.
They also inspect keyboard operation, visible focus, zoom, reflow, contrast, reduced
motion, landmarks, headings, labels, status announcements, and a supported screen
reader/browser combination.

DEV-023 already proves the critical path automatically. This commit provides human
acceptance evidence; it does not duplicate every automated assertion.

Codex can implement and verify the objective browser and code checks, but it cannot
hear a real screen reader or make a person's usability judgment. The exact remaining
steps are in
[`development/DEV-024-manual-acceptance.md`](DEV-024-manual-acceptance.md). Commit 4
must remain unchecked until a human completes and signs that checklist.

### Automated Checks Completed

- Representative `jest-axe` scans cover the application shell, authentication form,
  loaded dashboard, entry form, open dialog, and route-error recovery.
- Component and integration tests cover keyboard activation, form error-summary focus,
  skip-link behavior, route focus/title changes, dialog trapping/Escape/focus return,
  pending-action protection, live regions, session expiry, empty/error/retry states,
  and unsaved-change handling.
- A real Chromium production-build test verifies the rendered skip link becomes visible
  when focused and moves focus to main content.
- Chromium emulates `prefers-reduced-motion: reduce` and verifies the rendered
  transition duration is reduced.
- At a 320 CSS-pixel viewport, Chromium verifies no page-level horizontal overflow and
  checks visible dashboard buttons, selects, and entry actions render at least 44 by
  44 CSS pixels.
- The five-test live suite still completes signup, session restoration, entry creation,
  login, check-in, statistics/equivalents, reload, logout, protected-route denial, and
  cleanup against real PostgreSQL.

### Human Checks Still Required

- Complete the whole journey with a physical keyboard and judge focus visibility/order.
- Listen to the journey using a real screen reader/browser combination.
- Judge whether headings, labels, validation, announcements, empty states, and errors
  are understandable rather than merely present.
- Use actual browser 200% zoom and judge reflow, readability, and reachability.
- Inspect long content and narrow/mobile layouts visually.
- Measure rendered text, controls, borders, status, and focus-indicator contrast.
- Enable the operating system's reduced-motion setting and judge the experience.
- Record reviewer, date, versions, findings, severity, fixes/deferrals, and sign-off.

Suggested commit message:

```text
Commit 4: Complete manual release acceptance
```

Implement:

- Finish every pending item in the DEV-020 interactive audit and link the exact
  evidence instead of merely marking the parent task complete.
- Test the production build at supported desktop and narrow/mobile viewport sizes,
  200% browser zoom, keyboard-only navigation, and reduced-motion preference.
- Verify focus order and visibility, modal focus handling, form labels/errors, live
  status announcements, page titles, heading/landmark structure, and logout behavior.
- Perform the critical journey with at least one documented screen reader/browser
  combination and record versions, findings, and fixes.
- Confirm empty, loading, validation, unauthorized, not-found, server-error, and
  database-unavailable experiences expose understandable, non-sensitive feedback.
- Recheck USD formatting and the declared V1 product limitations.
- Treat unresolved serious or critical usability/accessibility findings as release
  blockers; record narrow approved deferrals with owner and date.

Commit gate:

```bash
make check
make e2e
make frontend-security-check
git diff --check
```

The interactive checklist itself must also be signed and dated; the commands above do
not replace human evidence.

## Commit 5 — Finalize the Release Runbook

**Status:** Not started.

### In Plain English

Commit 5 turns all earlier operational work into one ordered checklist an authorized
release owner can follow. It covers preparation, the release window, verification,
rollback, and incident escalation.

The checklist begins with backups, disk space, the immutable revision, configuration
and secret permissions, database health, and an explicit go/no-go decision. It then
describes forward migration, application restart, health checks, browser verification,
log/metric observation, and the exact rollback threshold. Every step identifies who
performs it and what evidence proves it succeeded.

This commit documents a future authorized operation. It does not execute it or add a
one-command deployment shortcut.

Suggested commit message:

```text
Commit 5: Finalize the release and rollback runbook
```

Implement:

- Add ordered pre-release, release, verification, rollback, and post-release sections.
- Require free disk-space and inode checks before installing an artifact or creating a
  backup; record minimum safe thresholds and the owner who can stop the release.
- Require a full immutable Git SHA/artifact identity, integrity evidence, previous
  approved artifact, dependency lock verification, and configuration version.
- Require a verified pre-migration backup and exact Alembic current/head evidence.
- Document forward migration, graceful process restart, liveness/readiness, private
  metrics, safe request-log correlation, and real browser checks.
- Define observation duration, success thresholds, rollback triggers, escalation
  contacts, and the difference between application rollback and data recovery.
- Include DNS, TLS certificate/renewal, proxy validation, service user, secret file
  permissions, PostgreSQL locality, backup retention, log retention, and metric access.
- Validate example commands statically and on disposable resources where possible.
- Clearly label every command that would require separate production authorization.

Commit gate:

```bash
make operations-check
make rehearse-restore
make e2e
make security-check
git diff --check
```

## Commit 6 — Record the Release-Candidate Decision

**Status:** Not started.

### In Plain English

Commit 6 performs the final audit and records a go/no-go result for one immutable
revision. It does not declare success merely because most tests passed.

Every DEV-001 through DEV-023 acceptance item must be complete, linked to evidence, or
covered by an explicitly approved deferral. CI, the clean-room gate, migrations,
restore rehearsal, browser smoke tests, security review, manual acceptance, and the
operations checklist are reviewed together.

If everything required is ready, the record says **release candidate ready**. If a
host decision or validation remains unresolved, it says **release blocked** and names
the owner and next action. Both are honest completion states for documentation; only
the former permits a separately authorized deployment process to begin.

Suggested commit message:

```text
Commit 6: Record the V1 release-candidate decision
```

Implement:

- Run the complete final gate from a clean worktree against the immutable candidate
  revision and record CI links plus local evidence.
- Reconcile every DEV tracker. Mark a parent task complete only when its merge/default-
  branch rule and acceptance criteria are satisfied.
- Confirm no expired security triage, unresolved serious accessibility issue, missing
  backup evidence, unsafe migration, or ownerless operational decision is hidden.
- Record all approved deferrals with risk, approver, expiry, and follow-up issue.
- Update README installation, environment, operations, troubleshooting, and release
  references so they match the verified commands.
- Update the master development tracker and M6 milestone only after the required work
  is merged and accepted on the default branch.
- Produce a dated release-candidate evidence table containing full SHA, migration head,
  dependency/tool versions, test counts, smoke run IDs, manual-audit record, backup/
  restore evidence, decision-register status, and final ready/blocked outcome.
- Do not deploy, change DNS, install a service, provision TLS, or mutate production.

Commit gate:

```bash
make clean
make install
make db-up
make db-upgrade
make check
make e2e
make e2e
make rehearse-restore
make operations-check
make security-check
git diff --check
git status --short
```

## Out of Scope

- Deploying to the Oracle VPS or any production environment.
- Changing DNS records, opening firewall ports, provisioning TLS certificates, or
  installing/configuring Nginx, systemd, PostgreSQL, collectors, or backup services on
  a real host.
- Reading, writing, rotating, or displaying real production secrets.
- Migrating, downgrading, restoring, deleting, or otherwise mutating production data.
- Automatically resolving release blockers or approving product/operations decisions.
- Adding post-V1 product features such as password reset, email verification, MFA,
  account deletion, multiple currencies, or user-visible session management.
- Load testing, penetration testing, external uptime monitoring, analytics, and a
  formal disaster-recovery exercise on production infrastructure.
- Treating automated smoke tests as a replacement for manual accessibility acceptance.

## Implementation Record

Complete this section as each commit lands. Record commit hashes, exact commands,
versions, test counts, migration heads, smoke run IDs, manual evidence, backup/restore
results, decisions, deferrals, and blockers.

### Commit Evidence

| Commit | Hash      | Result                   | Verification                                                                                                                                           |
| ------ | --------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1      | `df87f5f` | Complete                 | Validated 15-item decision register; operations checks, 609 backend tests, and dependency security scans passed; `e595c5d` made Markdown authoritative |
| 2      | `0c8f44e` | Complete                 | Clean install, PostgreSQL 16 migration/seed, all checks/builds, Chromium run `run-20260812190432-5c87f8bd`, cleanup, and security passed               |
| 3      | `cdf8d67` | Complete                 | Migration cycle, seven focused safety tests, 609 backend tests, PostgreSQL 16 restore at `0002_rate_limit_counters`, and exact cleanup passed          |
| 4      | —         | Human acceptance pending | Automated accessibility/focus/state coverage and five-test Chromium run `run-20260812192653-a3b53b17` passed; signed human checklist remains required  |
| 5      | —         | Not started              | —                                                                                                                                                      |
| 6      | —         | Not started              | —                                                                                                                                                      |

### Release-Candidate Evidence

| Evidence                                      | Result  | Record                                                                                                              |
| --------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------- |
| Immutable revision and artifact identity      | Pending | —                                                                                                                   |
| CI and complete clean-room quality gate       | Pending | —                                                                                                                   |
| Migration upgrade/downgrade/re-upgrade/drift  | Pass    | Disposable PostgreSQL completed base → head → base → head; Alembic reported no model drift                          |
| Backup and isolated restore rehearsal         | Pass    | PostgreSQL 16 custom archive restored at `0002_rate_limit_counters`; revision/counts matched and target was removed |
| Production build and loopback startup         | Pending | —                                                                                                                   |
| Repeated live Chromium smoke journey          | Pending | —                                                                                                                   |
| Dependency scans and advisory review          | Pending | —                                                                                                                   |
| Manual product and accessibility acceptance   | Pending | Automated portion passed; complete and sign `DEV-024-manual-acceptance.md`                                          |
| Production decision register                  | Pending | —                                                                                                                   |
| Release, verification, and rollback checklist | Pending | —                                                                                                                   |
| Approved deferrals                            | Pending | —                                                                                                                   |
| Final release-candidate decision              | Pending | —                                                                                                                   |

### Commit 2 Clean-Room Evidence

On 2026-08-12, revision `e595c5d` was rehearsed using local and disposable resources:

- `make clean` removed only enumerated generated artifacts, and `make install`
  restored the pinned backend requirements and locked frontend dependency graph.
- PostgreSQL 16.14 reported healthy. The local database migrated to
  `0002_rate_limit_counters`, matching the repository's sole Alembic head.
- `make check` passed formatting, ESLint/Ruff, TypeScript, all frontend and backend
  tests, the frontend production build, backend construction, and operations
  validation. The backend suite contained 609 tests.
- The documented `make seed-demo` workflow passed its local database guard, migration
  check, single transaction, deterministic reconciliation, and unrelated-row
  preservation contract.
- The built React frontend and FastAPI backend started on loopback, passed readiness,
  and completed all four Playwright Chromium smoke tests in run
  `run-20260812190432-5c87f8bd` without retries.
- Post-run verification found zero E2E users, sessions, entries, examples, temporary
  manifests, or application listeners on the two test ports.
- `make security-check` found no known backend runtime vulnerability and no untriaged
  high/critical frontend advisory. The existing React Router non-RSC exception remains
  time-bounded in the release control sheet.

Versions: Node.js 22.23.1, npm 10.9.8, Python 3.14.4, Ruff 0.15.22, pytest
9.0.2, Playwright 1.62.1, and PostgreSQL 16.14. This was a reproducibility rehearsal;
it did not access or change a production host, DNS, TLS, secrets, or production data.

### Commit 3 Data-Recovery Evidence

On 2026-08-12, the guarded data-safety rehearsal completed against the dedicated local
`penny_saved_test` database and a separately named disposable restore database:

- The migration integration test upgraded an empty PostgreSQL database to head,
  downgraded it to base, re-upgraded it to `0002_rate_limit_counters`, and confirmed
  the SQLAlchemy models require no additional Alembic operation.
- Revision `0001_initial_schema` creates all core account, session, entry, and
  opportunity-cost tables. Its downgrade drops those tables and their contents, so it
  is destructive and is not an ordinary production rollback step.
- Revision `0002_rate_limit_counters` creates only the shared rate-limit table and its
  expiry index. Its downgrade drops that table and its counters. Both revisions take
  PostgreSQL DDL locks; actual production duration and lock impact must be reviewed
  against the real database size before release authorization.
- The matching PostgreSQL 16 tools created a custom-format archive and restored it into
  `penny_saved_dev022_restore_verify`. Source and target both reported migration
  revision `0002_rate_limit_counters` and matching representative counts:
  `users=0`, `impulse_purchase_entries=0`, and `sessions=0`.
- The transient archive SHA-256 was
  `36119345707822346658486a26082ca6580b759c30a5c7ee64ac2b763cfba963`.
  The disposable database and temporary archive directory were removed afterward;
  an explicit database query returned zero matching restore databases.
- Seven focused migration/restore safety tests, all 609 backend tests, and the
  production operations validator passed.

The rehearsal proves the repository procedure on disposable local resources. The
release control sheet still blocks production until backup destination, encryption,
off-host copy, retention, restore owner, recovery-point objective, and recovery-time
expectation are approved. Application rollback keeps the database forward unless a
separately authorized recovery decision says otherwise.

### Required Production Decisions

The machine-validated source of truth is
[`development/release-decisions.md`](release-decisions.md). This readable summary
must be reconciled with that register whenever a decision changes.

| Decision                         | Owner                 | Approved value / blocker                                      | Status   |
| -------------------------------- | --------------------- | ------------------------------------------------------------- | -------- |
| Oracle VPS OS and patch policy   | DEV-024 release owner | No host image or patch policy approved                        | Blocked  |
| Domain and DNS ownership         | Product owner         | Canonical origin known; ownership and records unverified      | Blocked  |
| Reverse proxy and version        | DEV-024 release owner | Nginx candidate; installed version unverified                 | Blocked  |
| Service supervisor and user      | DEV-024 release owner | systemd/service-user candidates; host behavior unverified     | Blocked  |
| TLS client and renewal owner     | DEV-024 release owner | Client, schedule, alert, and owner unapproved                 | Blocked  |
| Secret delivery and permissions  | DEV-024 release owner | Placeholder contract exists; delivery/readers unapproved      | Blocked  |
| PostgreSQL version and ownership | DEV-024 release owner | PostgreSQL 16/local target; production ownership unverified   | Blocked  |
| Backup destination and retention | DEV-024 release owner | Local restore passes; production policy unapproved            | Blocked  |
| Log retention and access         | DEV-024 release owner | Structured journal candidate; limits/readers unapproved       | Blocked  |
| Metrics collection and access    | DEV-024 release owner | Private endpoint exists; collector/responders unapproved      | Blocked  |
| Incident contact and escalation  | Product owner         | No contact, response window, or threshold approved            | Blocked  |
| USD-only V1 scope                | Product owner         | USD-only V1; multi-currency is excluded                       | Ready    |
| Session lifetime and retention   | DEV-024 release owner | 30-day absolute sessions; cleanup ownership unapproved        | Blocked  |
| Email-dependent feature scope    | Product owner         | Reset, verification, MFA, and outbound account email excluded | Ready    |
| React Router advisory            | DEV-024 release owner | Non-RSC applicability exception through 2026-09-07            | Deferred |

DEV-024 is complete only when the evidence supports a dated **release candidate
ready** decision or an honest **release blocked** decision with every blocker assigned.
Neither outcome authorizes deployment by itself.
