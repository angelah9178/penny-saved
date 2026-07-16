# SYS-006: Development Tools and Roadmap

This step defines the project structure, developer commands, and implementation order.

## Proposed Project Structure

```text
frontend/
  package.json
  src/
    api/
    components/
    pages/
    routes/
    types/

backend/
  requirements.txt
  requirements-dev.txt
  app/
    api/
    auth/
    db/
    models/
    schemas/
    services/
  tests/
  alembic/

planning/
```

## Tooling Choices

Frontend:

- npm for package management and scripts
- TypeScript for application code
- Vite for local development and builds

Backend:

- pip for Python dependency installation
- Ruff for linting and formatting
- Pytest for backend tests
- Alembic for PostgreSQL migrations

Database:

- PostgreSQL for local development and production-like environments

## Backend Modules

```text
auth_service
- create_user
- verify_login
- create_session
- destroy_session
- get_current_user

entry_service
- create_entry
- list_dashboard_entries
- update_waiting_entry
- delete_waiting_entry
- check_in_entry
- update_entry_comment

stats_service
- get_summary
- calculate_total_saved
- calculate_opportunity_costs

opportunity_cost_service
- create_example
- list_examples
- update_example
- delete_example
```

## Makefile Commands

Recommended commands:

```text
make install
make dev
make frontend-dev
make backend-dev
make test
make frontend-test
make backend-test
make lint
make format
make db-upgrade
make db-downgrade
make db-revision
```

Command intent:

```text
make install        # install frontend dependencies with npm and backend dependencies with pip
make dev            # run frontend and backend dev servers
make frontend-dev   # run npm dev server
make backend-dev    # run FastAPI dev server
make test           # run frontend and backend tests
make frontend-test  # run npm test command
make backend-test   # run pytest
make lint           # run frontend lint and ruff check
make format         # run frontend format and ruff format
make db-upgrade     # run alembic upgrade head
make db-downgrade   # run alembic downgrade -1
make db-revision    # create a new alembic migration
```

## Implementation Phase 1: Project Foundation

- Create frontend app with TypeScript.
- Create backend app with FastAPI.
- Add npm frontend scripts.
- Add pip requirements files.
- Add Ruff configuration.
- Add Pytest configuration.
- Add PostgreSQL database configuration.
- Add shared Makefile commands.
- Add environment configuration.
- Add basic health check endpoint.

## Implementation Phase 2: Authentication

- Add user model.
- Add session model.
- Add password hashing.
- Add signup, login, logout, and me endpoints.
- Add frontend auth pages and protected routes.

## Implementation Phase 3: Entry Management

- Add impulse purchase entry model.
- Add create/list/detail/update/delete endpoints.
- Add derived dashboard bucket logic.
- Add dashboard sections in the frontend.

## Implementation Phase 4: Check-In Flow

- Add 48-hour eligibility enforcement.
- Add check-in endpoint.
- Add Saved and Purchased transitions.
- Add optional check-in comments.
- Add frontend check-in screen or modal.

## Implementation Phase 5: Statistics

- Add stats summary endpoint.
- Add time range filters.
- Add total saved calculation.
- Add avoided purchase and purchased counts.
- Add dashboard statistics UI.

## Implementation Phase 6: Opportunity Cost Examples

- Add opportunity cost example model.
- Add create/list/update/delete endpoints.
- Add opportunity cost calculations to stats summary.
- Add settings screen for managing examples.
- Add dashboard display for equivalents.

## Implementation Phase 7: Polish and Testing

- Add backend unit tests for lifecycle rules.
- Add API tests for auth and ownership.
- Add frontend form and routing tests.
- Add responsive layout checks.
- Add empty states and error states.

## Backend Test Priorities

- Passwords are hashed.
- Login creates a session.
- Logout invalidates a session.
- Users cannot access another user's records.
- Waiting entries can be edited and deleted.
- Saved/Purchased entries cannot edit item details.
- Check-in before 48 hours is rejected.
- Saved entries count toward total saved.
- Purchased entries do not count toward total saved.

## Frontend Test Priorities

- Unauthenticated users see auth screens.
- Authenticated users can reach the dashboard.
- Add item form validates required fields.
- Dashboard shows entries in the right sections.
- Check-in actions update the UI.
- Statistics filter changes summary data.
- Opportunity cost examples render from API data.
