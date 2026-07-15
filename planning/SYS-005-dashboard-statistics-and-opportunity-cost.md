# SYS-005: Dashboard, Statistics, and Opportunity Cost

This step defines how the dashboard presents entries and calculated savings.

## Dashboard Sections

The dashboard has four sections:

- Needs check-in
- Waiting
- Saved
- Purchased

Purchased should be hidden or collapsed by default and manually opened at the bottom of the page.

## Dashboard Grouping

The backend should return entries grouped into dashboard sections so the frontend does not duplicate business rules.

Grouping rules:

```text
Needs check-in:
status == waiting and created_at <= now - 48 hours

Waiting:
status == waiting and created_at > now - 48 hours

Saved:
status == saved

Purchased:
status == purchased
```

## Statistics

The dashboard shows:

- Total amount saved
- Avoided impulse purchase count
- Purchased count
- Opportunity cost equivalents

## Total Saved

Total saved includes only confirmed Saved entries.

```text
sum(price_cents) where status == saved
```

Purchased entries do not count toward total saved.

## Avoided Purchase Count

Avoided purchase count includes only Saved entries.

```text
count(entries) where status == saved
```

## Purchased Count

Purchased count includes only Purchased entries.

```text
count(entries) where status == purchased
```

## Time Filters

Supported filters:

- This month
- Last 3 months
- Last 6 months
- Last year
- All-time

Filter values:

```text
this_month
last_3_months
last_6_months
last_year
all_time
```

The date filter should use `checked_in_at`, because savings are only confirmed after check-in.

## Stats Response

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

## Opportunity Cost Examples

Users can create examples with:

- Label
- Unit name
- Dollar value

Example:

```text
label: hours worked
unit_name: hours
dollar_value_cents: 1000
```

If the user has saved 25000 cents, the equivalent is:

```text
25000 / 1000 = 25 hours
```

## Opportunity Cost Table

```text
opportunity_cost_examples
- id
- user_id
- label
- unit_name
- dollar_value_cents
- created_at
- updated_at
```

## Calculation Rules

- Exclude examples with invalid or zero dollar values.
- Store money as cents.
- Calculate equivalent units from the filtered total saved.
- Return rounded display values in a consistent way.

Recommended rounding:

- Whole number when exact or near exact.
- One decimal place when fractional.
- Avoid excessive precision in user-facing displays.

## Frontend Display

The frontend can render opportunity cost messages such as:

```text
The amount you have saved is equal to 25 hours worked.
```

The frontend should not calculate the source saved amount. It should use the backend summary response.

