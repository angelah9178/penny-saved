# DEV-024 Release-Candidate Decision

## Decision

**Release blocked — 2026-08-12.**

Commit 6 puts together the evidence produced by Commits 1–5. It does not add another
product feature or deploy the application. The code and local release procedures pass
their available checks, but the candidate cannot be declared ready until the named
production decisions below are approved and verified.

The master development plan also leaves DEV-019 through DEV-024 and milestone M6 open.
That is correct: this branch is `DEV-022-production-operations`, and the plan requires
the work to be merged and accepted on the default branch before those boxes change.

## Candidate Reviewed

- Baseline full Git SHA: `89cfbe20b4e2bdb1ea72304c4b0f3f9fcebb2a15`
- Baseline includes: DEV-024 Commits 1–5
- Migration head: `0002_rate_limit_counters`
- Manual acceptance: Pass, user reviewer, 2026-08-12
- Release procedure: [`../operations/RELEASE.md`](../operations/RELEASE.md)
- Deployment performed: No

The final Commit 6 SHA and CI link must be added after this record is committed and CI
completes. Until then, this baseline SHA identifies the immutable code audited locally.

## Evidence Consolidated from Commits 1–5

| Source   | What it established                                                                                                                 | Result |
| -------- | ----------------------------------------------------------------------------------------------------------------------------------- | ------ |
| Commit 1 | Release decisions have owners, evidence requirements, deadlines, and explicit statuses                                              | Pass   |
| Commit 2 | A clean install, database migration, production build, application startup, browser smoke journey, cleanup, and security scans work | Pass   |
| Commit 3 | Migrations can be rehearsed both ways and a PostgreSQL backup can be restored into an isolated database                             | Pass   |
| Commit 4 | Automated accessibility coverage and the user's signed manual product/accessibility checks pass                                     | Pass   |
| Commit 5 | An ordered release, verification, rollback, recovery, and escalation checklist exists and is machine-validated                      | Pass   |

## Final Local Gate Evidence

The full local gate completed on 2026-08-12 against the Commit 1–5 baseline plus this
decision record:

- clean dependency installation completed from the pinned Python requirements and npm lockfile;
- PostgreSQL 16 was healthy and Alembic was at `0002_rate_limit_counters`;
- formatting, ESLint, Ruff, TypeScript, production builds, and operations validation passed;
- all 429 frontend tests and all 610 backend tests passed;
- live Chromium runs `run-20260812195221-d51d2738` and
  `run-20260812195241-62b76a10` passed sequentially and each cleaned its database and ports;
- the isolated restore rehearsal passed at `0002_rate_limit_counters`, removed its
  disposable target, and produced transient backup SHA-256
  `643a885533c3ae6de58e605df44810bc6c23c018199a3655ff1a9233c5ffc57b`;
- backend audit found no known runtime vulnerability, and frontend review found no
  untriaged high/critical advisory.

CI cannot validate the uncommitted decision record. Add the final Commit 6 SHA and CI
link after commit/push; this remains evidence required before changing the result to ready.

## Blocking Decisions

The authoritative details are in [`release-decisions.md`](release-decisions.md).
Before a ready decision, the assigned owners must approve and verify:

- Oracle VPS image and patch policy;
- DNS ownership and production records;
- installed reverse-proxy and service-supervisor versions;
- service account, filesystem paths, and secret delivery/permissions;
- TLS client, renewal monitoring, and renewal owner;
- production PostgreSQL roles, access, backup destination, encryption, off-host copy,
  retention, recovery-point objective, and recovery-time expectation;
- log retention/readers, metrics collector/responders, and incident escalation contacts;
- session cleanup ownership.

The React Router advisory deferral is approved only through 2026-09-07 and must be
re-reviewed before that date. There are no other approved deferrals recorded.

## Required Next Action

The product owner and DEV-024 release owner must resolve the blocked control-sheet
items, verify them on the selected production infrastructure, rerun the final gate on
the immutable candidate, add the CI link and final SHA, and then record a new explicit
ready/no-go decision. None of those steps is authorized by this document.

After the relevant DEV branches are merged and accepted, reconcile DEV-019 through
DEV-024 in `0-development-plan.md`; update M5/M6 only when all included work meets its
exit gate.

## Authorization Boundary

This decision does not authorize deployment, DNS changes, TLS provisioning, service
installation, secret access, or any production database operation.
