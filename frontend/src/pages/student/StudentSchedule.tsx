import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { ErrorState, PageHeader } from "@/components/common";
import { AttendanceBadge } from "@/components/common/StatusBadges";
import { currentMonday, WeekCalendar, type CalendarEvent } from "@/components/calendar/WeekCalendar";
import { useI18n } from "@/contexts/I18nContext";
import { meApi } from "@/services/api";

/** Student's weekly schedule: upcoming lessons plus attendance of past ones. */
export default function StudentSchedule() {
  const { t } = useI18n();
  const [week, setWeek] = useState(currentMonday());
  const q = useQuery({ queryKey: ["me", "attendance"], queryFn: meApi.attendance });

  if (q.isError) return <ErrorState onRetry={() => q.refetch()} />;

  const events: CalendarEvent[] = (q.data?.lessons ?? []).map((l) => ({
    id: l.id,
    title: l.title,
    subtitle: l.topic,
    startsAt: l.starts_at,
    durationMinutes: l.duration_minutes,
    tone: l.lesson_status === "cancelled" ? "cancelled" : (l.status ?? l.lesson_status),
    meetingUrl: l.meeting_url,
    badge: l.status ? <AttendanceBadge status={l.status} short /> : undefined,
  }));

  return (
    <div>
      <PageHeader title={t.calendar.title} subtitle={t.calendar.subtitle} />
      <WeekCalendar weekStart={week} onWeekChange={setWeek} events={events} loading={q.isLoading} />
    </div>
  );
}
