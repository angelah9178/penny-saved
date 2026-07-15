# SYS-004: Data and API Contracts

This step defines the backend API and data contracts used by the TypeScript frontend.

## API Prefix

```text
/api
```

All app endpoints except signup, login, and logout require an authenticated session.

## Data Models

```text
users
sessions
impulse_purchase_entries
opportunity_cost_examples
```

## Common API Rules

- Use JSON request and response bodies.
- Use cents for money values.
- Use UTC ISO 8601 timestamps.
- Scope every query by authenticated user.
- Return frontend-ready derived fields when useful.
- Use consistent error responses.

## HTTP Status Codes

- `200 OK`: Successful read, update, login, logout, or check-in.
- `201 Created`: Successful signup, entry creation, or opportunity cost example creation.
- `204 No Content`: Successful delete when no response body is needed.
- `400 Bad Request`: Malformed request or unsupported enum value.
- `401 Unauthorized`: Missing, invalid, or expired session.
- `403 Forbidden`: Authenticated user tried to access another user's resource.
- `404 Not Found`: Resource does not exist for the current user.
- `409 Conflict`: Request violates lifecycle rules, such as early check-in or editing a checked-in entry.
- `422 Unprocessable Entity`: Field validation failed.

## Error Response

```json
{
  "error": {
    "code": "validation_error",
    "message": "Request validation failed."
  }
}
```

Common error codes:

```text
validation_error
unauthorized
forbidden
not_found
conflict
duplicate_email
invalid_credentials
early_check_in
invalid_entry_status
```

## Auth Endpoints

```text
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

## Entry Endpoints

```text
GET    /api/entries
POST   /api/entries
GET    /api/entries/{entry_id}
PATCH  /api/entries/{entry_id}
DELETE /api/entries/{entry_id}
POST   /api/entries/{entry_id}/check-in
PATCH  /api/entries/{entry_id}/comment
```

## Entry Response Shape

All entry endpoints that return an entry should use this shape:

```json
{
  "entry": {
    "id": "entry_id",
    "item_name": "New headphones",
    "price_cents": 8500,
    "reason_wanted": "I want better noise cancellation",
    "status": "waiting",
    "dashboard_bucket": "waiting",
    "comment": null,
    "created_at": "2026-07-15T12:00:00Z",
    "eligible_for_check_in_at": "2026-07-17T12:00:00Z",
    "checked_in_at": null,
    "updated_at": "2026-07-15T12:00:00Z"
  }
}
```

## Create Entry

Request:

```json
{
  "item_name": "New headphones",
  "price_cents": 8500,
  "reason_wanted": "I want better noise cancellation"
}
```

Response:

```json
{
  "entry": {
    "id": "entry_id",
    "item_name": "New headphones",
    "price_cents": 8500,
    "reason_wanted": "I want better noise cancellation",
    "status": "waiting",
    "dashboard_bucket": "waiting",
    "comment": null,
    "created_at": "2026-07-15T12:00:00Z",
    "eligible_for_check_in_at": "2026-07-17T12:00:00Z",
    "checked_in_at": null
  }
}
```

## List Entries

Response:

```json
{
  "needs_check_in": [],
  "waiting": [],
  "saved": [],
  "purchased": []
}
```

Each entry should include:

```json
{
  "id": "entry_id",
  "item_name": "New headphones",
  "price_cents": 8500,
  "reason_wanted": "I want better noise cancellation",
  "status": "waiting",
  "dashboard_bucket": "needs_check_in",
  "comment": null,
  "created_at": "2026-07-15T12:00:00Z",
  "eligible_for_check_in_at": "2026-07-17T12:00:00Z",
  "checked_in_at": null
}
```

Status:

- `200 OK`

## Update Waiting Entry

Request:

```json
{
  "item_name": "Updated item name",
  "price_cents": 9000,
  "reason_wanted": "Updated reason"
}
```

Rules:

- Allowed only when `status = waiting`.
- Return `409 Conflict` for Saved or Purchased entries.

Response: entry response shape.

## Check In Entry

Request:

```json
{
  "result": "saved",
  "comment": "I waited and realized I did not need it."
}
```

Allowed result values:

- `saved`
- `purchased`

Rules:

- Allowed only after 48 hours.
- Allowed only when `status = waiting`.
- Sets `checked_in_at`.
- Saves optional comment.
- Returns `409 Conflict` when the entry is less than 48 hours old.
- Returns `409 Conflict` when the entry is already Saved or Purchased.

Response: entry response shape.

## Update Comment

Request:

```json
{
  "comment": "Updated reflection."
}
```

Rules:

- Intended for Saved and Purchased entries.
- Does not affect statistics.
- Does not change item details.

Response: entry response shape.

## Delete Entry

Rules:

- Allowed only when `status = waiting`.
- Return `204 No Content` after successful delete.
- Return `409 Conflict` for Saved or Purchased entries.

## Stats Endpoint

```text
GET /api/stats/summary?range=this_month
```

Supported ranges:

```text
this_month
last_3_months
last_6_months
last_year
all_time
```

Response:

```json
{
  "range": "this_month",
  "total_saved_cents": 25000,
  "avoided_purchase_count": 4,
  "purchased_count": 1,
  "opportunity_costs": [
    {
      "example_id": "example_id",
      "label": "hours worked",
      "unit_name": "hours",
      "dollar_value_cents": 1000,
      "equivalent_units": 25
    }
  ]
}
```

## Opportunity Cost Endpoints

```text
GET    /api/opportunity-cost-examples
POST   /api/opportunity-cost-examples
PATCH  /api/opportunity-cost-examples/{example_id}
DELETE /api/opportunity-cost-examples/{example_id}
```

Create request:

```json
{
  "label": "hours worked",
  "unit_name": "hours",
  "dollar_value_cents": 1000
}
```

Response:

```json
{
  "example": {
    "id": "example_id",
    "label": "hours worked",
    "unit_name": "hours",
    "dollar_value_cents": 1000,
    "created_at": "2026-07-15T12:00:00Z",
    "updated_at": "2026-07-15T12:00:00Z"
  }
}
```

Validation:

- `label` is required.
- `unit_name` is required.
- `dollar_value_cents` must be greater than 0.

Delete response:

- `204 No Content`
