# SYS-003: Entry Lifecycle and Business Rules

This step defines how impulse purchase entries move through the app.

## Entry Purpose

An impulse purchase entry records something the user wants to buy but agrees to wait on for 48 hours.

## Stored Statuses

```text
waiting
saved
purchased
```

## Derived Dashboard Buckets

The dashboard displays four sections:

- Needs check-in
- Waiting
- Saved
- Purchased

Needs check-in is derived from Waiting entries.

```text
status == "waiting" and created_at <= now - 48 hours
```

Waiting contains unresolved entries that are not yet old enough for check-in.

```text
status == "waiting" and created_at > now - 48 hours
```

## Entry Table

```text
impulse_purchase_entries
- id
- user_id
- item_name
- price_cents
- reason_wanted
- status
- comment
- created_at
- checked_in_at
- updated_at
```

## Create Entry

User provides:

- Item name
- Price
- Reason wanted

Backend sets:

- `status = waiting`
- `created_at = now`
- `checked_in_at = null`

## Edit Waiting Entry

Waiting entries can update:

- Item name
- Price
- Reason wanted

Saved and Purchased entries cannot update these fields.

Attempting to edit item details after check-in should return `409 Conflict`.

## Delete Waiting Entry

Only Waiting entries can be deleted.

Saved and Purchased entries should remain as historical records.

Attempting to delete an entry after check-in should return `409 Conflict`.

## Check-In Eligibility

An entry can be checked in only when:

```text
status == "waiting"
created_at <= now - 48 hours
```

Attempting check-in too early should return `409 Conflict`.

## Check-In Outcomes

If the user chooses `I did not buy it`:

- Set `status = saved`
- Save optional comment
- Set `checked_in_at = now`
- Include price in total saved
- Include entry in avoided purchase count

If the user chooses `I bought it`:

- Set `status = purchased`
- Save optional comment
- Set `checked_in_at = now`
- Exclude price from total saved
- Include entry in purchased count

## Comment Updates

Saved and Purchased entries can update comments.

Comment updates must not change:

- Status
- Price
- Reason wanted
- Created date
- Checked-in date
- Statistics meaning

## Ownership Rules

Every entry belongs to exactly one user. Users must not be able to read, update, delete, or check in another user's entries.

## Lifecycle Summary

```text
Create item
  -> waiting
  -> waiting but shown as needs_check_in after 48 hours
  -> saved or purchased after manual check-in
```

