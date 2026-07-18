# Development Plan

## Purpose

This directory converts the approved `implementation/` design into reviewable development work. Each `DEV-xyz` item is intended to be one pull request (PR), with a narrow outcome, explicit dependencies, tests, and documentation updates.

The implementation design remains the technical source of truth. If development exposes a design conflict, update the relevant `implementation/` document (and the governing `planning/SYS-*` document when product behavior changes) in the same PR or in a prerequisite documentation PR.

## Tracking Rule

In the master tracker, use `[ ]` while a task is unfinished. Change it to `[x]` only after its PR is merged and its acceptance checks pass on the default branch.

## Category Documents

| Category | Document | Scope |
|---|---|---|
| Foundation and tooling | [1-foundation-and-tooling.md](1-foundation-and-tooling.md) | Repository scaffolding, local workflow, application foundations, schema, and CI |
| Authentication | [2-authentication.md](2-authentication.md) | Backend sessions and frontend authentication experience |
| Entries | [3-entry-management.md](3-entry-management.md) | Entry CRUD, dashboard API, and entry-management UI |
| Check-in lifecycle | [4-check-in-lifecycle.md](4-check-in-lifecycle.md) | Atomic resolution, check-in UI, and resolved comments |
| Statistics and opportunity costs | [5-statistics-and-opportunity-costs.md](5-statistics-and-opportunity-costs.md) | Aggregates, example CRUD, statistics UI, and settings UI |
| Hardening and release | [6-hardening-and-release.md](6-hardening-and-release.md) | UX hardening, security, observability, end-to-end tests, and release readiness |

## Master PR Tracker

Update this table as the canonical portfolio-level view. Detailed acceptance criteria live in the category documents.

|  | ID | PR title | Category | Depends on |
|---|---|---|---|---|
| [ ] | DEV-001 | Scaffold frontend and backend workspaces | Foundation | — |
| [ ] | DEV-002 | Add local environment and PostgreSQL workflow | Foundation | DEV-001 |
| [ ] | DEV-003 | Establish backend application foundation | Foundation | DEV-001, DEV-002 |
| [ ] | DEV-004 | Establish frontend application foundation | Foundation | DEV-001 |
| [ ] | DEV-005 | Add initial database models and migration | Foundation | DEV-002, DEV-003 |
| [ ] | DEV-006 | Add quality commands and continuous integration | Foundation | DEV-001, DEV-003, DEV-004, DEV-005 |
| [ ] | DEV-007 | Add deterministic development demo data | Foundation | DEV-005 |
| [ ] | DEV-008 | Implement authentication and session API | Authentication | DEV-005 |
| [ ] | DEV-009 | Implement authentication UI and route guards | Authentication | DEV-004, DEV-008 |
| [ ] | DEV-010 | Implement entry CRUD and dashboard API | Entries | DEV-005, DEV-008 |
| [ ] | DEV-011 | Build dashboard entry lists | Entries | DEV-009, DEV-010 |
| [ ] | DEV-012 | Build entry create, edit, and delete flows | Entries | DEV-010, DEV-011 |
| [ ] | DEV-013 | Implement atomic entry check-in API | Check-in | DEV-010 |
| [ ] | DEV-014 | Build the check-in experience | Check-in | DEV-011, DEV-013 |
| [ ] | DEV-015 | Add resolved-entry comment editing | Check-in | DEV-013, DEV-014 |
| [ ] | DEV-016 | Implement statistics aggregate API | Statistics | DEV-013 |
| [ ] | DEV-017 | Implement opportunity-cost example API | Statistics | DEV-005, DEV-008 |
| [ ] | DEV-018 | Build statistics and equivalents UI | Statistics | DEV-016, DEV-017 |
| [ ] | DEV-019 | Build opportunity-cost settings UI | Statistics | DEV-017, DEV-018 |
| [ ] | DEV-020 | Complete shared UX, accessibility, and responsive behavior | Hardening | DEV-012, DEV-015, DEV-018, DEV-019 |
| [ ] | DEV-021 | Add security and abuse protections | Hardening | DEV-008, DEV-010, DEV-017 |
| [ ] | DEV-022 | Add production observability and operational configuration | Release | DEV-003, DEV-021 |
| [ ] | DEV-023 | Add end-to-end smoke coverage | Release | DEV-007, DEV-020, DEV-021 |
| [ ] | DEV-024 | Validate release and document operations | Release | DEV-006, DEV-022, DEV-023 |

## Delivery Milestones

| Milestone | Included PRs | Exit gate | Status |
|---|---|---|---|
| M1 — Foundation | DEV-001–DEV-007 | Clean install, healthy app, reproducible migration, seed data, and green baseline CI | Not started |
| M2 — Accounts | DEV-008–DEV-009 | Signup/login/logout/session restoration pass API and UI tests | Not started |
| M3 — Entry management | DEV-010–DEV-012 | Owned CRUD and all dashboard buckets work without full-page reloads | Not started |
| M4 — Check-in | DEV-013–DEV-015 | Exact 48-hour and concurrent-transition tests pass; resolved comments are editable | Not started |
| M5 — Insights | DEV-016–DEV-019 | Date-boundary aggregates, equivalents, and example management pass | Not started |
| M6 — Release candidate | DEV-020–DEV-024 | Full CI and smoke suite pass; migration and release checklists are complete | Not started |

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
