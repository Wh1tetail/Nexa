import { z } from "zod";

import type { Dict } from "@/i18n/ru";

/** Mirrors backend password rules (app/schemas/auth.py). */
export const passwordSchema = (t: Dict) =>
  z
    .string()
    .min(8, t.auth.passwordMin)
    .max(128)
    .refine((v) => /\d/.test(v) && /[A-Za-zА-Яа-яЁё]/.test(v), t.auth.passwordLetterDigit);

export const optionalText = z
  .string()
  .trim()
  .transform((v) => (v === "" ? null : v))
  .nullable()
  .optional();
