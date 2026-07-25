import { z } from "zod";

const MIN_EMAIL_LENGTH = 3;
const MAX_EMAIL_LENGTH = 320;
const MIN_PASSWORD_LENGTH = 8;
const MAX_PASSWORD_LENGTH = 128;

export const authFormSchema = z.object({
  email: z
    .string()
    .transform((email) => email.trim())
    .pipe(
      z
        .string()
        .min(MIN_EMAIL_LENGTH, "Enter your email address.")
        .max(MAX_EMAIL_LENGTH, "Email must be 320 characters or fewer.")
        .refine(isBasicEmail, "Enter a valid email address."),
    ),
  password: z.string().superRefine((password, context) => {
    const length = Array.from(password).length;
    if (length < MIN_PASSWORD_LENGTH) {
      context.addIssue({
        code: "custom",
        message: "Password must be at least 8 characters.",
      });
    } else if (length > MAX_PASSWORD_LENGTH) {
      context.addIssue({
        code: "custom",
        message: "Password must be 128 characters or fewer.",
      });
    }
  }),
});

export type AuthFormValues = {
  email: string;
  password: string;
};

function isBasicEmail(email: string): boolean {
  if (Array.from(email).some((character) => /\s/u.test(character))) {
    return false;
  }

  const parts = email.split("@");
  return (
    parts.length === 2 &&
    parts[0] !== undefined &&
    parts[0].length > 0 &&
    parts[1] !== undefined &&
    parts[1].length > 0
  );
}
