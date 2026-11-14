import type { Locale } from "@/contexts/I18nContext";

const tag = (l: Locale) => (l === "ru" ? "ru-RU" : "en-GB");

/* ---------- display time zone ----------
 * Instants (ISO strings with an offset) are shown in the user's profile time
 * zone (users.timezone), not in whatever zone the browser happens to be in.
 * Calendar dates ("YYYY-MM-DD", e.g. subscription dates) have no zone. */
let displayTimeZone: string | undefined;

export function browserTimeZone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function setDisplayTimeZone(tz: string | null | undefined) {
  displayTimeZone = tz || undefined;
}

export function getDisplayTimeZone(): string {
  return displayTimeZone ?? browserTimeZone();
}

const DATE_ONLY = /^\d{4}-\d{2}-\d{2}$/;

/** "YYYY-MM-DD" as UTC midnight (formatted with timeZone UTC, so the day never shifts). */
export function parseDate(value: string): Date {
  if (DATE_ONLY.test(value)) {
    const [y, m, d] = value.split("-").map(Number);
    return new Date(Date.UTC(y, m - 1, d));
  }
  return new Date(value);
}

const zoneFor = (value: string) => (DATE_ONLY.test(value) ? "UTC" : getDisplayTimeZone());

export function fmtDate(value: string | null | undefined, l: Locale, opts?: Intl.DateTimeFormatOptions) {
  if (!value) return "—";
  return parseDate(value).toLocaleDateString(tag(l), {
    ...(opts ?? { day: "numeric", month: "short", year: "numeric" }),
    timeZone: zoneFor(value),
  });
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
    timeZone: getDisplayTimeZone(),
  });
}

export function fmtTime(value: string, l: Locale) {
  return new Date(value).toLocaleTimeString(tag(l), { hour: "2-digit", minute: "2-digit", timeZone: getDisplayTimeZone() });
}

export function fmtWeekday(value: string, l: Locale) {
  return new Date(value).toLocaleDateString(tag(l), {
    weekday: "short",
    day: "numeric",
    month: "short",
    timeZone: getDisplayTimeZone(),
  });
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

/* ---------- wall-clock conversions in the display time zone ---------- */

interface WallClock {
  year: number;
  month: number; // 1-12
  day: number;
  hour: number;
  minute: number;
}

/** Wall-clock parts of an instant in `tz`. */
export function wallClock(d: Date, tz = getDisplayTimeZone()): WallClock {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: tz,
    hourCycle: "h23",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).formatToParts(d);
  const get = (t: string) => Number(parts.find((p) => p.type === t)?.value);
  return { year: get("year"), month: get("month"), day: get("day"), hour: get("hour") % 24, minute: get("minute") };
}

/** UTC instant for a wall-clock time in `tz` (DST-aware, two-pass offset fix). */
export function fromWallClock(w: WallClock, tz = getDisplayTimeZone()): Date {
  const asUtc = Date.UTC(w.year, w.month - 1, w.day, w.hour, w.minute);
  const offsetAt = (ms: number) => {
    const p = wallClock(new Date(ms), tz);
    return Date.UTC(p.year, p.month - 1, p.day, p.hour, p.minute) - ms;
  };
  let guess = asUtc - offsetAt(asUtc);
  guess = asUtc - offsetAt(guess);
  return new Date(guess);
}

const pad = (n: number) => String(n).padStart(2, "0");

/** Calendar day key "YYYY-MM-DD" of an instant in the display time zone. */
export function dayKey(d: Date | string, tz = getDisplayTimeZone()) {
  const w = wallClock(typeof d === "string" ? new Date(d) : d, tz);
  return `${w.year}-${pad(w.month)}-${pad(w.day)}`;
}

/** yyyy-mm-dd for <input type=date>: today's (or `d`'s) date in the display time zone */
export function toDateInput(d: Date) {
  return dayKey(d);
}

/** yyyy-mm-ddThh:mm for <input type=datetime-local>, in the display time zone */
export function toDateTimeInput(d: Date) {
  const w = wallClock(d);
  return `${w.year}-${pad(w.month)}-${pad(w.day)}T${pad(w.hour)}:${pad(w.minute)}`;
}

/** datetime-local value (wall clock in the display time zone) -> ISO instant */
export function localInputToIso(v: string | null | undefined) {
  if (!v) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})/.exec(v);
  if (!m) return new Date(v).toISOString();
  const [, y, mo, d, h, mi] = m.map(Number);
  return fromWallClock({ year: y, month: mo, day: d, hour: h, minute: mi }).toISOString();
}

/** datetime-local value for "N days from today at hh:mm" in the display time zone */
export function wallClockInput(daysFromToday: number, hour: number, minute = 0) {
  const today = wallClock(new Date());
  const base = new Date(Date.UTC(today.year, today.month - 1, today.day + daysFromToday));
  return `${base.getUTCFullYear()}-${pad(base.getUTCMonth() + 1)}-${pad(base.getUTCDate())}T${pad(hour)}:${pad(minute)}`;
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
