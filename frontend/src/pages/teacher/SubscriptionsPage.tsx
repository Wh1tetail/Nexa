import { useQuery } from "@tanstack/react-query";
import { CreditCard, Plus } from "lucide-react";
import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { SubscriptionBadge } from "@/components/common/StatusBadges";
import { SubscriptionActions, SubscriptionFormDialog, useCanManageSubscriptions } from "@/components/subscriptions/SubscriptionDialogs";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { subscriptionsApi } from "@/services/api";
import type { SubscriptionStatus } from "@/types/api";
import { fmtDate } from "@/utils/format";
import { subscriptionTone } from "@/utils/status";

const FILTERS: (SubscriptionStatus | "")[] = ["", "active", "expiring_soon", "expired", "frozen"];

export default function SubscriptionsPage() {
  const { t, locale } = useI18n();
  const [params, setParams] = useSearchParams();
  const status = (params.get("status") ?? "") as SubscriptionStatus | "";
  const [creating, setCreating] = useState(false);
  const canManage = useCanManageSubscriptions(); // admin; teachers only view
  const all = useQuery({ queryKey: ["subscriptions", "current"], queryFn: () => subscriptionsApi.list() });
  const items = (all.data ?? []).filter((s) => !status || s.status === status);
  const count = (s: SubscriptionStatus | "") => (all.data ?? []).filter((x) => !s || x.status === s).length;

  return (
    <div>
      <PageHeader
        title={t.subscriptions.title}
        subtitle={canManage ? t.subscriptions.subtitle : t.subscriptions.viewOnly}
        actions={
          canManage && (
            <Button onClick={() => setCreating(true)}>
              <Plus />
              {t.subscriptions.create}
            </Button>
          )
        }
      />
      <Tabs value={status} onValueChange={(v) => setParams(v ? { status: v } : {})} className="mb-4">
        <TabsList>
          {FILTERS.map((f) => (
            <TabsTrigger key={f || "all"} value={f}>
              {f ? t.status.subscription[f] : t.common.all}
              <span className="tabular text-xs opacity-60">{count(f)}</span>
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>

      {all.isLoading ? (
        <CardListSkeleton rows={5} />
      ) : all.isError ? (
        <ErrorState onRetry={() => all.refetch()} />
      ) : !items.length ? (
        <Card>
          <EmptyState icon={CreditCard} title={t.subscriptions.empty} text={t.subscriptions.emptyHint} />
        </Card>
      ) : (
        <div className="grid gap-3">
          {items.map((s) => {
            const tone = subscriptionTone(s.status);
            return (
              <Card key={s.id} className="p-4 sm:p-5">
                <div className="flex flex-col gap-4 md:flex-row md:items-center">
                  {(() => {
                    const who = (
                      <>
                        <Avatar name={s.student_name} />
                        <div className="min-w-0">
                          <p className="truncate font-medium text-primary hover:text-accent">{s.student_name}</p>
                          <p className="truncate text-xs text-muted-foreground">{s.title ?? "—"}</p>
                        </div>
                      </>
                    );
                    // student profiles are teacher pages
                    return canManage ? (
                      <div className="flex min-w-0 items-center gap-3 md:w-64">{who}</div>
                    ) : (
                      <Link to={`/teacher/students/${s.student_id}`} className="flex min-w-0 items-center gap-3 md:w-64">{who}</Link>
                    );
                  })()}
                  <div className="grid flex-1 grid-cols-2 gap-4 sm:grid-cols-3">
                    <div>
                      <p className="text-xs text-muted-foreground">{t.subscription.end}</p>
                      <p className="tabular text-sm font-medium text-primary">{fmtDate(s.end_date, locale)}</p>
                      <p className={cn("tabular text-xs font-medium", tone.text)}>{t.common.days(s.days_left)}</p>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground">{t.subscription.left}</p>
                      <p className="tabular text-sm font-medium text-primary">
                        {s.lessons_left} <span className="text-muted-foreground">/ {s.total_lessons}</span>
                      </p>
                      <Progress value={(s.used_lessons * 100) / s.total_lessons} className="mt-1.5 h-1" />
                    </div>
                    <div className="col-span-2 flex items-center sm:col-span-1">
                      <SubscriptionBadge status={s.status} />
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <SubscriptionActions sub={s} compact />
                  </div>
                </div>
              </Card>
            );
          })}
        </div>
      )}
      <SubscriptionFormDialog open={creating} onOpenChange={setCreating} />
    </div>
  );
}
