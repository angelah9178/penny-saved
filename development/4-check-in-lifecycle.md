# Check-in Lifecycle Development

## Category Tracker

| ID | Outcome | Depends on | Status | PR |
|---|---|---|---|---|
| DEV-013 | Eligible entries transition atomically exactly once | DEV-010 | Not started | — |
| DEV-014 | User can resolve an eligible entry as saved or purchased | DEV-011, DEV-013 | Not started | — |
| DEV-015 | User can edit comments on resolved entries | DEV-013, DEV-014 | Not started | — |

## DEV-013 — Implement atomic entry check-in API

Scope:

- Add the check-in request/response schemas, service operation, repository row lock, and route.
- Select the owned entry `FOR UPDATE`, then recheck waiting status and `created_at + 48 hours` eligibility.
- At eligibility, set only status, normalized optional comment, `checked_in_at`, and `updated_at` using one injected clock.
- Return stable `early_check_in`, invalid status, ownership, validation, and unexpected error responses.
- Add PostgreSQL-backed service/API tests at one microsecond before and exactly at the boundary, plus concurrent requests.

Acceptance:

- Exactly `now == eligible_at` succeeds; any earlier request fails without mutation.
- Concurrent check-ins yield one success and one conflict, never two transitions.
- Statistics timestamps originate from `checked_in_at`, not creation time.

## DEV-014 — Build the check-in experience

Scope:

- Build the eligible-entry check-in route showing the original decision context and saved/purchased choices.
- Collect an optional normalized comment and require an explicit resolution action.
- Handle early/stale status conflicts, expired auth, request failure, and duplicate submission.
- Refresh dashboard/detail/statistics-related query keys after success and show the correct confirmation state.
- Add tests for both outcomes, optional comment, boundary conflicts, navigation, and cache effects.

Acceptance:

- Saved and purchased submissions use the same API contract and result in the proper dashboard bucket.
- Confirmation is accessible and cannot accidentally submit twice.
- The frontend relies on server eligibility and handles clock disagreement gracefully.

## DEV-015 — Add resolved-entry comment editing

Scope:

- Add the backend comment-only mutation route/service with ownership, row locking, normalization, and status checks.
- Build comment editing for saved and purchased details; do not expose core-field edits.
- Support clearing to `null` if allowed by the API normalization contract.
- Refresh affected dashboard/detail data and test waiting-entry rejection, ownership, empty normalization, and failures.

Acceptance:

- Resolved entries can change only `comment` and `updated_at`.
- Waiting entries receive the documented lifecycle conflict.
- Updated comments appear without a page reload.

## Design Traceability

- `implementation/0-implementation-plan.md`: 48-hour invariant and Phase 4 gate.
- `implementation/1-database-implementation-plan.md`: atomic check-in and lifecycle constraints.
- `implementation/2-frontend-implementation-plan.md`: check-in and comment flows.
- `implementation/3-backend-implementation-plan.md`: check-in/comment services and concurrency.
