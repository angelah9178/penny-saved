# Statistics and Opportunity Costs Development

## Category Tracker

| ID | Outcome | Depends on | Status | PR |
|---|---|---|---|---|
| DEV-016 | Correct time-ranged saved/purchased aggregates | DEV-013 | Not started | — |
| DEV-017 | Owned opportunity-cost example CRUD API | DEV-005, DEV-008 | Not started | — |
| DEV-018 | Statistics cards, filters, and calculated equivalents UI | DEV-016, DEV-017 | Not started | — |
| DEV-019 | Opportunity-cost example management UI | DEV-017, DEV-018 | Not started | — |

## DEV-016 — Implement statistics aggregate API

Scope:

- Add the supported range enum and pure UTC half-open boundary calculation.
- Implement one conditional PostgreSQL aggregate for total saved, avoided count, and purchased count using `checked_in_at`.
- Return zeros for empty ranges and never load all entries for Python aggregation.
- Add response schemas/routes and unit, repository, and API tests for every range and exact boundary.
- Cover calendar-month subtraction, month/year edges, equal end timestamps, large cent totals, and invalid ranges.

Acceptance:

- `this_month`, rolling 3/6/12-month, and `all_time` results match the implementation definitions.
- Saved contributes to saved total/avoided count; purchased contributes only to purchased count.
- Calculations use one request clock and safe integer cents.

## DEV-017 — Implement opportunity-cost example API

Scope:

- Add schemas, response mapping, owned repositories, services, and CRUD routes for examples.
- Normalize label/unit, enforce positive bounded cents, preserve stable creation order, and allow duplicate labels.
- Lock updates/deletes where required and distinguish other-owner `403` from absent `404` without leaking data.
- Add CRUD, constraint, ordering, ownership, normalization, and failure tests.

Acceptance:

- Create/update accept only the documented mutable fields; delete returns an empty `204`.
- Every database access is user-scoped and stable ordering is deterministic.
- Zero/negative/out-of-range dollar values cannot enter through API or database.

## DEV-018 — Build statistics and equivalents UI

Scope:

- Extend the stats response/service to load examples and compute equivalents with Decimal and `ROUND_HALF_UP` to one decimal.
- Build statistics cards, the range filter, opportunity-cost equivalents, and loading/empty/error states.
- Treat whole/fractional JSON values numerically rather than depending on lexical `25.0` formatting.
- Invalidate/refetch statistics after check-ins and example changes.
- Test each filter, zero totals, whole/fractional equivalents, rounding, failures, and relevant cache refresh.

Acceptance:

- Displayed totals/counts/equivalents match the selected server-calculated range.
- The browser performs formatting only; it does not reproduce aggregate or equivalent rules.
- Invalid stored zero values are defensively skipped/logged by the backend despite database prevention.

## DEV-019 — Build opportunity-cost settings UI

Scope:

- Build protected list/create/edit/delete settings flows with shared accessible form controls.
- Convert display currency to integer cents and surface field/global server errors.
- Add delete confirmation, duplicate-submit prevention, stable list behavior, and cache updates for settings and statistics.
- Test CRUD success, validation, auth expiry, ownership-safe failures, retry, and equivalents refresh.

Acceptance:

- Example changes immediately affect both settings and statistics views.
- Duplicate labels remain supported and destructive actions require confirmation.
- UI handles an empty example list with a clear creation action.

## Design Traceability

- `implementation/1-database-implementation-plan.md`: aggregate query, ranges, example constraints/order.
- `implementation/2-frontend-implementation-plan.md`: statistics and opportunity-cost presentation/state.
- `implementation/3-backend-implementation-plan.md`: statistics calculation and example service behavior.
