import type { Locale } from "@/contexts/I18nContext";

const tag = (l: Locale) => (l === "ru" ? "ru-RU" : "en-GB");

/** Parse "YYYY-MM-DD" as a local date (not UTC midnight). */
export function parseDate(value: string): Date {
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(y, m - 1, d);
  }
  return new Date(value);
}

export function fmtDate(value: string | null | undefined, l: Locale, opts?: Intl.DateTimeFormatOptions) {
  if (!value) return "—";
  return parseDate(value).toLocaleDateString(tag(l), opts ?? { day: "numeric", month: "short", year: "numeric" });
}

export function fmtShortDate(value: string | null | undefined, l: Locale) {
  return fmtDate(value, l, { day: "numeric", month: "short" });
}

export function fmtDateTime(value: string | null | undefined, l: Locale) {
  if (!value) return "—";
  return new Date(value).toLocaleString(tag(l), {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtTime(value: string, l: Locale) {
  return new Date(value).toLocaleTimeString(tag(l), { hour: "2-digit", minute: "2-digit" });
}

export function fmtWeekday(value: string, l: Locale) {
  return new Date(value).toLocaleDateString(tag(l), { weekday: "short", day: "numeric", month: "short" });
}

export function fmtRelative(value: string, l: Locale) {
  const diff = (new Date(value).getTime() - Date.now()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(tag(l), { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  if (abs < 86400 * 30) return rtf.format(Math.round(diff / 86400), "day");
  return fmtDate(value, l);
}

export function fmtSize(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** yyyy-mm-dd for <input type=date> in local time */
export function toDateInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

/** yyyy-mm-ddThh:mm for <input type=datetime-local> */
export function toDateTimeInput(d: Date) {
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${toDateInput(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** datetime-local value (local) -> ISO string with timezone */
export function localInputToIso(v: string | null | undefined) {
  if (!v) return null;
  return new Date(v).toISOString();
}

export function addDays(d: Date, n: number) {
  const r = new Date(d);
  r.setDate(r.getDate() + n);
  return r;
}

export function generatePassword() {
  const letters = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ";
  const digits = "23456789";
  const all = letters + digits;
  const rnd = (s: string) => s[crypto.getRandomValues(new Uint32Array(1))[0] % s.length];
  const base = Array.from({ length: 8 }, () => rnd(all)).join("");
  return rnd(letters) + base + rnd(digits);
}
