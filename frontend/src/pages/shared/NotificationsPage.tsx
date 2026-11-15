import { Bell, CheckCheck } from "lucide-react";
import { useState } from "react";

import { CardListSkeleton, EmptyState, ErrorState, PageHeader } from "@/components/common";
import { NotificationItem } from "@/components/notifications/NotificationItem";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useI18n } from "@/contexts/I18nContext";
import { useNotificationActions, useNotificationsList, useRealtimeStatus, useUnreadCount } from "@/hooks/useNotifications";

export default function NotificationsPage() {
  const { t } = useI18n();
  const [tab, setTab] = useState<"all" | "unread">("all");
  const list = useNotificationsList(tab === "unread");
  const unread = useUnreadCount();
  const { markAll } = useNotificationActions();
  const live = useRealtimeStatus();

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader
        title={t.notifications.title}
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-x-3 gap-y-1">
            {t.notifications.subtitle}
            <span className="inline-flex items-center gap-1.5 text-xs font-medium">
              <span className={live === "live" ? "size-2 rounded-full bg-success" : "size-2 animate-pulse rounded-full bg-warning"} />
              {live === "live" ? t.notifications.live : t.notifications.offline}
            </span>
          </span>
        }
        actions={
          (unread.data ?? 0) > 0 && (
            <Button variant="outline" onClick={() => markAll.mutate()} loading={markAll.isPending}>
              <CheckCheck />
              {t.notifications.markAll}
            </Button>
          )
        }
      />
      <Tabs value={tab} onValueChange={(v) => setTab(v as "all" | "unread")} className="mb-4">
        <TabsList>
          <TabsTrigger value="all">{t.notifications.all}</TabsTrigger>
          <TabsTrigger value="unread">
            {t.notifications.unread}
            {(unread.data ?? 0) > 0 && <span className="tabular rounded-full bg-accent px-1.5 text-[11px] text-accent-foreground">{unread.data}</span>}
          </TabsTrigger>
        </TabsList>
      </Tabs>
      {list.isLoading ? (
        <CardListSkeleton />
      ) : list.isError ? (
        <ErrorState onRetry={() => list.refetch()} />
      ) : list.data?.length ? (
        <Card className="grid gap-1 p-2">
          {list.data.map((n) => (
            <NotificationItem key={n.id} n={n} />
          ))}
        </Card>
      ) : (
        <Card>
          <EmptyState icon={Bell} title={t.notifications.empty} text={t.notifications.emptyHint} />
        </Card>
      )}
    </div>
  );
}
