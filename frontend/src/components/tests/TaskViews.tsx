import { BookOpen, CheckCircle2, Headphones, XCircle } from "lucide-react";
import { useRef, useState, type DragEvent } from "react";
import { toast } from "sonner";

import { Markdown } from "@/components/tests/Markdown";
import { InlineMedia, useBlobUrl } from "@/components/tests/TestMedia";
import { Card } from "@/components/ui/card";
import { Input, NativeSelect } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { meApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Attachment, Question } from "@/types/api";

const norm = (s: string, caseSensitive: boolean) => {
  const v = s.replace(/’/g, "'").split(/\s+/).filter(Boolean).join(" ");
  return caseSensitive ? v : v.toLowerCase();
};

const filled = (value: string[], n: number) => Array.from({ length: n }, (_, i) => value[i] ?? "");

// ---------- audio and reading blocks ----------

/** Audio with an optional listening limit. Every start from the beginning is
 *  counted on the server first; resuming after a pause is free. */
function LimitedAudio({
  file,
  attemptId,
  questionId,
  maxPlays,
  initialPlays,
  live,
}: {
  file: Attachment;
  attemptId?: number;
  questionId: number;
  maxPlays: number | null;
  initialPlays: number;
  live: boolean;
}) {
  const { t } = useI18n();
  const { url, isLoading } = useBlobUrl(file);
  const [plays, setPlays] = useState(initialPlays);
  const fresh = useRef(true); // the next "play" starts a new listening
  const pending = useRef(false);
  const limited = live && maxPlays !== null;
  const left = limited ? Math.max(maxPlays! - plays, 0) : null;

  async function onPlay(e: React.SyntheticEvent<HTMLAudioElement>) {
    const audio = e.currentTarget;
    if (!live || !attemptId || !fresh.current || pending.current) return;
    pending.current = true;
    try {
      const r = await meApi.playAudio(attemptId, questionId);
      setPlays(r.plays);
      fresh.current = false;
    } catch (err) {
      audio.pause();
      audio.currentTime = 0;
      if (maxPlays !== null) setPlays(maxPlays);
      toast.error(errorMessage(err));
    } finally {
      pending.current = false;
    }
  }

  if (limited && left === 0) {
    return <p className="rounded-xl bg-secondary px-4 py-3 text-sm text-muted-foreground">{t.tasks.noPlaysLeft}</p>;
  }
  if (isLoading || !url) return <Skeleton className="h-12 w-full" />;
  return (
    <div className="grid gap-1.5">
      <audio
        controls
        preload="metadata"
        src={url}
        className="w-full"
        controlsList="nodownload noplaybackrate"
        onContextMenu={(e) => e.preventDefault()}
        onPlay={onPlay}
        onEnded={() => {
          fresh.current = true;
        }}
        onSeeked={(e) => {
          if (e.currentTarget.currentTime < 0.3 && e.currentTarget.paused) fresh.current = true;
        }}
      />
      {limited && <p className="text-xs text-muted-foreground">{t.tasks.playsLeft(left!)}</p>}
    </div>
  );
}

export function BlockView({
  q,
  files,
  attemptId,
  plays = {},
  live = false,
}: {
  q: Question;
  files: Attachment[];
  attemptId?: number;
  plays?: Record<string, number>;
  /** the test is being taken (listening limits apply) */
  live?: boolean;
}) {
  const { t } = useI18n();
  const c = q.config;
  if (q.type === "audio") {
    const file = files.find((f) => f.id === c.attachment_id);
    return (
      <Card className="border-accent/20 bg-accent-soft/30 p-5 sm:p-6">
        <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-accent">
          <Headphones className="size-4" />
          {t.status.questionType.audio}
        </p>
        <h3 className="mt-1.5 text-base font-semibold">{q.text}</h3>
        {c.body && <p className="mt-1 whitespace-pre-wrap text-sm text-muted-foreground">{c.body}</p>}
        <div className="mt-3">
          {file ? (
            <LimitedAudio
              file={file}
              attemptId={attemptId}
              questionId={q.id}
              maxPlays={c.max_plays ?? null}
              initialPlays={plays[String(q.id)] ?? 0}
              live={live}
            />
          ) : null}
        </div>
      </Card>
    );
  }
  const image = c.image_id ? files.find((f) => f.id === c.image_id) : undefined;
  return (
    <Card className="p-5 sm:p-6">
      <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-accent">
        <BookOpen className="size-4" />
        {t.status.questionType.reading}
      </p>
      <h3 className="mt-1.5 text-lg font-semibold">{q.text}</h3>
      {image && (
        <div className="mt-3">
          <InlineMedia file={image} />
        </div>
      )}
      <div className="mt-3">
        <Markdown text={c.body ?? ""} />
      </div>
    </Card>
  );
}

// ---------- fill in the gaps ----------

export function GapsView({
  q,
  value,
  onChange,
}: {
  q: Question;
  value: string[];
  /** absent = review mode */
  onChange?: (v: string[]) => void;
}) {
  const { t } = useI18n();
  const c = q.config;
  const segments = c.segments ?? [];
  const gaps = c.gaps ?? [];
  const answers = (c.answers as string[][] | undefined) ?? null; // only when revealed
  const vals = filled(value, gaps.length);
  const readOnly = !onChange;
  const [picked, setPicked] = useState<string | null>(null);
  const set = (i: number, v: string) => onChange?.(vals.map((x, j) => (j === i ? v : x)));
  const isRight = (i: number) =>
    answers ? answers[i].some((a) => norm(a, !!c.case_sensitive) === norm(vals[i], !!c.case_sensitive)) && !!vals[i].trim() : null;

  const bankLeft = (c.bank ?? []).filter((w) => c.mode !== "drag" || !vals.includes(w));

  function gap(i: number) {
    const g = gaps[i];
    const ok = readOnly ? isRight(i) : null;
    const tone = ok === null ? "" : ok ? "border-success/60 bg-success-soft" : "border-danger/50 bg-danger-soft";
    if (readOnly) {
      return (
        <span key={`g${i}`} className="inline-flex flex-wrap items-baseline gap-1 align-baseline">
          <span className={cn("rounded-md border px-2 py-0.5 font-medium text-primary", tone || "bg-secondary")}>
            {vals[i] || "—"}
          </span>
          {ok === false && answers && <span className="text-xs text-success-strong">→ {answers[i][0]}</span>}
        </span>
      );
    }
    if (c.mode === "dropdown") {
      return (
        <NativeSelect
          key={`g${i}`}
          value={vals[i]}
          onChange={(e) => set(i, e.target.value)}
          className="mx-1 inline-flex h-9 w-auto min-w-[120px] align-middle"
          aria-label={`${t.tests.question} ${i + 1}`}
        >
          <option value="">{g.hint ? `(${g.hint})` : t.tasks.choose}</option>
          {(c.bank ?? []).map((w) => (
            <option key={w} value={w}>{w}</option>
          ))}
        </NativeSelect>
      );
    }
    if (c.mode === "drag") {
      return (
        <button
          key={`g${i}`}
          type="button"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e: DragEvent) => {
            e.preventDefault();
            const w = e.dataTransfer.getData("text/plain");
            if (w) set(i, w);
          }}
          onClick={() => {
            if (picked) {
              set(i, picked);
              setPicked(null);
            } else if (vals[i]) set(i, "");
          }}
          title={vals[i] ? t.tasks.removeWord : undefined}
          className={cn(
            "mx-1 inline-flex min-h-9 min-w-[96px] items-center justify-center rounded-lg border-2 border-dashed px-2 align-middle text-sm transition-colors",
            vals[i] ? "border-accent bg-accent-soft font-medium text-accent" : "border-input text-muted-foreground",
            picked && !vals[i] && "border-accent",
          )}
        >
          {vals[i] || (g.hint ? `(${g.hint})` : "…")}
        </button>
      );
    }
    return (
      <Input
        key={`g${i}`}
        value={vals[i]}
        onChange={(e) => set(i, e.target.value)}
        placeholder={g.hint ? `(${g.hint})` : t.tasks.gapPlaceholder}
        className="mx-1 inline-flex h-9 w-36 align-middle"
        maxLength={200}
        aria-label={`${t.tests.question} ${i + 1}`}
        autoComplete="off"
        spellCheck={false}
      />
    );
  }

  const right = readOnly && answers ? gaps.filter((_, i) => isRight(i)).length : null;
  return (
    <div className="grid gap-3">
      <div className="rounded-xl border bg-secondary/30 px-4 py-3 text-[15px] leading-[2.6]">
        {segments.map((s, i) => (
          <span key={`s${i}`}>
            <span className="whitespace-pre-wrap">{s}</span>
            {i < gaps.length && gap(i)}
          </span>
        ))}
      </div>
      {!readOnly && c.mode === "drag" && (
        <div className="grid gap-2">
          <p className="text-xs text-muted-foreground">{t.tasks.dragHint}</p>
          <div className="flex flex-wrap gap-2" aria-label={t.tasks.wordBank}>
            {bankLeft.map((w) => (
              <button
                key={w}
                type="button"
                draggable
                onDragStart={(e) => e.dataTransfer.setData("text/plain", w)}
                onClick={() => setPicked((p) => (p === w ? null : w))}
                aria-pressed={picked === w}
                className={cn(
                  "cursor-grab rounded-lg border bg-card px-3 py-1.5 text-sm font-medium text-primary shadow-sm transition-colors active:cursor-grabbing",
                  picked === w ? "border-accent bg-accent-soft text-accent" : "hover:bg-secondary",
                )}
              >
                {w}
              </button>
            ))}
          </div>
        </div>
      )}
      {right !== null && <p className="text-xs text-muted-foreground">{t.tasks.result(right, gaps.length)}</p>}
    </div>
  );
}

// ---------- matching ----------

export function MatchingView({ q, value, onChange }: { q: Question; value: string[]; onChange?: (v: string[]) => void }) {
  const { t } = useI18n();
  const c = q.config;
  const lefts = c.lefts ?? [];
  const answers = (c.answers as string[] | undefined) ?? null;
  const vals = filled(value, lefts.length);
  const readOnly = !onChange;
  return (
    <div className="grid gap-2">
      {!readOnly && <p className="text-xs text-muted-foreground">{t.tasks.matchHint}</p>}
      {lefts.map((left, i) => {
        const ok = readOnly && answers ? vals[i] === answers[i] : null;
        return (
          <div
            key={i}
            className={cn(
              "grid items-center gap-2 rounded-xl border px-3 py-2 sm:grid-cols-[1fr_auto_1fr]",
              ok === true && "border-success/50 bg-success-soft",
              ok === false && "border-danger/40 bg-danger-soft",
            )}
          >
            <span className="break-words text-sm font-medium text-primary">{left}</span>
            <span className="hidden text-muted-foreground sm:inline">→</span>
            {readOnly ? (
              <span className="flex flex-wrap items-center gap-2 text-sm">
                {ok === true && <CheckCircle2 className="size-4 text-success-strong" />}
                {ok === false && <XCircle className="size-4 text-danger-strong" />}
                <span className="font-medium">{vals[i] || "—"}</span>
                {ok === false && answers && <span className="text-xs text-success-strong">→ {answers[i]}</span>}
              </span>
            ) : (
              <NativeSelect
                value={vals[i]}
                onChange={(e) => onChange?.(vals.map((x, j) => (j === i ? e.target.value : x)))}
                className="h-9"
                aria-label={left}
              >
                <option value="">{t.tasks.choose}</option>
                {(c.rights ?? []).map((r) => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </NativeSelect>
            )}
          </div>
        );
      })}
    </div>
  );
}
