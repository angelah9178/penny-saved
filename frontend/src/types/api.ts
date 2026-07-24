/**
 * Shared JSON contracts between the React frontend and FastAPI backend.
 *
 * These types intentionally preserve the API's snake_case field names. Money crosses
 * the API boundary as integer cents, and timestamps cross it as UTC RFC 3339 strings.
 */

export type User = {
  id: string;
  email: string;
};

export type AuthRequest = {
  email: string;
  password: string;
};

export type AuthResponse = {
  user: User;
};

export type EntryStatus = "waiting" | "saved" | "purchased";

export type DashboardBucket =
  | "needs_check_in"
  | "waiting"
  | "saved"
  | "purchased";

export type Entry = {
  id: string;
  item_name: string;
  price_cents: number;
  reason_wanted: string;
  status: EntryStatus;
  dashboard_bucket: DashboardBucket;
  comment: string | null;
  created_at: string;
  eligible_for_check_in_at: string;
  checked_in_at: string | null;
  updated_at: string;
};

export type DashboardEntries = {
  needs_check_in: Entry[];
  waiting: Entry[];
  saved: Entry[];
  purchased: Entry[];
};

export type EntryResponse = {
  entry: Entry;
};

export type CreateEntryRequest = {
  item_name: string;
  price_cents: number;
  reason_wanted: string;
};

export type UpdateEntryRequest = CreateEntryRequest;

export type CheckInResult = Extract<EntryStatus, "saved" | "purchased">;

export type CheckInEntryRequest = {
  result: CheckInResult;
  comment: string | null;
};

export type UpdateEntryCommentRequest = {
  comment: string | null;
};

export type StatsRange =
  | "this_month"
  | "last_3_months"
  | "last_6_months"
  | "last_year"
  | "all_time";

export type OpportunityCostEquivalent = {
  example_id: string;
  label: string;
  unit_name: string;
  dollar_value_cents: number;
  equivalent_units: number;
};

export type StatsSummary = {
  range: StatsRange;
  total_saved_cents: number;
  avoided_purchase_count: number;
  purchased_count: number;
  opportunity_costs: OpportunityCostEquivalent[];
};

export type OpportunityCostExample = {
  id: string;
  label: string;
  unit_name: string;
  dollar_value_cents: number;
  created_at: string;
  updated_at: string;
};

export type OpportunityCostExamplesResponse = {
  examples: OpportunityCostExample[];
};

export type OpportunityCostExampleResponse = {
  example: OpportunityCostExample;
};

export type CreateOpportunityCostExampleRequest = {
  label: string;
  unit_name: string;
  dollar_value_cents: number;
};

export type UpdateOpportunityCostExampleRequest =
  CreateOpportunityCostExampleRequest;

export type ApiErrorDetail = {
  code: string;
  message: string;
  fields?: Record<string, string>;
};

export type ApiErrorResponse = {
  error: ApiErrorDetail;
};
