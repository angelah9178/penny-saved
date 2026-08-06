import { z } from "zod";

import {
  formatCentsForEntryForm,
  parseDollarsToCents,
} from "../entries/entryFormValidation";

const MAX_LABEL_LENGTH = 120;
const MAX_UNIT_NAME_LENGTH = 80;

const requiredTrimmedText = (fieldName: string, maximumLength: number) =>
  z.string().transform((value, context) => {
    const trimmed = value.trim();

    if (Array.from(trimmed).length === 0) {
      context.addIssue({ code: "custom", message: `Enter ${fieldName}.` });
      return z.NEVER;
    }

    if (Array.from(trimmed).length > maximumLength) {
      context.addIssue({
        code: "custom",
        message: `${capitalize(fieldName)} must be ${maximumLength} characters or fewer.`,
      });
      return z.NEVER;
    }

    return trimmed;
  });

export const opportunityCostFormSchema = z.object({
  label: requiredTrimmedText("a label", MAX_LABEL_LENGTH),
  unit_name: requiredTrimmedText("a unit name", MAX_UNIT_NAME_LENGTH),
  dollar_value: z.string().transform((value, context) => {
    try {
      return parseDollarsToCents(value);
    } catch (error) {
      context.addIssue({
        code: "custom",
        message:
          error instanceof Error
            ? opportunityCostMoneyMessage(error.message)
            : "Enter a valid dollar value.",
      });
      return z.NEVER;
    }
  }),
});

export type OpportunityCostFormValues = {
  label: string;
  unit_name: string;
  dollar_value: string;
};

export const EMPTY_OPPORTUNITY_COST_FORM_VALUES: OpportunityCostFormValues = {
  label: "",
  unit_name: "",
  dollar_value: "",
};

export function formatCentsForOpportunityCostForm(cents: number): string {
  return formatCentsForEntryForm(cents);
}

function opportunityCostMoneyMessage(message: string): string {
  return message
    .replace("a price", "a dollar value")
    .replace("Price", "Dollar value");
}

function capitalize(value: string): string {
  return `${value.charAt(0).toUpperCase()}${value.slice(1)}`;
}
