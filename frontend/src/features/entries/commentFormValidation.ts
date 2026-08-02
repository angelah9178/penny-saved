import { z } from "zod";

export const MAX_ENTRY_COMMENT_LENGTH = 4_000;

export const entryCommentSchema = z.string().transform((value, context) => {
  const trimmed = value.trim();
  if (Array.from(trimmed).length > MAX_ENTRY_COMMENT_LENGTH) {
    context.addIssue({
      code: "custom",
      message: "Comment must be 4,000 characters or fewer.",
    });
    return z.NEVER;
  }
  return trimmed.length === 0 ? null : trimmed;
});
