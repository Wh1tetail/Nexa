import {
  Bell,
  BookOpenCheck,
  CalendarClock,
  ClipboardCheck,
  ClipboardList,
  CreditCard,
  FileCheck2,
  FileUp,
  type LucideIcon,
} from "lucide-react";
import { useNavigate } from "react-router-dom";

import { useI18n } from "@/contexts/I18nContext";
import { useNotificationActions } from "@/hooks/useNotifications";
import { cn } from "@/lib/utils";
import type { Notification, NotificationType } from "@/types/api";
import { fmtRelative } from "@/utils/format";

const ICONS: Record<NotificationType, { icon: LucideIcon; tone: string }> = {
  homework_assigned: { icon: ClipboardList, tone: "bg-accent-soft text-accent" },
  homework_submitted: { icon: FileUp, tone: "bg-accent-soft text-accent" },
  homework_reviewed: { icon: FileCheck2, tone: "bg-success-soft text-success-strong" },
  test_assigned: { icon: BookOpenCheck, tone: "bg-accent-soft text-accent" },
  test_completed: { icon: ClipboardCheck, tone: "bg-accent-soft text-accent" },
  test_graded: { icon: ClipboardCheck, tone: "bg-success-soft text-success-strong" },
  lesson_changed: { icon: CalendarClock, tone: "bg-warning-soft text-warning-strong" },
  subscription_expiring: { icon: CreditCard, tone: "bg-warning-soft text-warning-strong" },
  subscription_expired: { icon: CreditCard, tone: "bg-danger-soft text-danger" },
  system: { icon: Bell, tone: "bg-secondary text-primary" },
};

export function NotificationItem({ n, onNavigate }: { n: Notification; onNavigate?: () => void }) {
  const { locale } = useI18n();
  const navigate = useNavigate();
  const { markRead } = useNotificationActions();
  const { icon: Icon, tone } = ICONS[n.type] ?? ICONS.system;

  return (
    <button
      type="button"
      onClick={() => {
        if (!n.is_read) markRead.mutate(n.id);
        if (n.link) {
          navigate(n.link);
          onNavigate?.();
        }
      }}
      className={cn(
        "flex w-full items-start gap-3 rounded-xl p-3 text-left transition-colors hover:bg-secondary",
        !n.is_read && "bg-accent-soft/50",
      )}
    >
      <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl", tone)}>
        <Icon className="size-4" />
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex items-start justify-between gap-2">
          <span className={cn("text-sm text-primary", !n.is_read && "font-semibold")}>{n.title}</span>
          {!n.is_read && <span className="mt-1.5 size-2 shrink-0 rounded-full bg-accent" />}
        </span>
        {n.body && <span className="mt-0.5 line-clamp-2 block text-sm text-muted-foreground">{n.body}</span>}
        <span className="mt-1 block text-xs text-muted-foreground/80">{fmtRelative(n.created_at, locale)}</span>
      </span>
    </button>
  );
}
