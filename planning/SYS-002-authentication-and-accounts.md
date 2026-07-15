# SYS-002: Authentication and Accounts

This step defines the simplest account system that still protects user data correctly.

## Auth Model

Users authenticate with:

- Email
- Password

The backend manages sessions using HTTP-only cookies.

## Auth Flow

1. User signs up with email and password.
2. Backend validates the email and password.
3. Backend hashes the password.
4. Backend creates the user.
5. Backend creates a session.
6. Backend sets an HTTP-only session cookie.
7. Frontend treats the user as logged in.

Login follows the same session creation path after password verification.

Logout deletes the active session and clears the cookie.

## Why Cookie Sessions

Cookie sessions are the preferred v1 approach because they are simple and easy to invalidate.

The frontend should not store auth tokens in local storage. The browser sends the session cookie automatically with API requests.

## User Table

```text
users
- id
- email
- password_hash
- created_at
- updated_at
```

Rules:

- Email must be unique.
- Email should be normalized before storage.
- Password must never be stored directly.
- Password hashes should use bcrypt or argon2.

## Session Table

```text
sessions
- id
- user_id
- session_token_hash
- expires_at
- created_at
- last_used_at
```

Rules:

- Store only the hashed session token.
- Send only the raw session token to the browser cookie.
- Reject expired sessions.
- Delete the session on logout.
- Every protected API request must resolve the current user from the session.

## Auth API

```text
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

## Signup Request

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

## Auth Response

```json
{
  "user": {
    "id": "user_id",
    "email": "user@example.com"
  }
}
```

## Backend Auth Rules

- Reject duplicate signup emails.
- Reject invalid login credentials.
- Do not reveal whether email or password was wrong during login.
- Require a valid session for all non-auth app endpoints.
- Scope every query by the authenticated user's id.

## Frontend Auth Rules

- Use `/api/auth/me` to restore logged-in state after refresh.
- Redirect unauthenticated users away from protected screens.
- Redirect authenticated users away from login/signup screens when appropriate.
- Show validation errors from the backend without exposing sensitive details.

