import { useQuery } from "@tanstack/react-query";

import { ErrorState, PageHeader, PageSkeleton, SectionTitle } from "@/components/common";
import { SubscriptionBadge } from "@/components/common/StatusBadges";
import { SubscriptionWidget } from "@/components/subscriptions/SubscriptionWidget";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { meApi } from "@/services/api";
import { fmtDate } from "@/utils/format";

export default function StudentSubscription() {
  const { t, locale } = useI18n();
  const current = useQuery({ queryKey: ["me", "subscription"], queryFn: meApi.subscription });
  const all = useQuery({ queryKey: ["me", "subscriptions"], queryFn: meApi.subscriptions });

  if (current.isLoading) return <PageSkeleton />;
  if (current.isError) return <ErrorState onRetry={() => current.refetch()} />;

  const history = (all.data ?? []).filter((s) => s.id !== current.data?.id);

  return (
    <div className="space-y-8">
      <PageHeader title={t.subscription.title} />
      <div className="max-w-2xl">
        <SubscriptionWidget sub={current.data} />
      </div>
      {history.length > 0 && (
        <div className="max-w-2xl">
          <SectionTitle>{t.subscription.history}</SectionTitle>
          <Card className="divide-y">
            {history.map((s) => (
              <div key={s.id} className="flex items-center justify-between gap-3 p-4">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium text-primary">{s.title ?? t.subscription.title}</p>
                  <p className="tabular text-xs text-muted-foreground">
                    {fmtDate(s.start_date, locale)} — {fmtDate(s.end_date, locale)} · {s.used_lessons}/{s.total_lessons}
                  </p>
                </div>
                <SubscriptionBadge status={s.status} />
              </div>
            ))}
          </Card>
        </div>
      )}
    </div>
  );
}
