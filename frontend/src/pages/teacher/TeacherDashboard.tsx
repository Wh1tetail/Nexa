import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, ClipboardCheck, CreditCard, FileUp, Users } from "lucide-react";
import { Link } from "react-router-dom";

import { EmptyState, ErrorState, PageSkeleton, StatCard } from "@/components/common";
import { SubscriptionBadge } from "@/components/common/StatusBadges";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { dashboardApi } from "@/services/api";
import { fmtDate, fmtRelative, fmtTime, fmtWeekday } from "@/utils/format";

export default function TeacherDashboard() {
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["dashboard", "teacher"], queryFn: dashboardApi.teacher, refetchInterval: 60_000 });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const d = q.data;
  const needAttention = d.expiring_subscriptions.length;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="page-title">{t.dashboard.hello(d.full_name.split(" ")[0])}</h1>
        <p className="page-subtitle">{t.dashboard.teacherSubtitle}</p>
      </div>

      {needAttention > 0 && (
        <Link
          to="/teacher/subscriptions?status=expiring_soon"
          className="flex items-center gap-3 rounded-2xl border border-warning/40 bg-warning-soft p-4 transition-shadow hover:shadow-soft"
        >
          <AlertTriangle className="size-5 shrink-0 text-warning" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-semibold text-warning-strong">{t.subscriptions.alertTitle(needAttention)}</p>
            <p className="text-xs text-warning-strong">{t.subscriptions.alertText}</p>
          </div>
        </Link>
      )}

      <div className="grid grid-cols-2 gap-3 sm:gap-4 lg:grid-cols-4">
        <StatCard icon={Users} label={t.dashboard.studentsTotal} value={d.students_total} to="/teacher/students" />
        <StatCard icon={CreditCard} tone="success" label={t.dashboard.subsActive} value={d.subscriptions_active} to="/teacher/subscriptions" />
        <StatCard
          icon={AlertTriangle}
          tone="warning"
          label={t.dashboard.subsExpiring}
          value={d.subscriptions_expiring}
          hint={d.subscriptions_expired ? `${t.status.subscription.expired}: ${d.subscriptions_expired}` : undefined}
          to="/teacher/subscriptions?status=expiring_soon"
        />
        <StatCard
          icon={ClipboardCheck}
          tone="primary"
          label={t.dashboard.toReview}
          value={d.homework_to_review + d.tests_to_review}
          hint={t.dashboard.toReviewHint(d.homework_to_review, d.tests_to_review)}
          to="/teacher/homework"
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>{t.dashboard.upcomingLessons}</CardTitle>
            <Button variant="link" size="sm" asChild className="h-auto p-0">
              <Link to="/teacher/lessons">{t.common.viewAll}</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {d.upcoming_lessons.length ? (
              <ul className="grid gap-2">
                {d.upcoming_lessons.map((l) => (
                  <li key={l.id} className="flex items-center gap-3 rounded-xl border p-3">
                    <div className="flex w-16 shrink-0 flex-col items-center rounded-lg bg-accent-soft py-1.5 text-accent">
                      <span className="text-[11px] font-medium">{fmtWeekday(l.starts_at, locale).split(",")[0]}</span>
                      <span className="tabular text-sm font-semibold">{fmtTime(l.starts_at, locale)}</span>
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium text-primary">{l.title}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {fmtDate(l.starts_at, locale, { day: "numeric", month: "long" })} · {t.common.minutes(l.duration_minutes)} ·{" "}
                        {t.common.studentsCount(l.participants)}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={CalendarClock} title={t.dashboard.noLessons} className="py-8" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex-row items-center justify-between space-y-0">
            <CardTitle>{t.dashboard.expiringTitle}</CardTitle>
            <Button variant="link" size="sm" asChild className="h-auto p-0">
              <Link to="/teacher/subscriptions">{t.common.viewAll}</Link>
            </Button>
          </CardHeader>
          <CardContent>
            {d.expiring_subscriptions.length ? (
              <ul className="divide-y">
                {d.expiring_subscriptions.map((s) => (
                  <li key={s.id}>
                    <Link to={`/teacher/students/${s.student_id}`} className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 hover:bg-secondary/60">
                      <Avatar name={s.student_name} />
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium text-primary">{s.student_name}</p>
                        <p className="tabular text-xs text-muted-foreground">
                          {fmtDate(s.end_date, locale)} · {t.subscription.left.toLowerCase()}: {s.lessons_left}
                        </p>
                      </div>
                      <SubscriptionBadge status={s.status} />
                    </Link>
                  </li>
                ))}
              </ul>
            ) : (
              <EmptyState icon={CreditCard} title={t.dashboard.expiringEmpty} className="py-8" />
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{t.dashboard.activity}</CardTitle>
        </CardHeader>
        <CardContent>
          {d.recent_activity.length ? (
            <ul className="divide-y">
              {d.recent_activity.map((a, i) => (
                <li key={i}>
                  <Link to={a.link} className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-3 hover:bg-secondary/60">
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent">
                      {a.kind === "homework_submitted" ? <FileUp className="size-4" /> : <ClipboardCheck className="size-4" />}
                    </span>
                    <p className="min-w-0 flex-1 text-sm">
                      <span className="font-medium text-primary">{a.student_name}</span>{" "}
                      <span className="text-muted-foreground">
                        {a.kind === "homework_submitted" ? t.dashboard.activityHomework : t.dashboard.activityTest}
                      </span>{" "}
                      <span className="font-medium text-primary">«{a.title}»</span>
                    </p>
                    <span className="hidden shrink-0 text-xs text-muted-foreground sm:block">{fmtRelative(a.at, locale)}</span>
                  </Link>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState title={t.dashboard.activityEmpty} className="py-8" />
          )}
        </CardContent>
      </Card>
    </div>
  );
}
