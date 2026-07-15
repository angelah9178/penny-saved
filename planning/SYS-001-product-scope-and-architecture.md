# SYS-001: Product Scope and Architecture

This step defines what A Penny Saved is, what it is not, and how the system should be shaped for the first implementation.

## Product Boundary

A Penny Saved is a delayed-decision web app for impulse purchases. A user records something they want to buy, waits 48 hours, and then checks in to confirm whether they bought it.

The app tracks:

- Items the user is waiting on
- Items ready for check-in
- Items the user avoided buying
- Items the user bought
- Total confirmed money saved
- Avoided purchase count
- Opportunity cost comparisons

## V1 In Scope

- Email/password signup and login
- Responsive dashboard
- Add impulse purchase entry
- View Waiting entries
- View Needs check-in entries
- Complete manual check-in after 48 hours
- Move entries to Saved or Purchased
- Edit Waiting item details
- Delete Waiting entries
- Edit comments on Saved and Purchased entries
- View hidden/collapsible Purchased section
- Create and manage opportunity cost examples
- Filter savings statistics by time range

## V1 Out of Scope

- Bank account integrations
- Payment processing
- Automatic purchase detection
- Shared accounts
- Social features
- Native mobile apps
- Browser extensions
- Recurring budget management
- Admin dashboard

## Technical Stack

Frontend:

- TypeScript
- React
- Vite
- React Router
- TanStack Query
- npm

Backend:

- Python
- FastAPI
- SQLAlchemy
- Alembic
- Pydantic
- pip
- Ruff
- Pytest

Database:

- PostgreSQL

## High-Level Architecture

```text
React + TypeScript frontend
        |
        | HTTP API with cookie session
        v
FastAPI backend
        |
        v
PostgreSQL database
```

## Frontend Responsibilities

- Render screens and routes
- Display dashboard sections
- Handle forms and field-level feedback
- Call backend APIs
- Refresh data after mutations
- Keep the app responsive across screen sizes

## Backend Responsibilities

- Authenticate users
- Manage sessions
- Enforce user ownership
- Validate requests
- Apply entry lifecycle rules
- Derive Needs check-in state
- Calculate statistics
- Calculate opportunity cost equivalents
- Return frontend-ready API responses

## Database Responsibilities

- Persist users
- Persist sessions
- Persist impulse purchase entries
- Persist opportunity cost examples
- Maintain relational integrity
- Support filtered statistics queries

## Key Architecture Decision

Needs check-in should be a derived dashboard bucket, not a stored status.

```text
needs_check_in = status == "waiting" and created_at <= now - 48 hours
```

The stored status values should remain simple:

- `waiting`
- `saved`
- `purchased`
