import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect, useSyncExternalStore } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";

import { useI18n } from "@/contexts/I18nContext";
import { notificationsApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { realtimeStatus, runNotificationStream } from "@/services/realtime";
import type { Notification, NotificationType } from "@/types/api";

/** Fallback polling: frequent only while the live stream is down. */
const POLL_OFFLINE_MS = 30_000;
const POLL_LIVE_MS = 5 * 60_000;

export function useRealtimeStatus() {
  return useSyncExternalStore(realtimeStatus.subscribe, realtimeStatus.get);
}

function usePollInterval() {
  return useRealtimeStatus() === "live" ? POLL_LIVE_MS : POLL_OFFLINE_MS;
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: notificationsApi.unreadCount,
    refetchInterval: usePollInterval(),
    select: (d) => d.count,
  });
}

export function useNotificationsList(unreadOnly = false) {
  return useQuery({
    queryKey: ["notifications", "list", unreadOnly],
    queryFn: () => notificationsApi.list(unreadOnly),
    refetchInterval: usePollInterval(),
  });
}

/** Which cached data becomes stale when a given notification arrives. */
const STALE: Record<NotificationType, QueryKey[]> = {
  homework_assigned: [["me", "homework"]],
  homework_submitted: [["homework"]],
  homework_reviewed: [["me", "homework"]],
  test_assigned: [["me", "tests"]],
  test_completed: [["tests"]],
  test_graded: [["me", "tests"], ["me", "attempt"]],
  lesson_changed: [["me", "attendance"]],
  subscription_expiring: [["subscriptions"], ["me", "subscription"], ["students"]],
  subscription_expired: [["subscriptions"], ["me", "subscription"], ["students"]],
  system: [],
};

/** Opens the live notification stream for the signed-in user (mount once, in the layout). */
export function useRealtimeNotifications() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { t } = useI18n();

  useEffect(() => {
    const controller = new AbortController();
    const onNotification = (n: Notification) => {
      // put it on top of cached lists instantly, then refetch counts & related data
      qc.setQueriesData<Notification[]>({ queryKey: ["notifications", "list"] }, (old) =>
        old && !old.some((x) => x.id === n.id) ? [n, ...old] : old,
      );
      qc.invalidateQueries({ queryKey: ["notifications"] });
      qc.invalidateQueries({ queryKey: ["dashboard"] });
      (STALE[n.type] ?? []).forEach((key) => qc.invalidateQueries({ queryKey: key }));
      toast(n.title, {
        description: n.body ?? undefined,
        action: n.link ? { label: t.notifications.open, onClick: () => navigate(n.link!) } : undefined,
      });
    };
    runNotificationStream({ onNotification, signal: controller.signal });
    return () => controller.abort();
  }, [qc, navigate, t]);
}

export function useNotificationActions() {
  const qc = useQueryClient();
  const { t } = useI18n();
  const invalidate = () => qc.invalidateQueries({ queryKey: ["notifications"] });
  const markRead = useMutation({ mutationFn: notificationsApi.read, onSuccess: invalidate });
  const markAll = useMutation({
    mutationFn: notificationsApi.readAll,
    onSuccess: () => {
      invalidate();
      toast.success(t.notifications.allRead);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return { markRead, markAll };
}
