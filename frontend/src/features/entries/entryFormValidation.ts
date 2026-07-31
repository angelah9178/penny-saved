import { z } from "zod";

const MAX_ITEM_NAME_LENGTH = 200;
const MAX_REASON_WANTED_LENGTH = 2_000;
const MAX_PRICE_CENTS = 999_999_999_999;
const PRICE_PATTERN = /^(?:0|[1-9]\d*)(?:\.\d{1,2})?$/u;

const requiredTrimmedText = (fieldName: string, maximumLength: number) =>
  z.string().transform((value, context) => {
    const trimmed = value.trim();
    const length = Array.from(trimmed).length;

    if (length === 0) {
      context.addIssue({
        code: "custom",
        message: `Enter ${fieldName}.`,
      });
      return z.NEVER;
    }

    if (length > maximumLength) {
      context.addIssue({
        code: "custom",
        message: `${capitalize(fieldName)} must be ${maximumLength.toLocaleString("en-US")} characters or fewer.`,
      });
      return z.NEVER;
    }

    return trimmed;
  });

export const entryFormSchema = z.object({
  item_name: requiredTrimmedText("an item name", MAX_ITEM_NAME_LENGTH),
  price: z.string().transform((value, context) => {
    try {
      return parseDollarsToCents(value);
    } catch (error) {
      context.addIssue({
        code: "custom",
        message:
          error instanceof Error ? error.message : "Enter a valid price.",
      });
      return z.NEVER;
    }
  }),
  reason_wanted: requiredTrimmedText(
    "a reason for wanting it",
    MAX_REASON_WANTED_LENGTH,
  ),
});

export type EntryFormValues = {
  item_name: string;
  price: string;
  reason_wanted: string;
};

export function parseDollarsToCents(value: string): number {
  const price = value.trim();
  if (!PRICE_PATTERN.test(price)) {
    throw new Error(
      "Enter a price in dollars with no more than two decimal places.",
    );
  }

  const [dollars = "0", cents = ""] = price.split(".");
  const priceCents = Number(`${dollars}${cents.padEnd(2, "0")}`);

  if (priceCents < 1) {
    throw new Error("Price must be at least $0.01.");
  }
  if (priceCents > MAX_PRICE_CENTS) {
    throw new Error("Price must be $9,999,999,999.99 or less.");
  }

  return priceCents;
}

export function formatCentsForEntryForm(priceCents: number): string {
  if (!Number.isSafeInteger(priceCents) || priceCents < 0) {
    throw new Error("Price cents must be a non-negative safe integer.");
  }

  const dollars = Math.floor(priceCents / 100);
  const cents = String(priceCents % 100).padStart(2, "0");
  return `${dollars}.${cents}`;
}

function capitalize(value: string): string {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}
