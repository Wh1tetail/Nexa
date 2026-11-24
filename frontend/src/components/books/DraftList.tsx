import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ClipboardCheck, FileQuestion, Quote } from "lucide-react";
import { Link } from "react-router-dom";

import { CardListSkeleton, EmptyState, ErrorState } from "@/components/common";
import { QuestionView } from "@/components/tests/QuestionView";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { booksApi } from "@/services/api";
import type { Book, Question, QuestionDraft } from "@/types/api";

/** A draft shown with the test's own question view (right answers marked). */
export function draftAsQuestion(d: QuestionDraft): Question {
  return {
    id: d.id,
    position: 0,
    type: d.question.type,
    text: d.question.text,
    options: d.question.options,
    correct_answer: d.question.correct_answer,
    points: d.question.points,
    explanation: d.question.explanation ?? null,
    attachment_ids: [],
    config: (d.question.config ?? {}) as Question["config"],
  };
}

function DraftCard({ d, index }: { d: QuestionDraft; index: number }) {
  const { t } = useI18n();
  return (
    <div className="grid gap-2">
      <QuestionView index={index} question={draftAsQuestion(d)} value={[]} />
      <div className="flex flex-wrap items-center gap-2 px-1 text-xs text-muted-foreground">
        <Badge variant={d.status === "draft" ? "warning" : d.status === "rejected" ? "danger" : "success"}>
          {t.books.draftStatus[d.status]}
        </Badge>
        <Badge variant="neutral">{t.books.difficultyOne[d.difficulty]}</Badge>
        <span>{t.books.sourcePage(d.page_start, d.page_end)}</span>
        {d.warnings.map((w) => (
          <Badge key={w} variant="danger" className="gap-1">
            <AlertTriangle className="size-3" />
            {t.books.warning[w] ?? w}
          </Badge>
        ))}
      </div>
      {d.excerpt && (
        <p className="flex gap-2 rounded-lg bg-secondary px-3 py-2 text-sm italic text-muted-foreground">
          <Quote className="mt-0.5 size-3.5 shrink-0" />
          <span className="break-words">{d.excerpt}</span>
        </p>
      )}
    </div>
  );
}

/** Generated drafts (read-only in stage 5; review and export come in stage 6). */
export function DraftList({ book }: { book: Book }) {
  const { t } = useI18n();
  const q = useQuery({ queryKey: ["books", book.id, "drafts"], queryFn: () => booksApi.drafts(book.id) });
  if (q.isLoading) return <CardListSkeleton rows={2} />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  return (
    <section className="space-y-3">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-baseline sm:justify-between">
        <h2 className="text-lg font-semibold text-primary">{t.books.drafts}</h2>
        {q.data.length > 0 && (
          <Button asChild>
            <Link to={`/methodist/books/${book.id}/review`}><ClipboardCheck />{t.books.openReview}</Link>
          </Button>
        )}
      </div>
      {q.data.length === 0 ? (
        <Card><EmptyState icon={FileQuestion} title={t.books.noDrafts} text={t.books.noDraftsText} /></Card>
      ) : (
        q.data.map((d, i) => <DraftCard key={d.id} d={d} index={i} />)
      )}
    </section>
  );
}
