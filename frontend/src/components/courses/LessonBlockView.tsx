import { useMutation } from "@tanstack/react-query";
import { ChevronDown, ChevronUp, FileWarning, RotateCcw } from "lucide-react";
import { createContext, useContext, useState, type ReactNode } from "react";
import { toast } from "sonner";

import { Markdown } from "@/components/tests/Markdown";
import { QuestionView } from "@/components/tests/QuestionView";
import { LimitedAudio } from "@/components/tests/TaskViews";
import { InlineMedia, useBlobUrl } from "@/components/tests/TestMedia";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { BLOCK_ICONS, embedUrl } from "@/pages/courses/shared";
import { coursesApi } from "@/services/api";
import { errorMessage } from "@/services/http";
import type { Attachment, BlockCheckResult, LessonBlockState, LessonBlockView as Block } from "@/types/api";

/** How a lesson is being worked through: preview / teacher view (nothing is
 *  saved) or a student's lesson (checks, results and listens are kept). */
export interface LessonRunner {
  check: (blockId: number, answers: Record<number, string[]>) => Promise<BlockCheckResult>;
  /** saved work per block (student) */
  saved?: Record<number, LessonBlockState>;
  /** listens used per block (student); with `countPlay` listening limits apply */
  plays?: Record<number, number>;
  countPlay?: (blockId: number) => Promise<number>;
  onChecked?: (blockId: number) => void;
}

const RunnerContext = createContext<LessonRunner | null>(null);

export function LessonRunnerProvider({ runner, children }: { runner: LessonRunner; children: ReactNode }) {
  return <RunnerContext.Provider value={runner}>{children}</RunnerContext.Provider>;
}

function useRunner(lessonId: number): LessonRunner {
  return useContext(RunnerContext) ?? { check: (blockId, answers) => coursesApi.check(lessonId, blockId, answers) };
}

function BlockHeader({ block }: { block: Block }) {
  const { t } = useI18n();
  const Icon = BLOCK_ICONS[block.type];
  return (
    <div className="mb-3">
      <p className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-accent">
        <Icon className="size-4" />
        {t.courses.block[block.type]}
      </p>
      {block.title && <h2 className="mt-1 break-words text-lg font-semibold text-primary">{block.title}</h2>}
    </div>
  );
}

function Missing() {
  const { t } = useI18n();
  return (
    <p className="flex items-center gap-2 rounded-xl bg-secondary px-4 py-3 text-sm text-muted-foreground">
      <FileWarning className="size-4" />
      {t.courses.missingFile}
    </p>
  );
}

function Transcript({ text }: { text: string }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  return (
    <div className="mt-3">
      <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        {open ? <ChevronUp /> : <ChevronDown />}
        {open ? t.courses.hideTranscript : t.courses.showTranscript}
      </Button>
      {open && <p className="mt-2 whitespace-pre-wrap rounded-xl bg-secondary/60 px-4 py-3 text-sm text-primary">{text}</p>}
    </div>
  );
}

function Audio({ file, maxPlays, blockId, runner }: { file?: Attachment; maxPlays?: number | null; blockId: number; runner: LessonRunner }) {
  const { t } = useI18n();
  if (!file) return <Missing />;
  const live = !!runner.countPlay;
  return (
    <div className="grid gap-1.5">
      <LimitedAudio
        file={file}
        count={runner.countPlay ? () => runner.countPlay!(blockId) : undefined}
        maxPlays={maxPlays ?? null}
        initialPlays={runner.plays?.[blockId] ?? 0}
        live={live}
      />
      {maxPlays && !live ? <p className="text-xs text-muted-foreground">{t.courses.playsLimit(maxPlays)}</p> : null}
    </div>
  );
}

function VideoFile({ file }: { file: Attachment }) {
  const { url, isLoading } = useBlobUrl(file);
  if (isLoading || !url) return <Skeleton className="aspect-video w-full" />;
  return <video controls preload="metadata" src={url} className="aspect-video w-full rounded-xl bg-black" controlsList="nodownload" />;
}

/** Answers -> check on the server -> results with the correct answers; can be tried again. */
function Exercise({ lessonId, block, layout }: { lessonId: number; block: Block; layout?: "stack" }) {
  const { t } = useI18n();
  const runner = useRunner(lessonId);
  const saved = runner.saved?.[block.id];
  const [answers, setAnswers] = useState<Record<number, string[]>>(() =>
    Object.fromEntries(Object.entries(saved?.answers ?? {}).map(([k, v]) => [Number(k), v])),
  );
  const [result, setResult] = useState<BlockCheckResult | null>(saved?.result ?? null);
  const check = useMutation({
    mutationFn: () => runner.check(block.id, answers),
    onSuccess: (r) => {
      setResult(r);
      runner.onChecked?.(block.id);
    },
    onError: (e) => toast.error(errorMessage(e)),
  });
  return (
    <div className={cn("grid gap-3", layout === "stack" && "content-start")}>
      {block.questions.map((q, i) => {
        const r = result?.results[i];
        return r && result ? (
          <QuestionView
            key={`${q.id}-r`}
            index={i}
            question={result.questions[i]}
            value={r.answer}
            result={{ id: i, question_id: i, answer: r.answer, is_correct: r.is_correct, points_awarded: r.points_awarded, teacher_comment: null }}
          />
        ) : (
          <QuestionView
            key={q.id}
            index={i}
            question={q}
            value={answers[i] ?? []}
            onChange={(v) => setAnswers((a) => ({ ...a, [i]: v }))}
          />
        );
      })}
      <div className="flex flex-wrap items-center gap-3">
        {result ? (
          <>
            <Badge variant={result.score === result.max_score ? "success" : result.score > 0 ? "warning" : "danger"} className="tabular">
              {t.courses.result(result.score, result.max_score)}
            </Badge>
            {saved && saved.attempts > 1 && saved.best_percent !== null && (
              <span className="text-xs text-muted-foreground">{t.myCourses.best(saved.best_percent)}</span>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setResult(null);
                setAnswers({});
              }}
            >
              <RotateCcw />
              {t.courses.tryAgain}
            </Button>
          </>
        ) : (
          <Button loading={check.isPending} onClick={() => check.mutate()}>{t.courses.check}</Button>
        )}
      </div>
    </div>
  );
}

function Shell({ block, children, className }: { block: Block; children: ReactNode; className?: string }) {
  return (
    <Card className={cn("p-5 sm:p-6", className)}>
      <BlockHeader block={block} />
      {children}
    </Card>
  );
}

/** One lesson block as a student sees it. */
export function LessonBlockView({ lessonId, block, files }: { lessonId: number; block: Block; files: Attachment[] }) {
  const { t } = useI18n();
  const runner = useRunner(lessonId);
  const c = block.content;
  const file = (id?: number | null) => (id ? files.find((f) => f.id === id) : undefined);

  switch (block.type) {
    case "text":
      return (
        <Shell block={block}>
          <Markdown text={c.body ?? ""} />
        </Shell>
      );
    case "grammar":
      return (
        <Shell block={block} className="border-l-4 border-l-accent">
          <Markdown text={c.body ?? ""} />
          {!!c.examples?.length && (
            <ul className="mt-4 grid gap-1.5 rounded-xl bg-accent-soft/40 px-4 py-3">
              {c.examples.map((e, i) => (
                <li key={i} className="text-sm italic text-primary">{e}</li>
              ))}
            </ul>
          )}
        </Shell>
      );
    case "vocabulary":
      return (
        <Shell block={block}>
          <ul className="grid gap-2 sm:grid-cols-2">
            {(c.words ?? []).map((w, i) => (
              <li key={i} className="rounded-xl border px-4 py-3">
                <p className="flex flex-wrap items-baseline gap-x-2">
                  <span className="text-base font-semibold text-primary">{w.word}</span>
                  {w.transcription && <span className="text-sm text-muted-foreground">[{w.transcription}]</span>}
                </p>
                {w.translation && <p className="text-sm text-primary">{w.translation}</p>}
                {w.example && <p className="mt-1 text-sm italic text-muted-foreground">{w.example}</p>}
              </li>
            ))}
          </ul>
        </Shell>
      );
    case "image": {
      const f = file(c.attachment_id);
      return (
        <Shell block={block}>
          <figure className="grid gap-2">
            {f ? <InlineMedia file={f} /> : <Missing />}
            {c.caption && <figcaption className="text-sm text-muted-foreground">{c.caption}</figcaption>}
          </figure>
        </Shell>
      );
    }
    case "audio":
      return (
        <Shell block={block} className="border-accent/20 bg-accent-soft/30">
          {c.body && <p className="mb-3 whitespace-pre-wrap text-sm text-muted-foreground">{c.body}</p>}
          <Audio file={file(c.attachment_id)} blockId={block.id} runner={runner} />
          {c.transcript && <Transcript text={c.transcript} />}
        </Shell>
      );
    case "video": {
      const f = file(c.attachment_id);
      return (
        <Shell block={block}>
          {c.provider && c.video_id ? (
            <div className="aspect-video w-full overflow-hidden rounded-xl bg-secondary">
              <iframe
                src={embedUrl(c.provider, c.video_id)}
                title={block.title ?? t.courses.block.video}
                className="size-full"
                allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; fullscreen"
                allowFullScreen
                referrerPolicy="strict-origin-when-cross-origin"
                loading="lazy"
              />
            </div>
          ) : f ? (
            <VideoFile file={f} />
          ) : (
            <Missing />
          )}
          {c.caption && <p className="mt-2 text-sm text-muted-foreground">{c.caption}</p>}
        </Shell>
      );
    }
    case "reading": {
      const img = file(c.image_id);
      return (
        <div className="grid gap-4 lg:grid-cols-2 lg:items-start">
          <Shell block={block} className="lg:sticky lg:top-20 lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
            {img && <div className="mb-3"><InlineMedia file={img} /></div>}
            <Markdown text={c.body ?? ""} />
          </Shell>
          <Exercise lessonId={lessonId} block={block} layout="stack" />
        </div>
      );
    }
    case "listening":
      return (
        <div className="grid gap-3">
          <Shell block={block} className="border-accent/20 bg-accent-soft/30">
            {c.body && <p className="mb-3 whitespace-pre-wrap text-sm text-muted-foreground">{c.body}</p>}
            <Audio file={file(c.attachment_id)} maxPlays={c.max_plays} blockId={block.id} runner={runner} />
            {c.transcript && <Transcript text={c.transcript} />}
          </Shell>
          <Exercise lessonId={lessonId} block={block} />
        </div>
      );
    default:
      // quiz and single exercises
      return (
        <div className="grid gap-3">
          {block.title || c.body ? (
            <Shell block={block}>
              {c.body && <p className="whitespace-pre-wrap text-sm text-muted-foreground">{c.body}</p>}
            </Shell>
          ) : (
            <div className="px-1 [&>div]:mb-0">
              <BlockHeader block={block} />
            </div>
          )}
          <Exercise lessonId={lessonId} block={block} />
        </div>
      );
  }
}
