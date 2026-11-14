import { ArrowLeft, Check, CheckCheck, Download, MessageSquare, Paperclip, Search, SendHorizontal, UserRound, X } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";

import { EmptyState, ErrorState, PageHeader } from "@/components/common";
import { ACCEPT, validateFiles } from "@/components/common/Files";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/contexts/AuthContext";
import { useI18n } from "@/contexts/I18nContext";
import { useChatHistory, useChatThreads, useMarkThreadRead, useSendMessage } from "@/hooks/useMessages";
import { cn } from "@/lib/utils";
import { filesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import { activeChat } from "@/services/realtime";
import type { Attachment, ChatMessage, ChatThread } from "@/types/api";
import { dayKey, fmtDate, fmtShortDate, fmtSize, fmtTime } from "@/utils/format";

const MAX_LENGTH = 4000;
const MAX_FILES = 5;
/** Chat card fills the viewport below the header and page title. */
const PANE_HEIGHT = "h-[calc(100dvh-12.5rem)] min-h-[420px] sm:h-[calc(100dvh-14rem)]";

export default function MessagesPage() {
  const { user } = useAuth();
  const { t } = useI18n();
  const threads = useChatThreads();
  const params = useParams();
  const isTeacher = user?.role === "teacher";
  // teacher: thread from the URL; student: the one conversation with their teacher
  const studentId = isTeacher ? (params.studentId ? Number(params.studentId) : null) : (user?.student_id ?? null);
  const thread = threads.data?.find((x) => x.student_id === studentId) ?? null;

  if (threads.isError) {
    return <ErrorState onRetry={() => threads.refetch()} />;
  }

  if (!isTeacher) {
    return (
      <div className="mx-auto max-w-3xl">
        <PageHeader title={t.messages.title} subtitle={t.messages.subtitleStudent} />
        <Card className={cn("flex flex-col overflow-hidden", PANE_HEIGHT)}>
          {threads.isLoading ? (
            <ConversationSkeleton />
          ) : thread ? (
            <Conversation thread={thread} />
          ) : (
            <EmptyState icon={UserRound} title={t.messages.noTeacher} text={t.messages.noTeacherHint} className="my-auto" />
          )}
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className={cn(studentId != null && "hidden lg:block")}>
        <PageHeader title={t.messages.title} subtitle={t.messages.subtitleTeacher} />
      </div>
      <Card className={cn("grid overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]", PANE_HEIGHT)}>
        <aside className={cn("min-h-0 flex-col border-r lg:flex", studentId != null ? "hidden" : "flex")}>
          <ThreadList threads={threads.data} loading={threads.isLoading} activeId={studentId} />
        </aside>
        <section className={cn("min-h-0 flex-col lg:flex", studentId == null ? "hidden" : "flex")}>
          {threads.isLoading ? (
            <ConversationSkeleton />
          ) : thread ? (
            <Conversation thread={thread} key={thread.student_id} />
          ) : studentId != null ? (
            <EmptyState icon={MessageSquare} title={t.messages.notFound} className="my-auto" />
          ) : (
            <EmptyState icon={MessageSquare} title={t.messages.pickThread} text={t.messages.pickThreadHint} className="my-auto" />
          )}
        </section>
      </Card>
    </div>
  );
}

function ThreadList({ threads, loading, activeId }: { threads?: ChatThread[]; loading: boolean; activeId: number | null }) {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const [query, setQuery] = useState("");
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return (threads ?? []).filter((x) => !q || x.partner.full_name.toLowerCase().includes(q));
  }, [threads, query]);

  return (
    <>
      <div className="border-b p-3">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={t.messages.search} className="pl-9" />
        </div>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-2">
        {loading ? (
          <div className="grid gap-2 p-1">
            {Array.from({ length: 5 }, (_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : !threads?.length ? (
          <EmptyState icon={UserRound} title={t.messages.noThreads} text={t.messages.noThreadsHint} />
        ) : !filtered.length ? (
          <EmptyState icon={Search} title={t.messages.noMatches} />
        ) : (
          filtered.map((x) => {
            const last = x.last_message;
            return (
              <Link
                key={x.student_id}
                to={`/teacher/messages/${x.student_id}`}
                className={cn(
                  "flex items-center gap-3 rounded-lg px-2.5 py-2.5 transition-colors hover:bg-secondary",
                  activeId === x.student_id && "bg-accent-soft hover:bg-accent-soft",
                )}
              >
                <Avatar name={x.partner.full_name} className="size-10 shrink-0" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className={cn("truncate text-sm font-medium text-primary", !x.partner.is_active && "text-muted-foreground line-through")}>
                      {x.partner.full_name}
                    </span>
                    {last && <span className="shrink-0 text-[11px] text-muted-foreground">{fmtShortDate(last.created_at, locale)}</span>}
                  </div>
                  <div className="flex items-center justify-between gap-2">
                    <span className="truncate text-xs text-muted-foreground">
                      {last ? (last.sender_user_id === user?.id ? `${t.messages.you}: ` : "") + lastText(last) : t.messages.noMessagesYet}
                    </span>
                    {x.unread_count > 0 && (
                      <span className="tabular shrink-0 rounded-full bg-accent px-1.5 text-[11px] font-medium text-white">{x.unread_count}</span>
                    )}
                  </div>
                </div>
              </Link>
            );
          })
        )}
      </div>
    </>
  );
}

/** Text for previews: the message, or its file names. */
function lastText(m: ChatMessage) {
  if (m.body) return m.body;
  const [first, ...rest] = m.attachments;
  return first ? `📎 ${first.original_name}${rest.length ? ` +${rest.length}` : ""}` : "";
}

function ConversationSkeleton() {
  return (
    <div className="flex flex-1 flex-col gap-3 p-4">
      <Skeleton className="h-10 w-48" />
      <Skeleton className="h-12 w-2/3" />
      <Skeleton className="ml-auto h-12 w-1/2" />
      <Skeleton className="h-12 w-3/5" />
    </div>
  );
}

function Conversation({ thread }: { thread: ChatThread }) {
  const { t, locale } = useI18n();
  const { user } = useAuth();
  const navigate = useNavigate();
  const isTeacher = user?.role === "teacher";
  const sid = thread.student_id;
  const history = useChatHistory(sid);
  const send = useSendMessage(sid);
  const markRead = useMarkThreadRead(sid);
  const [text, setText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const fileInput = useRef<HTMLInputElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const stickToBottom = useRef(true);
  const prevHeight = useRef<number | null>(null);
  const { messages } = history;

  // no toasts for this conversation while it is on screen
  useEffect(() => {
    activeChat.set(sid);
    return () => activeChat.set(null);
  }, [sid]);

  // mark the partner's messages read while the conversation is visible
  const hasUnread = messages.some((m) => m.sender_user_id !== user?.id && !m.read_at);
  const { mutate: markReadMutate, isPending: markingRead } = markRead;
  useEffect(() => {
    const tryRead = () => {
      if (hasUnread && !markingRead && document.visibilityState === "visible") markReadMutate();
    };
    tryRead();
    document.addEventListener("visibilitychange", tryRead);
    return () => document.removeEventListener("visibilitychange", tryRead);
  }, [hasUnread, markingRead, markReadMutate]);

  // keep the view pinned to the newest message; keep position when older ones load
  useLayoutEffect(() => {
    const el = scroller.current;
    if (!el) return;
    if (prevHeight.current != null) {
      el.scrollTop += el.scrollHeight - prevHeight.current;
      prevHeight.current = null;
    } else if (stickToBottom.current) {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages]);

  function loadOlder() {
    prevHeight.current = scroller.current?.scrollHeight ?? null;
    history.fetchNextPage();
  }

  const body = text.trim();
  const tooLong = text.length > MAX_LENGTH;
  const canSend = thread.partner.is_active && (body.length > 0 || files.length > 0) && !tooLong && !send.isPending;

  function addFiles(list: FileList | null) {
    if (!list?.length) return;
    const { ok, errors } = validateFiles(Array.from(list), t.files);
    errors.forEach((e) => toast.error(e));
    const next = [...files, ...ok];
    if (next.length > MAX_FILES) toast.error(t.messages.maxFiles(MAX_FILES));
    setFiles(next.slice(0, MAX_FILES));
    if (fileInput.current) fileInput.current.value = "";
  }

  function submit() {
    if (!canSend) return;
    stickToBottom.current = true;
    send.mutate({ body, files }, {
      onSuccess: () => {
        setText("");
        setFiles([]);
        textarea.current?.focus();
      },
      onError: (e) => toast.error(errorMessage(e)),
    });
  }

  function onKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  }

  // auto-grow the composer up to ~6 lines
  useLayoutEffect(() => {
    const el = textarea.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text]);

  const today = dayKey(new Date());
  const yesterday = dayKey(new Date(Date.now() - 86_400_000));
  const dayLabel = (iso: string) => {
    const k = dayKey(iso);
    return k === today ? t.messages.today : k === yesterday ? t.messages.yesterday : fmtDate(iso, locale, { day: "numeric", month: "long" });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <header className="flex items-center gap-3 border-b px-3 py-2.5 sm:px-4">
        {isTeacher && (
          <Button variant="ghost" size="icon" className="-ml-1 lg:hidden" onClick={() => navigate("/teacher/messages")} aria-label={t.messages.back}>
            <ArrowLeft className="!size-5" />
          </Button>
        )}
        <Avatar name={thread.partner.full_name} className="size-9 shrink-0" />
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-primary">{thread.partner.full_name}</p>
          {!thread.partner.is_active && <p className="truncate text-xs text-danger">{t.messages.inactive}</p>}
        </div>
        {isTeacher && (
          <Button variant="outline" size="sm" asChild>
            <Link to={`/teacher/students/${sid}`}>
              <UserRound />
              <span className="hidden sm:inline">{t.messages.profile}</span>
            </Link>
          </Button>
        )}
      </header>

      <div
        ref={scroller}
        onScroll={(e) => {
          const el = e.currentTarget;
          stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80;
        }}
        className="min-h-0 flex-1 overflow-y-auto bg-secondary/40 px-3 py-4 sm:px-5"
        aria-live="polite"
      >
        {history.isLoading ? (
          <ConversationSkeleton />
        ) : history.isError ? (
          <ErrorState onRetry={() => history.refetch()} />
        ) : !messages.length ? (
          <EmptyState icon={MessageSquare} title={t.messages.emptyThread} text={t.messages.emptyThreadHint} />
        ) : (
          <div className="grid gap-1.5">
            {history.hasNextPage && (
              <div className="mb-2 flex justify-center">
                <Button variant="outline" size="sm" onClick={loadOlder} loading={history.isFetchingNextPage}>
                  {t.messages.loadOlder}
                </Button>
              </div>
            )}
            {messages.map((m, i) => (
              <MessageRow
                key={m.id}
                m={m}
                mine={m.sender_user_id === user?.id}
                dayHeader={i === 0 || dayKey(messages[i - 1].created_at) !== dayKey(m.created_at) ? dayLabel(m.created_at) : null}
                time={fmtTime(m.created_at, locale)}
              />
            ))}
          </div>
        )}
      </div>

      <form
        className="border-t bg-background p-2.5 sm:p-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {files.length > 0 && (
          <ul className="mb-2 flex flex-wrap gap-1.5" aria-label={t.messages.attached}>
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`} className="flex max-w-full items-center gap-1.5 rounded-lg border bg-secondary/60 py-1 pl-2.5 pr-1 text-xs">
                <Paperclip className="size-3.5 shrink-0 text-muted-foreground" />
                <span className="max-w-[180px] truncate font-medium text-primary">{f.name}</span>
                <span className="shrink-0 text-muted-foreground">{fmtSize(f.size)}</span>
                <button
                  type="button"
                  onClick={() => setFiles(files.filter((_, j) => j !== i))}
                  className="rounded p-0.5 text-muted-foreground hover:bg-background hover:text-danger"
                  aria-label={`${t.common.delete}: ${f.name}`}
                >
                  <X className="size-3.5" />
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-end gap-2">
          <input ref={fileInput} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => addFiles(e.target.files)} />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            className="size-10 shrink-0 text-muted-foreground"
            onClick={() => fileInput.current?.click()}
            disabled={!thread.partner.is_active || files.length >= MAX_FILES || send.isPending}
            aria-label={t.messages.attach}
            title={t.messages.attach}
          >
            <Paperclip className="!size-5" />
          </Button>
          <Textarea
            ref={textarea}
            rows={1}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder={thread.partner.is_active ? t.messages.placeholder : t.messages.inactive}
            disabled={!thread.partner.is_active}
            aria-label={t.messages.placeholder}
            aria-invalid={tooLong}
            className="max-h-40 min-h-10 resize-none"
          />
          <Button type="submit" size="icon" className="size-10 shrink-0" disabled={!canSend} loading={send.isPending} aria-label={t.messages.send}>
            <SendHorizontal />
          </Button>
        </div>
        <p className={cn("mt-1.5 hidden px-1 text-[11px] text-muted-foreground sm:block", tooLong && "block text-danger")}>
          {tooLong ? `${t.messages.tooLong(MAX_LENGTH)} (${text.length})` : t.messages.sendHint}
        </p>
      </form>
    </div>
  );
}

function MessageRow({ m, mine, dayHeader, time }: { m: ChatMessage; mine: boolean; dayHeader: string | null; time: string }) {
  const { t } = useI18n();
  return (
    <>
      {dayHeader && (
        <div className="my-2 flex justify-center">
          <span className="rounded-full bg-background px-3 py-0.5 text-[11px] font-medium text-muted-foreground shadow-sm">{dayHeader}</span>
        </div>
      )}
      <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
        <div
          className={cn(
            "max-w-[85%] rounded-2xl px-3.5 py-2 text-sm shadow-sm sm:max-w-[70%]",
            mine ? "rounded-br-md bg-accent text-white" : "rounded-bl-md bg-background text-primary",
          )}
        >
          {m.attachments.length > 0 && (
            <div className={cn("grid gap-1.5", m.body && "mb-1.5")}>
              {m.attachments.map((a) => (
                <ChatFile key={a.id} file={a} mine={mine} />
              ))}
            </div>
          )}
          {m.body && <p className="whitespace-pre-wrap break-words">{m.body}</p>}
          <div className={cn("mt-0.5 flex items-center justify-end gap-1 text-[10px]", mine ? "text-white/75" : "text-muted-foreground")}>
            <span>{time}</span>
            {mine &&
              (m.read_at ? (
                <CheckCheck className="size-3.5" aria-label={t.messages.read} />
              ) : (
                <Check className="size-3.5" aria-label={t.messages.sent} />
              ))}
          </div>
        </div>
      </div>
    </>
  );
}

function ChatFile({ file, mine }: { file: Attachment; mine: boolean }) {
  const { t } = useI18n();
  const [busy, setBusy] = useState(false);
  return (
    <button
      type="button"
      disabled={busy}
      onClick={async () => {
        setBusy(true);
        try {
          await filesApi.download(file);
        } catch (e) {
          toast.error(errorMessage(e));
        } finally {
          setBusy(false);
        }
      }}
      className={cn(
        "flex min-w-0 items-center gap-2.5 rounded-xl px-2.5 py-2 text-left transition-colors disabled:opacity-60",
        mine ? "bg-white/15 hover:bg-white/25" : "bg-secondary hover:bg-secondary/70",
      )}
      aria-label={`${t.common.download}: ${file.original_name}`}
    >
      <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", mine ? "bg-white/20" : "bg-accent-soft text-accent")}>
        {busy ? <span className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" /> : <Download className="size-4" />}
      </span>
      <span className="min-w-0">
        <span className="block truncate font-medium">{file.original_name}</span>
        <span className={cn("block text-[11px]", mine ? "text-white/75" : "text-muted-foreground")}>{fmtSize(file.size_bytes)}</span>
      </span>
    </button>
  );
}
