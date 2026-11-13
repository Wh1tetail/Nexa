import * as Popover from "@radix-ui/react-popover";
import { Bell, CheckCheck } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { EmptyState } from "@/components/common";
import { NotificationItem } from "@/components/notifications/NotificationItem";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { homePath, useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useNotificationActions, useNotificationsList, useUnreadCount } from "@/hooks/useNotifications";

export function NotificationBell() {
  const { t } = useI18n();
  const { user } = useAuth();
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const list = useNotificationsList();
  const { markAll } = useNotificationActions();
  const count = unread.data ?? 0;
  const base = homePath(user?.role ?? "teacher");

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <Button variant="ghost" size="icon" className="relative" aria-label={t.nav.notifications}>
          <Bell className="!size-5" />
          {count > 0 && (
            <span className="tabular absolute right-1.5 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white ring-2 ring-background">
              {count > 99 ? "99+" : count}
            </span>
          )}
        </Button>
      </Popover.Trigger>
      <Popover.Portal>
        <Popover.Content
          align="end"
          sideOffset={8}
          collisionPadding={12}
          className="z-50 w-[min(380px,calc(100vw-24px))] rounded-2xl border bg-popover shadow-lift data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95"
        >
          <div className="flex items-center justify-between border-b px-4 py-3">
            <p className="font-semibold text-primary">{t.notifications.title}</p>
            {count > 0 && (
              <Button variant="ghost" size="sm" onClick={() => markAll.mutate()} loading={markAll.isPending}>
                <CheckCheck />
                {t.notifications.markAll}
              </Button>
            )}
          </div>
          <div className="max-h-[60vh] overflow-y-auto p-2">
            {list.isLoading ? (
              <div className="space-y-2 p-2">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-14" />
                ))}
              </div>
            ) : list.data?.length ? (
              list.data.slice(0, 8).map((n) => <NotificationItem key={n.id} n={n} onNavigate={() => setOpen(false)} />)
            ) : (
              <EmptyState icon={Bell} title={t.notifications.empty} className="py-8" />
            )}
          </div>
          <div className="border-t p-2">
            <Button variant="ghost" className="w-full" asChild onClick={() => setOpen(false)}>
              <Link to={`${base}/notifications`}>{t.common.viewAll}</Link>
            </Button>
          </div>
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
