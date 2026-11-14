import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, EyeOff, Hourglass } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { ErrorState, PageSkeleton } from "@/components/common";
import { AttemptBadge } from "@/components/common/StatusBadges";
import { QuestionView } from "@/components/tests/QuestionView";
import { TestMaterials } from "@/components/tests/TestMedia";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useI18n } from "@/contexts/I18nContext";
import { cn } from "@/lib/utils";
import { meApi } from "@/services/api";
import { fmtDateTime } from "@/utils/format";

export default function AttemptResultPage() {
  const { attemptId } = useParams();
  const { t, locale } = useI18n();
  const q = useQuery({ queryKey: ["me", "attempt", attemptId], queryFn: () => meApi.attempt(Number(attemptId)) });

  if (q.isLoading) return <PageSkeleton />;
  if (q.isError || !q.data) return <ErrorState onRetry={() => q.refetch()} />;
  const a = q.data;
  const byQ = Object.fromEntries(a.answers.map((x) => [x.question_id, x]));
  const pct = a.percent;
  const ring = pct === null ? "text-muted-foreground" : pct >= 80 ? "text-success" : pct >= 50 ? "text-warning" : "text-danger";

  return (
    <div className="mx-auto max-w-3xl">
      <Link to="/student/tests" className="mb-4 inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-primary">
        <ArrowLeft className="size-4" />
        {t.tests.title}
      </Link>

      <Card className="flex flex-col items-center gap-6 p-6 text-center sm:flex-row sm:text-left">
        <div className="relative size-28 shrink-0">
          <svg viewBox="0 0 36 36" className="size-28 -rotate-90">
            <circle cx="18" cy="18" r="15.5" fill="none" className="stroke-secondary" strokeWidth="3" />
            <circle
              cx="18"
              cy="18"
              r="15.5"
              fill="none"
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              strokeDasharray={`${((pct ?? 0) * 97.4) / 100} 97.4`}
              className={cn("transition-all duration-700", ring)}
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center">
            {pct === null ? (
              <Hourglass className="size-7 text-muted-foreground" />
            ) : (
              <span className="tabular text-2xl font-semibold text-primary">{pct}%</span>
            )}
          </div>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:justify-start">
            <AttemptBadge status={a.status} />
            {a.passed !== null && (
              <Badge variant={a.passed ? "success" : "danger"}>
                {a.passed ? t.tests.passed : t.tests.notPassed} · {t.tests.passingAt(a.passing_percent ?? 0)}
              </Badge>
            )}
          </div>
          <h1 className="mt-2 text-xl font-semibold">{a.test_title}</h1>
          {a.score !== null && (
            <p className="tabular mt-1 text-sm text-muted-foreground">
              {t.tests.score}: {a.score} / {a.max_score}
            </p>
          )}
          <p className="mt-1 text-sm text-muted-foreground">{fmtDateTime(a.submitted_at, locale)}</p>
          {a.status === "pending_review" && <p className="mt-3 text-sm text-primary">{t.tests.awaitingReview}</p>}
          {a.status === "graded" && !a.show_correct_answers && (
            <p className="mt-3 inline-flex items-center gap-1.5 text-sm text-muted-foreground">
              <EyeOff className="size-4" />
              {t.tests.answersHidden}
            </p>
          )}
        </div>
      </Card>

      <div className="mt-6 grid gap-4">
        <TestMaterials files={a.files} usedIds={a.questions.flatMap((x) => x.attachment_ids)} />
        {a.questions.map((qq, i) => (
          <QuestionView
            key={qq.id}
            index={i}
            question={qq}
            files={a.files}
            value={byQ[qq.id]?.answer ?? []}
            result={a.status === "graded" ? byQ[qq.id] : undefined}
          />
        ))}
      </div>
    </div>
  );
}
