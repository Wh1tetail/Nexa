import { CheckCircle2, Loader2, RotateCcw, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import type { BookJob } from "@/types/api";
import { fmtDateTime } from "@/utils/format";

export const isActiveJob = (j: BookJob | null | undefined) => !!j && (j.status === "queued" || j.status === "running");

/** A background job: progress while it runs, the outcome afterwards, cancel / run again. */
export function JobProgress({
  title,
  job,
  onCancel,
  cancelling,
  onRestart,
  restarting,
  generation,
}: {
  title: string;
  job: BookJob;
  onCancel: () => void;
  cancelling: boolean;
  onRestart: () => void;
  restarting: boolean;
  /** wording for a generation job: "generation finished", "generate again" */
  generation?: boolean;
}) {
  const { t, locale } = useI18n();
  const active = isActiveJob(job);
  const failed = job.status === "failed";
  const Icon = active ? Loader2 : job.status === "done" ? CheckCircle2 : XCircle;
  const tone = active ? "text-accent" : job.status === "done" ? "text-success-strong" : failed ? "text-danger" : "text-muted-foreground";

  return (
    <Card className={cn("p-5 sm:p-6", failed && "border-danger/40")}>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 items-start gap-3">
          <Icon className={cn("mt-0.5 size-5 shrink-0", tone, active && "animate-spin motion-reduce:animate-none")} />
          <div className="min-w-0">
            <p className="font-semibold text-primary">{title}</p>
            <p className="text-sm text-muted-foreground">
              {job.cancel_requested && active ? t.books.cancelling : (generation ? t.books.genStatus : t.books.jobStatus)[job.status]}
              {job.finished_at && !active && <> · {fmtDateTime(job.finished_at, locale)}</>}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          {active ? (
            <Button variant="outline" size="sm" loading={cancelling} disabled={job.cancel_requested} onClick={onCancel}>
              {t.books.cancel}
            </Button>
          ) : (
            <Button variant="outline" size="sm" loading={restarting} onClick={onRestart}>
              {!restarting && <RotateCcw />}
              {generation ? t.books.generateAgain : t.books.reprocess}
            </Button>
          )}
        </div>
      </div>

      {active && (
        <div className="mt-4 grid gap-1.5" aria-live="polite">
          <Progress value={job.status === "queued" ? 0 : job.progress} />
          <div className="flex flex-wrap justify-between gap-x-4 text-xs text-muted-foreground">
            <span>{t.books.jobProgress(job.progress)}</span>
            {job.attempts > 1 && <span>{t.books.attempt(job.attempts, job.max_attempts)}</span>}
          </div>
          <p className="mt-2 text-xs text-muted-foreground">{t.books.queuedHint}</p>
        </div>
      )}
      {failed && (
        <p className="mt-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger-strong">
          {(job.error_code && t.books.jobError[job.error_code]) || t.books.jobErrorOther}
        </p>
      )}
    </Card>
  );
}
