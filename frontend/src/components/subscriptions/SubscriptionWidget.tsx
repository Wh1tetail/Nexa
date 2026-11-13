import { AlertTriangle, CalendarDays, CreditCard, Snowflake } from "lucide-react";
import type { ReactNode } from "react";

import { EmptyState } from "@/components/common";
import { SubscriptionBadge } from "@/components/common/StatusBadges";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { Subscription } from "@/types/api";
import { fmtDate } from "@/utils/format";
import { subscriptionTone } from "@/utils/status";

/** Subscription tracker: dates, days left, lessons paid/used/left and a
 *  colour-coded progress bar (green >7 days, orange 1–7, red when expired). */
export function SubscriptionWidget({
  sub,
  title,
  actions,
  className,
}: {
  sub: Subscription | null | undefined;
  title?: string;
  actions?: ReactNode;
  className?: string;
}) {
  const { t, locale } = useI18n();

  if (!sub) {
    return (
      <Card className={className}>
        <CardHeader>
          <CardTitle>{title ?? t.subscription.title}</CardTitle>
        </CardHeader>
        <EmptyState icon={CreditCard} title={t.subscription.none} text={t.subscription.noneHint} className="pt-2" />
      </Card>
    );
  }

  const tone = subscriptionTone(sub.status);
  const lessonsPct = Math.round((sub.used_lessons * 100) / sub.total_lessons);
  // remaining share of the period — the bar "drains" as the end date approaches
  const remainingPct = sub.status === "expired" ? 100 : Math.max(100 - sub.progress_percent, 3);

  const message =
    sub.status === "expired"
      ? t.subscription.expiredMsg
      : sub.status === "expiring_soon"
        ? t.subscription.expiringMsg(sub.days_left)
        : sub.status === "frozen"
          ? t.subscription.frozenMsg
          : null;

  return (
    <Card className={className}>
      <CardHeader className="flex-row items-start justify-between gap-3 space-y-0">
        <div className="min-w-0">
          <CardTitle>{title ?? t.subscription.title}</CardTitle>
          {sub.title && <p className="mt-1 truncate text-sm text-muted-foreground">{sub.title}</p>}
        </div>
        <SubscriptionBadge status={sub.status} />
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3">
          <div>
            <p className="text-xs text-muted-foreground">{t.subscription.daysLeft}</p>
            <p className={cn("tabular mt-1 text-4xl font-semibold leading-none tracking-tight", tone.text)}>
              {sub.days_left}
            </p>
          </div>
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <CalendarDays className="size-4" />
            <span className="tabular">
              {fmtDate(sub.start_date, locale)} — {fmtDate(sub.end_date, locale)}
            </span>
          </div>
        </div>

        <div>
          <Progress
            value={remainingPct}
            className="h-2.5"
            indicatorClassName={tone.bar}
            aria-label={t.subscription.daysLeft}
          />
        </div>

        {message && (
          <div className={cn("flex items-start gap-2 rounded-xl p-3 text-sm", tone.soft, tone.text)}>
            {sub.status === "frozen" ? <Snowflake className="mt-0.5 size-4 shrink-0" /> : <AlertTriangle className="mt-0.5 size-4 shrink-0" />}
            <span>{message}</span>
          </div>
        )}

        <div className="grid grid-cols-3 gap-2 sm:gap-3">
          {[
            [t.subscription.paid, sub.total_lessons],
            [t.subscription.used, sub.used_lessons],
            [t.subscription.left, sub.lessons_left],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-xl bg-secondary px-3 py-3">
              <p className="tabular text-xl font-semibold text-primary">{value}</p>
              <p className="mt-0.5 text-[11px] leading-tight text-muted-foreground sm:text-xs">{label}</p>
            </div>
          ))}
        </div>

        <div>
          <div className="mb-1.5 flex justify-between text-xs text-muted-foreground">
            <span>{t.subscription.lessonsProgress}</span>
            <span className="tabular">
              {sub.used_lessons} / {sub.total_lessons}
            </span>
          </div>
          <Progress value={lessonsPct} className="h-1.5" />
        </div>

        {actions && <div className="flex flex-wrap gap-2 pt-1">{actions}</div>}
      </CardContent>
    </Card>
  );
}
