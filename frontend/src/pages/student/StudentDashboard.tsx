import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck, CalendarCheck, CheckCircle2, ClipboardList, GraduationCap, Video } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, PageSkeleton, StatCard } from "@/components/common";
import { NotificationItem } from "@/components/notifications/NotificationItem";
import { SubscriptionWidget } from "@/components/subscriptions/SubscriptionWidget";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { dashboardApi } from "@/services/api";
import { fmtDate, fmtTime, fmtWeekday } from "@/utils/format";
import { scoreVariant } from "@/utils/status";

export default function StudentDashboard() {
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["dashboard", "student"], queryFn: dashboardApi.student });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const d = q.data;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="page-title">{t.dashboard.hello(d.full_name.split(" ")[0])}</h1>
          <p className="page-subtitle">{t.dashboard.studentSubtitle}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <div className="flex items-center gap-2 rounded-xl border bg-background px-3 py-2 text-sm">
            <GraduationCap className="size-4 text-accent" />
            <span className="text-muted-foreground">{t.dashboard.level}:</span>
            <span className="font-semibold text-primary">{d.english_level}</span>
          </div>
          <div className="flex min-w-0 items-center gap-2 rounded-xl border bg-background px-3 py-2 text-sm">
            <span className="text-muted-foreground">{t.dashboard.teacher}:</span>
            <span className="truncate font-semibold text-primary">{d.teacher_name ?? t.dashboard.noTeacher}</span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard icon={CheckCircle2} tone="success" label={t.dashboard.hwDone} value={d.homework_done} to="/student/homework" />
        <StatCard
          icon={ClipboardList}
          label={t.dashboard.hwUpcoming}
          value={d.homework_upcoming}
          hint={d.homework_needs_revision > 0 ? t.dashboard.hwRevision(d.homework_needs_revision) : undefined}
          tone={d.homework_needs_revision > 0 ? "warning" : "accent"}
          to="/student/homework"
        />
        <StatCard icon={BookOpenCheck} label={t.dashboard.testsPending} value={d.pending_tests} tone="primary" to="/student/tests" />
        <StatCard
          icon={CalendarCheck}
          label={t.dashboard.attendanceRate}
          value={`${d.attendance.attendance_rate}%`}
          hint={`${d.attendance.present + d.attendance.late} / ${d.attendance.total_marked}`}
          tone="success"
          to="/student/attendance"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1.15fr_1fr]">
        <SubscriptionWidget sub={d.subscription} />

        <Card>
          <CardHeader>
            <CardTitle>{t.dashboard.nextLessons}</CardTitle>
          </CardHeader>
          <CardContent>
            {d.next_lessons.length ? (
              <ul className="grid gap-2">
                {d.next_lessons.map((l) => (
                  <li key={l.id} className="flex items-center gap-3 rounded-xl border p-3">
                    <div className="flex w-14 shrink-0 flex-col items-center rounded-lg bg-accent-soft py-1.5 text-accent">
                      <span className="text-[11px] font-medium uppercase">{fmtWeekday(l.starts_at, locale).split(",")[0]}</span>
                      <span className="tabular text-sm font-semibold">{fmtTime(l.starts_at, locale)}</span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-primary">{l.title}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {fmtDate(l.starts_at, locale, { day: "numeric", month: "long" })}
                        {l.topic ? ` · ${l.topic}` : ""}
                      </p>
                    </div>
                    {l.meeting_url && (
                      <Button size="sm" variant="soft" asChild>
                        <a href={l.meeting_url} target="_blank" rel="noreferrer noopener">
                          <Video />
                          <span className="hidden sm:inline">{t.dashboard.join}</span>
                        </a>
                      </Button>
                    )}
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={CalendarCheck} title={t.dashboard.noLessons} className="py-8" />
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>{t.dashboard.recentTests}</CardTitle>
            <Button variant="link" size="sm" asChild className="h-auto p-0">
              <Link to="/student/tests">{t.common.viewAll}</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {d.recent_tests.length ? (
              <ul className="divide-y">
                {d.recent_tests.map((r) => (
                  <li key={r.test_id}>
                    <Link
                      to={`/student/tests/attempts/${r.attempt_id}`}
                      className="-mx-2 flex items-center justify-between gap-3 rounded-lg px-2 py-3 hover:bg-secondary/60"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-primary">{r.title}</p>
                        <p className="text-xs text-muted-foreground">{fmtDate(r.submitted_at, locale)}</p>
                      </div>
                      {r.percent !== null ? (
                        <Badge variant={scoreVariant(r.percent)} className="tabular">{r.percent}%</Badge>
                      ) : (
                        <Badge variant="primary">{t.status.attempt.pending_review}</Badge>
                      )}
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={BookOpenCheck} title={t.dashboard.noTests} className="py-8" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>{t.dashboard.recentNotifications}</CardTitle>
            <Button variant="link" size="sm" asChild className="h-auto p-0">
              <Link to="/student/notifications">{t.common.viewAll}</Link>
            </Button>
          </CardHeader>
          <CardContent className="px-3 sm:px-4">
            {d.notifications.length ? (
              <div className="grid gap-1">
                {d.notifications.map((n) => (
                  <NotificationItem key={n.id} n={n} />
                ))}
              </div>
            ) : (
              <EmptyState title={t.dashboard.noNotifications} className="py-8" />
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
