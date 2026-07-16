# SYS-000: System Design Guide

This guide defines the implementation design sequence for A Penny Saved. The design is based on the client request and the functional/screen flowcharts.

## Product Summary

A Penny Saved is a responsive web app that helps users avoid impulse purchases by making them wait 48 hours before deciding whether to buy. Users add impulse purchase entries, return after the waiting period, complete a manual check-in, and see how much money they saved by not buying.

The app uses:

- TypeScript frontend
- Python backend
- Email/password authentication
- Server-managed sessions
- Relational database storage

## Design Principles

- Keep the first version simple and focused.
- Treat the app as a delayed-decision tracker, not a full finance platform.
- Store durable facts in the database and derive temporary dashboard categories from those facts.
- Enforce all important lifecycle and ownership rules in the backend.
- Keep frontend state synchronized with backend API responses.

## System Design Steps

1. Define product scope and architecture.
   - Document the v1 boundary.
   - Choose the frontend/backend/database shape.
   - Identify responsibilities for each layer.

2. Define authentication and account design.
   - Support email/password signup and login.
   - Store hashed passwords only.
   - Use HTTP-only cookie sessions.
   - Scope all app data to the current user.

3. Define impulse purchase entry lifecycle.
   - Create Waiting entries.
   - Derive Needs check-in after 48 hours.
   - Move entries to Saved or Purchased after check-in.
   - Limit edits and deletes based on status.

4. Define data and API contracts.
   - Model users, sessions, impulse purchase entries, and opportunity cost examples.
   - Define request and response payloads.
   - Define validation and error behavior.

5. Define dashboard, statistics, and opportunity cost calculations.
   - Group entries for the dashboard.
   - Calculate total saved.
   - Support time filters.
   - Convert saved money into user-defined comparison units.

6. Define development tools and implementation roadmap.
   - Establish project structure.
   - Define Makefile commands.
   - Identify build phases.
   - Define testing expectations.

## Planned SYS Documents

- `SYS-001`: Product scope and architecture
- `SYS-002`: Authentication and accounts
- `SYS-003`: Entry lifecycle and business rules
- `SYS-004`: Data and API contracts
- `SYS-005`: Dashboard, statistics, and opportunity cost
- `SYS-006`: Development tools and implementation roadmap

## Source Planning Documents

- `planning/0-client-request.md`
- `planning/FLOW-001-functional-flowcharts.md`
- `planning/FLOW-002-screen-flowcharts.md`

