import { useQuery } from "@tanstack/react-query";
import { CalendarCheck, CalendarClock, CalendarX2, Percent } from "lucide-react";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader, SectionTitle, StatCard, StatsSkeleton } from "@/components/common";
import { AttendanceBadge, LessonBadge } from "@/components/common/StatusBadges";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { meApi } from "@/services/api";
import { fmtDate, fmtTime } from "@/utils/format";

export default function StudentAttendance() {
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["me", "attendance"], queryFn: meApi.attendance });

  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;
  const s = q.data?.stats;
  const now = Date.now();
  const lessons = q.data?.lessons ?? [];
  const upcoming = lessons.filter((l) => new Date(l.starts_at).getTime() > now && l.lesson_status === "scheduled").reverse();
  const past = lessons.filter((l) => !upcoming.includes(l));

  return (
    <div className="space-y-8">
      <PageHeader title={t.attendance.title} subtitle={t.attendance.subtitle} />
      {!s ? (
        <StatsSkeleton />
      ) : (
        <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
          <StatCard icon={CalendarCheck} tone="success" label={t.attendance.visited} value={s.present + s.late} hint={`${t.status.attendance.late}: ${s.late}`} />
          <StatCard icon={CalendarX2} tone="danger" label={t.attendance.missed} value={s.absent + s.excused} hint={`${t.status.attendance.excused}: ${s.excused}`} />
          <StatCard icon={CalendarClock} label={t.attendance.upcoming} value={s.upcoming} />
          <StatCard icon={Percent} tone="primary" label={t.attendance.rate} value={`${s.attendance_rate}%`} />
        </div>
      )}

      {upcoming.length > 0 && (
        <div>
          <SectionTitle>{t.attendance.upcoming}</SectionTitle>
          <Card className="divide-y">
            {upcoming.map((l) => (
              <div key={l.id} className="flex items-center gap-4 p-4">
                <div className="w-20 shrink-0">
                  <p className="text-sm font-medium text-primary">{fmtDate(l.starts_at, locale, { day: "numeric", month: "short" })}</p>
                  <p className="tabular text-xs text-muted-foreground">{fmtTime(l.starts_at, locale)}</p>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-primary">{l.title}</p>
                  {l.topic && <p className="truncate text-xs text-muted-foreground">{l.topic}</p>}
                </div>
                {l.meeting_url && (
                  <a href={l.meeting_url} target="_blank" rel="noreferrer noopener" className="text-sm font-medium text-accent hover:underline">
                    {t.dashboard.join}
                  </a>
                )}
              </div>
            ))}
          </Card>
        </div>
      )}

      <div>
        <SectionTitle>{t.attendance.history}</SectionTitle>
        {q.isLoading ? (
          <CardListSkeleton />
        ) : past.length ? (
          <Card className="divide-y">
            {past.map((l) => (
              <div key={l.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 p-4">
                <div className="w-20 shrink-0">
                  <p className="text-sm font-medium text-primary">{fmtDate(l.starts_at, locale, { day: "numeric", month: "short" })}</p>
                  <p className="tabular text-xs text-muted-foreground">{fmtTime(l.starts_at, locale)}</p>
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-primary">{l.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {[l.topic, l.comment].filter(Boolean).join(" · ") || "—"}
                  </p>
                </div>
                {l.lesson_status === "cancelled" ? <LessonBadge status="cancelled" /> : <AttendanceBadge status={l.status} />}
              </div>
            ))}
          </Card>
        ) : (
          <Card>
            <EmptyState icon={CalendarCheck} title={t.attendance.empty} />
          </Card>
        )}
      </div>
    </div>
  );
}
