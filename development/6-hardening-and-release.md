# Hardening and Release Development

## Category Tracker

| ID | Outcome | Depends on | Status | PR |
|---|---|---|---|---|
| DEV-020 | Consistent accessible, responsive, resilient product UX | DEV-012, DEV-015, DEV-018, DEV-019 | Not started | — |
| DEV-021 | Public-facing security and abuse baseline | DEV-008, DEV-010, DEV-017 | Not started | — |
| DEV-022 | Production-grade logging, headers, settings, and health behavior | DEV-003, DEV-021 | Not started | — |
| DEV-023 | Automated critical-user-journey smoke coverage | DEV-007, DEV-020, DEV-021 | Not started | — |
| DEV-024 | Verified, documented release candidate | DEV-006, DEV-022, DEV-023 | Not started | — |

## DEV-020 — Complete shared UX, accessibility, and responsive behavior

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

## DEV-021 — Add security and abuse protections

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

## DEV-022 — Add production observability and operational configuration

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

## DEV-023 — Add end-to-end smoke coverage

Scope:

- Add a small browser smoke suite for signup/login, create entry, seeded eligible check-in, statistics/equivalents, and logout.
- Run against the real frontend/backend and PostgreSQL with isolated deterministic data.
- Provide local and CI commands, failure artifacts, and reliable readiness/cleanup behavior.
- Keep deeper boundary/authorization/concurrency coverage in lower-level suites.

Acceptance:

- The critical journey passes repeatedly in CI without timing sleeps for the 48-hour rule.
- Failed runs retain useful non-secret diagnostics.
- Test isolation prevents state leakage and never targets development or production data.

## DEV-024 — Validate release and document operations

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

## Design Traceability

- `implementation/0-implementation-plan.md`: hardening gate, definition of done, security/operations, open items.
- `implementation/2-frontend-implementation-plan.md`: states, accessibility, responsive design, frontend security.
- `implementation/3-backend-implementation-plan.md`: security, abuse controls, observability, test acceptance.
- `implementation/4-development-tools-implementation-plan.md`: CI, Oracle operations boundary, documentation rules.
