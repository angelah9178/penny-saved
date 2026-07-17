# Entry Management Development

## Category Tracker

| ID | Outcome | Depends on | Status | PR |
|---|---|---|---|---|
| DEV-010 | Owned entry CRUD and four-bucket dashboard API | DEV-005, DEV-008 | Not started | — |
| DEV-011 | Dashboard renders deterministic entry buckets | DEV-009, DEV-010 | Not started | — |
| DEV-012 | Complete waiting-entry create, edit, and delete UX | DEV-010, DEV-011 | Not started | — |

## DEV-010 — Implement entry CRUD and dashboard API

Scope:

- Add entry Pydantic schemas, response mapping, repositories, services, and routes for create/list/detail/update/delete.
- Normalize strings and enforce positive bounded integer cents without floating-point API/database values.
- Scope every primary query by authenticated user and use the minimal existence check required to distinguish `403` from `404`.
- Partition list results into `needs_check_in`, `waiting`, `saved`, and `purchased` with one request clock and deterministic ordering.
- Permit core edits/deletion only while stored status is waiting; return `204` with no body for delete.
- Test ownership, normalization, ordering ties, exact derived bucket boundaries, lifecycle conflicts, and response/error contracts.

Acceptance:

- All four arrays are always present and derived fields use the same request-scoped UTC clock.
- Cross-user access returns the contractually required `403` without leaking resource data; unknown IDs return `404`.
- Entry responses consistently include `updated_at`, bucket, and eligibility fields specified by the design.

## DEV-011 — Build dashboard entry lists

Scope:

- Build the protected dashboard and components for all four buckets.
- Display item, formatted USD price, timing/status, comments where relevant, and correct actions per stored/derived state.
- Use TanStack Query keys and the credentialed API client; implement loading, empty, expired-auth, and retryable error states.
- Preserve backend ordering and avoid duplicating eligibility/business calculations in the browser beyond display countdowns.
- Add component tests for all buckets, zero data, request failure, and auth expiry.

Acceptance:

- Dashboard data renders after auth restoration and all four empty/non-empty states are understandable.
- Eligible entries link to check-in while younger waiting entries expose only legal waiting actions.
- Currency formatting is frontend-only and API cents remain integers.

## DEV-012 — Build entry create, edit, and delete flows

Scope:

- Build shared create/edit form controls for item name, price, and reason wanted.
- Parse user currency input deterministically into integer cents and show safe validation errors.
- Add waiting-entry detail/edit navigation and an explicit delete confirmation.
- On successful mutations, update/invalidate detail and dashboard queries so results appear without a reload.
- Handle duplicate submission, lifecycle conflicts caused by stale UI, server failures, and cancellation.
- Add MSW-backed tests for create, edit, delete, invalid money/text, errors, and cache refresh.

Acceptance:

- A newly created entry immediately appears in Waiting.
- Edit changes only allowed core fields; deletion removes the entry and returns to a valid route.
- UI never sends decimals/floats or assumes that hiding an action enforces authorization.

## Design Traceability

- `implementation/1-database-implementation-plan.md`: entry constraints and dashboard query design.
- `implementation/2-frontend-implementation-plan.md`: dashboard composition and create/edit/delete flows.
- `implementation/3-backend-implementation-plan.md`: entry service, ownership, response mapping, transactions.
