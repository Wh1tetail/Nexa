import { useInfiniteQuery, useMutation, useQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { useMemo } from "react";

import { useRealtimeStatus } from "@/hooks/useNotifications";
import { MESSAGES_PAGE, messagesApi } from "@/services/api";
import type { ChatMessage } from "@/types/api";

/** Fallback polling: frequent only while the live stream is down. */
const POLL_OFFLINE_MS = 20_000;
const POLL_LIVE_MS = 5 * 60_000;

function usePollInterval() {
  return useRealtimeStatus() === "live" ? POLL_LIVE_MS : POLL_OFFLINE_MS;
}

export function useChatThreads(enabled = true) {
  return useQuery({
    queryKey: ["messages", "threads"],
    queryFn: messagesApi.threads,
    refetchInterval: usePollInterval(),
    enabled,
  });
}

export function useChatUnread(enabled = true) {
  return useQuery({
    queryKey: ["messages", "unread"],
    queryFn: messagesApi.unreadCount,
    refetchInterval: usePollInterval(),
    select: (d) => d.count,
    enabled,
  });
}

type History = InfiniteData<ChatMessage[], number | undefined>;

/** Pages are newest-first (page 0 = latest messages); `messages` is oldest-first. */
export function useChatHistory(studentId: number | null) {
  const query = useInfiniteQuery({
    queryKey: ["messages", "thread", studentId],
    queryFn: ({ pageParam }) => messagesApi.history(studentId!, pageParam),
    initialPageParam: undefined as number | undefined,
    getNextPageParam: (last) => (last.length === MESSAGES_PAGE ? last[0].id : undefined),
    refetchInterval: usePollInterval(),
    enabled: studentId != null,
  });
  const messages = useMemo(() => {
    const seen = new Set<number>();
    const out: ChatMessage[] = [];
    for (const page of [...(query.data?.pages ?? [])].reverse()) {
      for (const m of page) {
        if (!seen.has(m.id)) {
          seen.add(m.id);
          out.push(m);
        }
      }
    }
    return out;
  }, [query.data]);
  return { ...query, messages };
}

export function useSendMessage(studentId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => messagesApi.send(studentId, body),
    onSuccess: (msg) => {
      qc.setQueryData<History>(["messages", "thread", studentId], (old) => {
        if (!old?.pages.length || old.pages[0].some((m) => m.id === msg.id)) return old;
        return { ...old, pages: [[...old.pages[0], msg], ...old.pages.slice(1)] };
      });
      qc.invalidateQueries({ queryKey: ["messages", "threads"] });
    },
  });
}

export function useMarkThreadRead(studentId: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => messagesApi.read(studentId),
    onSuccess: (r) => {
      if (r.count > 0) {
        qc.invalidateQueries({ queryKey: ["messages", "threads"] });
        qc.invalidateQueries({ queryKey: ["messages", "unread"] });
        qc.invalidateQueries({ queryKey: ["messages", "thread", studentId] });
      }
    },
  });
}
