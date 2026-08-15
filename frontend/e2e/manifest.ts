import { readFileSync } from "node:fs";
import path from "node:path";

type ManifestUser = {
  id: string | null;
  email: string;
};

export type E2EManifest = {
  version: number;
  run_id: string;
  signup_user: ManifestUser;
  journey_user: ManifestUser;
  eligible_item_name: string;
  check_in_comment: string;
  expected_saved_total_cents: number;
  expected_avoided_purchase_count: number;
  expected_purchased_count: number;
  whole_equivalent_label: string;
  whole_equivalent_units: number;
  fractional_equivalent_label: string;
  fractional_equivalent_units: number;
  signup_entry_item_name: string;
  signup_entry_price_cents: number;
  signup_entry_reason: string;
};

export function readE2EManifest(): E2EManifest {
  const manifestPath = process.env.E2E_MANIFEST_PATH;
  if (!manifestPath || !path.isAbsolute(manifestPath)) {
    throw new Error("E2E_MANIFEST_PATH must be an absolute path");
  }
  const parsed: unknown = JSON.parse(readFileSync(manifestPath, "utf8"));
  if (!isManifest(parsed)) throw new Error("E2E manifest has an invalid shape");
  return parsed;
}

export function readE2EPassword(): string {
  const password = process.env.E2E_PASSWORD;
  if (!password || password.length < 8) {
    throw new Error("E2E_PASSWORD must be an ephemeral valid password");
  }
  return password;
}

function isManifest(value: unknown): value is E2EManifest {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<E2EManifest>;
  return (
    candidate.version === 1 &&
    typeof candidate.run_id === "string" &&
    isUser(candidate.signup_user) &&
    isUser(candidate.journey_user) &&
    typeof candidate.eligible_item_name === "string" &&
    typeof candidate.check_in_comment === "string" &&
    typeof candidate.expected_saved_total_cents === "number" &&
    typeof candidate.expected_avoided_purchase_count === "number" &&
    typeof candidate.expected_purchased_count === "number" &&
    typeof candidate.whole_equivalent_label === "string" &&
    typeof candidate.whole_equivalent_units === "number" &&
    typeof candidate.fractional_equivalent_label === "string" &&
    typeof candidate.fractional_equivalent_units === "number" &&
    typeof candidate.signup_entry_item_name === "string" &&
    typeof candidate.signup_entry_price_cents === "number" &&
    typeof candidate.signup_entry_reason === "string"
  );
}

function isUser(value: unknown): value is ManifestUser {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<ManifestUser>;
  return (
    (typeof candidate.id === "string" || candidate.id === null) &&
    typeof candidate.email === "string"
  );
}
