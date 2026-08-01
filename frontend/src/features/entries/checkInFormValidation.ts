import { z } from "zod";

import type { CheckInResult } from "../../types/api";

export const MAX_CHECK_IN_COMMENT_LENGTH = 4_000;

export type CheckInFormValues = {
  result: CheckInResult | "";
  comment: string;
};

export const checkInFormSchema = z.object({
  result: z.string().transform((value, context): CheckInResult => {
    if (value !== "saved" && value !== "purchased") {
      context.addIssue({
        code: "custom",
        message: "Choose what happened with this purchase.",
      });
      return z.NEVER;
    }
    return value;
  }),
  comment: z.string().transform((value, context) => {
    const trimmed = value.trim();
    if (Array.from(trimmed).length > MAX_CHECK_IN_COMMENT_LENGTH) {
      context.addIssue({
        code: "custom",
        message: "Comment must be 4,000 characters or fewer.",
      });
      return z.NEVER;
    }
    return trimmed.length === 0 ? null : trimmed;
  }),
});
