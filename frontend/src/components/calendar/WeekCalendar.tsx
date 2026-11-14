import { CalendarDays, ChevronLeft, ChevronRight, Video } from "lucide-react";
import { useMemo, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { dayKey, fmtTime } from "@/utils/format";

export type CalendarTone = "scheduled" | "completed" | "cancelled" | "present" | "late" | "absent" | "excused";

export interface CalendarEvent {
  id: number;
  title: string;
  subtitle?: string | null;
  startsAt: string;
  durationMinutes: number;
  tone: CalendarTone;
  meetingUrl?: string | null;
  badge?: ReactNode;
}

const TONES: Record<CalendarTone, string> = {
  scheduled: "border-l-accent bg-accent-soft/60",
  completed: "border-l-success bg-success-soft/70",
  present: "border-l-success bg-success-soft/70",
  late: "border-l-warning bg-warning-soft/70",
  absent: "border-l-danger bg-danger-soft/70",
  excused: "border-l-muted-foreground/40 bg-secondary",
  cancelled: "border-l-muted-foreground/30 bg-secondary opacity-60 line-through decoration-muted-foreground/50",
};

/* Week keys are calendar dates ("YYYY-MM-DD"); arithmetic is done on UTC dates so
   it never depends on the browser's own time zone. */
const toUtc = (key: string) => {
  const [y, m, d] = key.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d));
};
const toKey = (d: Date) => d.toISOString().slice(0, 10);

export function shiftDays(key: string, days: number) {
  const d = toUtc(key);
  d.setUTCDate(d.getUTCDate() + days);
  return toKey(d);
}

/** Monday of the week that contains `key`. */
export function mondayOf(key: string) {
  const weekday = (toUtc(key).getUTCDay() + 6) % 7; // Monday = 0
  return shiftDays(key, -weekday);
}

export function currentMonday() {
  return mondayOf(dayKey(new Date()));
}

interface Props {
  weekStart: string; // Monday, "YYYY-MM-DD" in the display time zone
  onWeekChange: (monday: string) => void;
  events: CalendarEvent[];
  loading?: boolean;
  onEventClick?: (id: number) => void;
}

export function WeekCalendar({ weekStart, onWeekChange, events, loading, onEventClick }: Props) {
  const { t, locale } = useI18n();
  const tag = locale === "ru" ? "ru-RU" : "en-GB";
  const today = dayKey(new Date());
  const days = useMemo(() => Array.from({ length: 7 }, (_, i) => shiftDays(weekStart, i)), [weekStart]);

  const byDay = useMemo(() => {
    const map: Record<string, CalendarEvent[]> = {};
    for (const e of events) (map[dayKey(e.startsAt)] ??= []).push(e);
    Object.values(map).forEach((list) => list.sort((a, b) => a.startsAt.localeCompare(b.startsAt)));
    return map;
  }, [events]);

  const fmtDay = (key: string, opts: Intl.DateTimeFormatOptions) =>
    toUtc(key).toLocaleDateString(tag, { ...opts, timeZone: "UTC" });
  const range = `${fmtDay(days[0], { day: "numeric", month: "short" })} — ${fmtDay(days[6], { day: "numeric", month: "short", year: "numeric" })}`;
  const inWeek = events.some((e) => days.includes(dayKey(e.startsAt)));

  const eventCard = (e: CalendarEvent) => {
    const end = new Date(new Date(e.startsAt).getTime() + e.durationMinutes * 60000).toISOString();
    const body = (
      <>
        <p className="tabular text-xs font-semibold text-primary">
          {fmtTime(e.startsAt, locale)}–{fmtTime(end, locale)}
        </p>
        <p className="mt-0.5 line-clamp-2 break-words text-sm font-medium text-primary">{e.title}</p>
        {e.subtitle && <p className="mt-0.5 line-clamp-2 break-words text-xs text-muted-foreground">{e.subtitle}</p>}
        {(e.badge || e.meetingUrl) && (
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            {e.badge}
            {e.meetingUrl && e.tone === "scheduled" && (
              <a
                href={e.meetingUrl}
                target="_blank"
                rel="noreferrer noopener"
                onClick={(ev) => ev.stopPropagation()}
                className="inline-flex items-center gap-1 text-xs font-medium text-accent hover:underline"
              >
                <Video className="size-3.5" />
                {t.dashboard.join}
              </a>
            )}
          </div>
        )}
      </>
    );
    const cls = cn("block w-full rounded-lg border-l-[3px] px-2.5 py-2 text-left transition-shadow", TONES[e.tone]);
    return onEventClick ? (
      <button key={e.id} type="button" onClick={() => onEventClick(e.id)} className={cn(cls, "hover:shadow-soft")}>
        {body}
      </button>
    ) : (
      <div key={e.id} className={cls}>
        {body}
      </div>
    );
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon-sm" aria-label={t.calendar.prevWeek} onClick={() => onWeekChange(shiftDays(weekStart, -7))}>
            <ChevronLeft />
          </Button>
          <Button variant="outline" size="icon-sm" aria-label={t.calendar.nextWeek} onClick={() => onWeekChange(shiftDays(weekStart, 7))}>
            <ChevronRight />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => onWeekChange(currentMonday())} disabled={weekStart === currentMonday()}>
            {t.calendar.today}
          </Button>
        </div>
        <p className="tabular text-sm font-semibold text-primary">{range}</p>
      </div>

      {/* Desktop: 7 columns */}
      <div className="hidden grid-cols-7 gap-2 md:grid">
        {days.map((d) => (
          <Card key={d} className={cn("flex min-h-[220px] flex-col p-2", d === today && "ring-2 ring-accent/40")}>
            <div className="mb-2 px-1">
              <p className={cn("text-xs font-medium uppercase", d === today ? "text-accent" : "text-muted-foreground")}>
                {fmtDay(d, { weekday: "short" })}
              </p>
              <p className={cn("tabular text-lg font-semibold", d === today ? "text-accent" : "text-primary")}>
                {fmtDay(d, { day: "numeric" })}
              </p>
            </div>
            <div className="grid gap-1.5">
              {loading ? <Skeleton className="h-14" /> : (byDay[d] ?? []).map(eventCard)}
            </div>
          </Card>
        ))}
      </div>

      {/* Mobile: one list, days in order */}
      <div className="grid gap-3 md:hidden">
        {loading ? (
          <Skeleton className="h-32" />
        ) : (
          days.map((d) => {
            const list = byDay[d] ?? [];
            if (!list.length && d !== today) return null;
            return (
              <Card key={d} className={cn("p-3", d === today && "ring-2 ring-accent/40")}>
                <p className={cn("mb-2 text-sm font-semibold capitalize", d === today ? "text-accent" : "text-primary")}>
                  {fmtDay(d, { weekday: "long", day: "numeric", month: "long" })}
                </p>
                {list.length ? <div className="grid gap-1.5">{list.map(eventCard)}</div> : (
                  <p className="text-sm text-muted-foreground">{t.calendar.noLessonsDay}</p>
                )}
              </Card>
            );
          })
        )}
      </div>

      {!loading && !inWeek && (
        <p className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground">
          <CalendarDays className="size-4" />
          {t.calendar.emptyWeek}
        </p>
      )}
    </div>
  );
}
